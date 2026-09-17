from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.ai_orchestration import AIOrchestrationService

ai_bp = Blueprint('ai', __name__, url_prefix='/api/v1/ai')

@ai_bp.route('/understand', methods=['POST'])
@login_required
def understand():
    """
    POST /api/v1/ai/understand
    Converts transcript into structured JSON intent & entities (API_SPEC.md §3).
    Never mutates DB or returns product_id.
    """
    data = request.get_json() or {}
    transcript = data.get('transcript')
    context = data.get('context', {})

    if not transcript:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "transcript is required."
            }
        }), 400

    result = AIOrchestrationService.understand_transcript(transcript, context)
    return jsonify(result), 200
