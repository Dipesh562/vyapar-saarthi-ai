import os
import json
from typing import Dict, Any
from config import Config

class STTClient:
    @staticmethod
    def transcribe_audio(audio_bytes: bytes, filename: str = None, language_hint: str = None) -> Dict[str, Any]:
        """
        Speech-to-Text client wrapper using Gemini Multimodal Audio API (VOICE_SPEC.md §7).
        Transcribes Marathi, Hindi, Hinglish, or English audio streams.
        Returns STT_UNAVAILABLE error if service is unconfigured or fails.
        """
        if not audio_bytes or len(audio_bytes) < 10:
            return {
                "transcript": "",
                "confidence": 0.0,
                "language_detected": language_hint or "unknown",
                "error": "STT_UNAVAILABLE"
            }

        gemini_key = Config.GEMINI_API_KEY
        if not gemini_key or gemini_key.startswith('mock') or gemini_key == 'mock_key_for_dev':
            return {
                "transcript": "",
                "confidence": 0.0,
                "language_detected": language_hint or "unknown",
                "error": "STT_UNAVAILABLE"
            }

        # Determine MIME type from filename extension
        mime_type = "audio/wav"
        if filename:
            fn_lower = filename.lower()
            if fn_lower.endswith('.webm'):
                mime_type = "audio/webm"
            elif fn_lower.endswith('.mp3'):
                mime_type = "audio/mp3"
            elif fn_lower.endswith('.ogg'):
                mime_type = "audio/ogg"
            elif fn_lower.endswith('.m4a'):
                mime_type = "audio/m4a"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

            prompt = (
                f"Listen to this Indian store merchant's spoken voice command. "
                f"Preferred language hint: {language_hint or 'hi-IN'}. "
                f"Transcribe the audio accurately in its spoken language (Hindi/Marathi/Hinglish/English). "
                f"Return ONLY valid JSON matching this schema: "
                f"{{\"transcript\": \"<exact spoken text>\", \"confidence\": <float 0.0 to 1.0>, \"language_detected\": \"hi-IN\"|\"mr-IN\"|\"en-IN\"}}"
            )

            for model_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[audio_part, prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )

                    if response.text:
                        parsed = json.loads(response.text.strip())
                        if isinstance(parsed, dict) and "transcript" in parsed:
                            return {
                                "transcript": parsed.get("transcript", "").strip(),
                                "confidence": float(parsed.get("confidence", 0.90)),
                                "language_detected": parsed.get("language_detected", language_hint or "hi-IN")
                            }
                except Exception as sub_err:
                    print(f"[STTClient] Gemini audio model ({model_name}) notice: {sub_err}")

        except Exception as err:
            print(f"[STTClient] Audio transcription error: {err}")

        return {
            "transcript": "",
            "confidence": 0.0,
            "language_detected": language_hint or "unknown",
            "error": "STT_UNAVAILABLE"
        }
