from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.query_router import BusinessAssistantQueryRouter
from app.utils.decorators import get_active_store_id

assistant_bp = Blueprint('assistant', __name__, url_prefix='/api/v1/assistant')

@assistant_bp.route('/query', methods=['POST'])
@login_required
def query_assistant():
    """
    POST /api/v1/assistant/query
    Answers free-form business questions grounded strictly in store DB data (API_SPEC.md §3).
    """
    data = request.get_json() or {}
    question = data.get('question')

    if not question:
        return jsonify({
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "question parameter is required."
            }
        }), 400

    result = BusinessAssistantQueryRouter.answer_query(get_active_store_id(), question)
    return jsonify(result), 200
