import uuid
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import VoiceSession, Customer
from app.services.stt_client import STTClient
from app.services.ai_orchestration import AIOrchestrationService
from app.services.product_matching import ProductMatchingEngine
from app.services.billing_engine import BillingEngine
from app.services.voice_feedback import VoiceFeedbackService
from app.services.cart_session import MerchantCartSession

voice_bp = Blueprint('voice', __name__, url_prefix='/api/v1/voice')

@voice_bp.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    """
    POST /api/v1/voice/transcribe
    Accepts audio file upload, performs STT transcription, and records voice session.
    """
    session_id = request.form.get('session_id') or str(uuid.uuid4())
    language_hint = request.form.get('language_hint')

    audio_file = request.files.get('audio')
    audio_bytes = audio_file.read() if audio_file else b''

    # Fallback to plain text if passed in form for dev/testing
    raw_transcript_text = request.form.get('transcript_text')

    if raw_transcript_text:
        transcript = raw_transcript_text
        confidence = 0.95
    else:
        stt_res = STTClient.transcribe_audio(audio_bytes, language_hint=language_hint)
        transcript = stt_res.get('transcript', '')
        confidence = stt_res.get('confidence', 0.0)

    if confidence < 0.6:
        retry_msg = VoiceFeedbackService.build_stt_failed_message()
        return jsonify({
            "status": "stt_failed",
            "message": retry_msg,
            "error": {
                "code": "LOW_CONFIDENCE_TRANSCRIPTION",
                "message": retry_msg
            }
        }), 422

    # Save session
    session = VoiceSession(
        session_id=session_id,
        store_id=current_user.store_id,
        user_id=current_user.user_id,
        transcript=transcript,
        confidence_score=confidence
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        "session_id": session_id,
        "transcript": transcript,
        "confidence": float(confidence)
    }), 200

@voice_bp.route('/process_bill', methods=['POST'])
@login_required
def process_voice_bill():
    """
    POST /api/v1/voice/process_bill (M11: End-to-End Voice Billing Integration)
    Accepts spoken text or audio -> parses AI intent -> matches products -> creates draft bill!
    """
    data = request.get_json() or {}
    transcript = data.get('transcript')
    session_id = data.get('session_id') or str(uuid.uuid4())

    retry_msg = VoiceFeedbackService.build_stt_failed_message()

    if not transcript:
        return jsonify({
            "status": "stt_failed",
            "message": retry_msg,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": retry_msg
            }
        }), 400

    # Step 1: Fetch store cart session context & AI Intent/Entity Extraction
    session_ctx = MerchantCartSession.get_context(current_user.store_id)
    ai_res = AIOrchestrationService.understand_transcript(transcript, context=session_ctx)
    intent = ai_res.get('intent', 'create_bill')
    confidence = ai_res.get('confidence', 1.0)

    if intent in ['check_stock', 'business_query']:
        return jsonify({
            "session_id": session_id,
            "status": "query",
            "intent": intent,
            "message": f"Recognized intent: '{intent}'. Please use the Assistant tab for business queries."
        }), 200

    if confidence < 0.6:
        return jsonify({
            "status": "stt_failed",
            "message": retry_msg,
            "error": {
                "code": "LOW_CONFIDENCE_INTENT",
                "message": retry_msg
            }
        }), 422

    parsed_items = ai_res.get('items', [])
    cust_name = ai_res.get('customer_name')
    payment_status = ai_res.get('payment_status', 'paid')

    # Resolve customer if spoken
    resolved_customer_id = None
    if cust_name:
        cust = Customer.query.filter(
            Customer.store_id == current_user.store_id,
            Customer.name.ilike(f"%{cust_name}%")
        ).first()
        if cust:
            resolved_customer_id = cust.customer_id
            MerchantCartSession.set_last_customer(current_user.store_id, {"customer_id": cust.customer_id, "name": cust.name})

    # Step 2: Product Matching Engine for each raw item entity
    matched_items = []
    clarifications_needed = []

    for item in parsed_items:
        raw_text = item.get('raw_text', '')
        quantity = item.get('quantity', 1.0)

        # Handle referential items e.g., "add 2 more", "aur do kilo"
        if item.get('is_reference') or raw_text.lower().strip() in ['more', 'aur', 'add more', 'do more', '2 more', 'aur do']:
            last_item_ref = MerchantCartSession.resolve_reference(current_user.store_id, "item")
            if last_item_ref:
                raw_text = last_item_ref.get('raw_text') or last_item_ref.get('name') or raw_text

        match_result = ProductMatchingEngine.match_product(current_user.store_id, raw_text)

        if match_result['matched'] and match_result['product']:
            product = match_result['product']
            matched_items.append({
                "product_id": product.product_id,
                "quantity": quantity
            })
            MerchantCartSession.set_last_item(current_user.store_id, {
                "product_id": product.product_id,
                "name": product.name,
                "raw_text": raw_text,
                "quantity": quantity
            })
        elif match_result['needs_clarification']:
            candidates = match_result.get('candidates', [])
            question = match_result.get('clarification_question')
            clarifications_needed.append({
                "raw_text": raw_text,
                "quantity": quantity,
                "question": question,
                "candidates": candidates,
                "speech_text": VoiceFeedbackService.build_clarification_speech_text(question, candidates)
            })
        else:
            question = f"Product '{raw_text}' not found in your inventory."
            clarifications_needed.append({
                "raw_text": raw_text,
                "quantity": quantity,
                "question": question,
                "candidates": [],
                "speech_text": VoiceFeedbackService.build_clarification_speech_text(question, [])
            })

    if not matched_items and not clarifications_needed:
        return jsonify({
            "status": "stt_failed",
            "message": retry_msg,
            "error": {
                "code": "NO_PRODUCTS_MATCHED",
                "message": retry_msg
            }
        }), 400

    if clarifications_needed:
        return jsonify({
            "session_id": session_id,
            "status": "needs_clarification",
            "clarifications": clarifications_needed,
            "partial_matched_items": matched_items
        }), 200

    # Step 3: Deterministic Billing Engine -> Create or Update Draft Bill
    draft_bill_id = data.get('draft_bill_id')
    final_items = matched_items
    
    if draft_bill_id:
        existing_draft = BillingEngine.get_draft_bill(draft_bill_id, current_user.store_id)
        if existing_draft:
            # Extract existing items
            existing_items_input = [{'product_id': item['product_id'], 'quantity': item['quantity']} for item in existing_draft.get('line_items', [])]
            
            # Merge with new matched_items by aggregating quantities
            merged_items_dict = {}
            for item in existing_items_input + matched_items:
                pid = item['product_id']
                merged_items_dict[pid] = merged_items_dict.get(pid, 0.0) + item['quantity']
            
            final_items = [{'product_id': pid, 'quantity': qty} for pid, qty in merged_items_dict.items()]
            
            # Use existing customer if not newly resolved
            if not resolved_customer_id:
                resolved_customer_id = existing_draft.get('customer_id')
                
            # Void the old draft
            BillingEngine.void_draft_bill(draft_bill_id, current_user.store_id)

    draft_bill = BillingEngine.create_draft_bill(
        store_id=current_user.store_id,
        items=final_items,
        customer_id=resolved_customer_id
    )
    MerchantCartSession.update_cart(current_user.store_id, final_items)

    readback_text = VoiceFeedbackService.build_readback_text(draft_bill)

    return jsonify({
        "session_id": session_id,
        "status": "draft_created",
        "payment_status": payment_status,
        "draft_bill": draft_bill,
        "readback_text": readback_text
    }), 201

@voice_bp.route('/feedback', methods=['POST'])
@login_required
def voice_feedback():
    """
    POST /api/v1/voice/feedback
    Records merchant clarification feedback to learn product synonyms.
    """
    data = request.get_json() or {}
    spoken_text = data.get('spoken_text')
    product_id = data.get('chosen_product_id')

    if not spoken_text or not product_id:
        return jsonify({"status": "error", "message": "spoken_text and chosen_product_id are required"}), 400

    synonym = ProductMatchingEngine.record_merchant_correction(
        store_id=current_user.store_id,
        spoken_text=spoken_text,
        product_id=product_id
    )

    return jsonify({
        "status": "success",
        "message": f"Learned synonym '{spoken_text}' -> Product ID {product_id}",
        "evidence_count": synonym.evidence_count if synonym else 1
    }), 200

