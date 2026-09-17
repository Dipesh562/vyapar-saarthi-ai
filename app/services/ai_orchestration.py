import os
import json
import re
from typing import Dict, Any
import anthropic
from config import Config

SYSTEM_PROMPT = """You are Vyapar Saarthi AI, a voice-first assistant for Indian kirana stores.
Your task is to parse spoken transcripts (in Marathi, Hindi, Hinglish, or English) into structured JSON.

Rules:
1. Output ONLY valid JSON matching this schema:
{
  "intent": "create_bill" | "record_payment" | "check_stock" | "business_query",
  "items": [
    { "raw_text": "<spoken item name>", "quantity": <number>, "unit": "<unit string or null>", "is_reference": boolean }
  ],
  "customer_name": "<spoken customer name or null>",
  "payment_status": "paid" | "udhaar" | null,
  "confidence": <float between 0.0 and 1.0>,
  "needs_clarification": boolean
}

2. NEVER resolve a database product_id or price. Extract raw item names as spoken (e.g. "aata", "fortune oil", "tur dal").
3. Quantities should be numbers (e.g. "do kilo" -> quantity: 2, unit: "kg"; "aadha kilo" -> quantity: 0.5, unit: "kg"; "ek packet" -> quantity: 1, unit: "packet").
4. Context Awareness:
   - If Context is provided and contains last_referenced_item, and transcript mentions relative modification (e.g. "add two more", "aur do kilo", "change to 3 kg"), use last_referenced_item details and set "is_reference": true.
   - If transcript is a relative modification but NO last_referenced_item exists in Context, extract spoken text as raw_text and set "is_reference": true.
5. If intent is unclear, set confidence low (< 0.6) and needs_clarification: true.
"""

class AIOrchestrationService:
    @staticmethod
    def _preprocess_transcript(transcript: str) -> str:
        """
        Preprocesses transcript: normalizes Devanagari digits, spoken numbers, and unit names ONLY.
        Does NOT extract items or short-circuit AI execution.
        """
        if not transcript:
            return ""
        try:
            from app.services.product_matching import _normalize_multilingual
            return _normalize_multilingual(transcript)
        except Exception:
            return transcript.strip()

    @staticmethod
    def understand_transcript(transcript: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interprets transcript into structured JSON (AI_SPEC.md §4).
        Respects VOICE_PIPELINE_MODE ('ai_first' vs 'legacy').
        In 'ai_first' mode: Preprocess -> Gemini -> Claude -> Regex Fallback.
        In 'legacy' mode: Regex Fallback -> Gemini -> Claude -> Regex Fallback.
        """
        if not transcript or not transcript.strip():
            return {
                "intent": "create_bill",
                "items": [],
                "customer_name": None,
                "payment_status": "paid",
                "confidence": 0.0,
                "needs_clarification": True
            }

        pipeline_mode = os.environ.get('VOICE_PIPELINE_MODE', getattr(Config, 'VOICE_PIPELINE_MODE', 'ai_first')).lower()

        # ── LEGACY MODE: Regex First ──
        if pipeline_mode == 'legacy':
            parsed_fast = AIOrchestrationService._fallback_parser(transcript)
            if parsed_fast and parsed_fast.get("items") and len(parsed_fast["items"]) > 0:
                return parsed_fast

        # ── AI FIRST MODE: Preprocess -> Gemini -> Claude -> Fallback ──
        cleaned_transcript = AIOrchestrationService._preprocess_transcript(transcript)

        gemini_key = Config.GEMINI_API_KEY
        anthropic_key = Config.ANTHROPIC_API_KEY

        # 1. Try Gemini Models
        if gemini_key and not gemini_key.startswith('mock') and gemini_key != 'mock_key_for_dev':
            for model_name in ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-flash-latest']:
                try:
                    from google import genai
                    from google.genai import types

                    client = genai.Client(api_key=gemini_key)
                    prompt_content = f"Spoken Transcript: \"{transcript}\"\nCleaned Transcript: \"{cleaned_transcript}\"\nContext: {json.dumps(context or {})}"

                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_content,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )

                    if response.text:
                        parsed = json.loads(response.text.strip())
                        if isinstance(parsed, dict) and "items" in parsed:
                            return parsed
                except Exception as gemini_err:
                    print(f"[AIOrchestrationService] Gemini ({model_name}) notice: {gemini_err}")

        # 2. Try Anthropic Claude API
        if anthropic_key and not anthropic_key.startswith('mock') and anthropic_key != 'mock_key_for_dev':
            try:
                client = anthropic.Anthropic(api_key=anthropic_key)
                prompt_content = f"Spoken Transcript: \"{transcript}\"\nCleaned Transcript: \"{cleaned_transcript}\"\nContext: {json.dumps(context or {})}"

                response = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=500,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt_content}]
                )

                response_text = response.content[0].text.strip()
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
            except Exception as anthropic_err:
                print(f"[AIOrchestrationService] Anthropic error: {anthropic_err}")

        # 3. Rule-based Kirana Regex Fallback Parser
        return AIOrchestrationService._fallback_parser(transcript)

    @staticmethod
    def _fallback_parser(transcript: str) -> Dict[str, Any]:
        """
        Deterministic fallback parser for multi-item spoken utterances.
        Uses Kirana dictionary normalization (Hindi numbers -> digits, Hindi units -> English)
        and segment-based extraction so multiple items spoken together are each extracted cleanly.
        """
        try:
            from app.services.product_matching import _normalize_multilingual
            t = _normalize_multilingual(transcript)
        except Exception:
            try:
                from unidecode import unidecode
                t = unidecode(transcript).lower()
            except ImportError:
                t = transcript.lower()

        items = []
        intent = "create_bill"
        customer_name = None
        payment_status = "paid"

        if "udhaar" in t or "khata" in t or "credit" in t:
            payment_status = "udhaar"

        # Extract customer name e.g. "rahul ke khate me", "ramesh ko", "suresh ka"
        cust_match = re.search(r'([a-zA-Z]+)\s+(ke khate|ko|ka)', t, re.IGNORECASE)
        if cust_match:
            customer_name = cust_match.group(1).capitalize()
            # Clean customer suffix clause out of text to avoid polluting product names
            t = re.sub(r'\b[a-zA-Z]+\s+(ke khate|ko|ka)(\s+(me|pe))?\b', '', t, flags=re.IGNORECASE)

        # Remove trailing payment status keywords from item parsing text
        t = re.sub(r'\b(udhaar|khata|credit|paid|online)\b', '', t, flags=re.IGNORECASE).strip()

        # Units pattern
        UNITS_PAT = r'(packet|packets|pkt|kilo|kg|kilogram|liter|litre|litres|liters|l|g|gram|grams|ml|milliliter|dozen|box|piece|pieces|pc|pcs)'
        unit_map = {
            'kilo': 'kg', 'kilogram': 'kg', 'liter': 'litre', 'litres': 'litre',
            'liters': 'litre', 'l': 'litre', 'milliliter': 'ml', 'grams': 'gram',
            'g': 'gram', 'packets': 'packet', 'pkt': 'packet',
            'piece': 'pc', 'pieces': 'pc', 'pcs': 'pc'
        }
        NOISE_WORDS = {'ke', 'ko', 'me', 'pe', 'ka', 'ki', 'hai', 'aur', 'and', 'do', 'de', 'bhi', 'ek'}

        # Split transcript into item chunks by delimiters: comma, 'aur', 'and', or before a digit sequence
        raw_chunks = re.split(r',|\baur\b|\band\b|(?=\b\d+(?:\.\d+)?\b)', t)

        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Try parsing quantity + optional unit + product name
            m = re.match(r'^(\d+(?:\.\d+)?)\s*' + UNITS_PAT + r'?\s*(.+)$', chunk, re.IGNORECASE)
            if m:
                qty_str = m.group(1)
                unit_str = (m.group(2) or 'pc').strip().lower()
                raw_item = (m.group(3) or '').strip()

                unit_str = unit_map.get(unit_str, unit_str)
                try:
                    qty = float(qty_str)
                except ValueError:
                    qty = 1.0

                # Clean trailing noise words
                raw_item = re.sub(r'\b(ke|ko|me|pe|ka|ki|hai|aur|and|do|de|bhi)\b', '', raw_item, flags=re.IGNORECASE).strip()
                raw_item = re.sub(r'\s+', ' ', raw_item)

                if raw_item and raw_item.lower() not in NOISE_WORDS:
                    items.append({
                        "raw_text": raw_item,
                        "quantity": qty,
                        "unit": unit_str,
                        "is_reference": raw_item.lower() in ['more', 'aur', 'add more', 'do more', '2 more', 'aur do']
                    })
            else:
                # Chunk without leading quantity e.g. "fortune oil"
                clean_chunk = re.sub(r'\b(ke|ko|me|pe|ka|ki|hai|aur|and|do|de|bhi)\b', '', chunk, flags=re.IGNORECASE).strip()
                clean_chunk = re.sub(r'\s+', ' ', clean_chunk)
                if clean_chunk and clean_chunk.lower() not in NOISE_WORDS and len(clean_chunk) > 1:
                    items.append({
                        "raw_text": clean_chunk,
                        "quantity": 1.0,
                        "unit": "pc",
                        "is_reference": clean_chunk.lower() in ['more', 'aur', 'add more', 'do more', '2 more', 'aur do']
                    })

        if not items:
            if "kitna" in t or "stock" in t:
                intent = "check_stock"
            else:
                items = [{"raw_text": transcript.strip(), "quantity": 1.0, "unit": "pc"}]

        return {
            "intent": intent,
            "items": items,
            "customer_name": customer_name,
            "payment_status": payment_status,
            "confidence": 0.85,
            "needs_clarification": False
        }
