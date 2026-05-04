from flask import Blueprint, jsonify, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import redis_conn
from app.models import UserRole
from app.services.chatbot_service import ChatbotService, get_chatbot_model
from app.routes.auth import role_required
import json
import logging

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)
chatbot_model = None


# ✅ FIX 1: SAFE INITIALIZATION
def init_chatbot_model(app):
    global chatbot_model
    try:
        chatbot_model = get_chatbot_model(app)
        if chatbot_model:
            logger.info("Chatbot model initialized successfully")
        else:
            logger.warning("Chatbot model NOT initialized (check GEMINI_API_KEY)")
    except Exception as e:
        logger.error(f"Chatbot init failed: {e}")
        chatbot_model = None


# ─────────────────────────────────────────────
# REDIS CHAT HISTORY
# ─────────────────────────────────────────────
def get_conversation_history(patient_id: str, limit: int = 10) -> list:
    key = f"chat:history:{patient_id}"
    history = redis_conn.lrange(key, 0, limit - 1)

    try:
        return [json.loads(msg) for msg in history]
    except:
        return []


def save_message(patient_id: str, role: str, content: str):
    key = f"chat:history:{patient_id}"
    message = {"role": role, "content": content}

    redis_conn.lpush(key, json.dumps(message))
    redis_conn.ltrim(key, 0, 99)
    redis_conn.expire(key, 86400)


# ─────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ─────────────────────────────────────────────
@chat_bp.route("/message", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def send_message():
    patient_id = get_jwt_identity()
    data = request.get_json() or {}

    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "message required"}), 400

    # 🚨 Emergency detection
    if ChatbotService.handle_emergency_query(user_message):
        emergency_response = ChatbotService.emergency_response(user_message)

        save_message(patient_id, "user", user_message)
        save_message(patient_id, "assistant", emergency_response)

        return jsonify({
            "emergency": True,
            "response": emergency_response,
        }), 200

    history = get_conversation_history(patient_id, limit=5)

    save_message(patient_id, "user", user_message)

    stream = data.get("stream", False)

    if stream:
        return handle_streaming_response(patient_id, user_message, history)
    else:
        return handle_non_streaming_response(patient_id, user_message, history)


# ─────────────────────────────────────────────
# NON-STREAMING
# ─────────────────────────────────────────────
def handle_non_streaming_response(patient_id, user_message, history):
    try:
        if not chatbot_model:
            return jsonify({
                "response": "Chatbot unavailable. Check API key.",
                "emergency": False
            }), 200

        response_text = ""
        for chunk in ChatbotService.stream_response(user_message, chatbot_model, history):
            response_text += chunk

        save_message(patient_id, "assistant", response_text)

        return jsonify({
            "response": response_text,
            "emergency": False
        }), 200

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": "Failed to get response"}), 500


# ─────────────────────────────────────────────
# STREAMING (STABLE)
# ─────────────────────────────────────────────
def handle_streaming_response(patient_id, user_message, history):

    def generate():
        full_response = ""

        try:
            if not chatbot_model:
                yield f'data: {json.dumps({"error": "Chatbot unavailable"})}\n\n'
                return

            for chunk in ChatbotService.stream_response(user_message, chatbot_model, history):
                if chunk:
                    full_response += chunk
                    yield f'data: {json.dumps({"chunk": chunk})}\n\n'

            save_message(patient_id, "assistant", full_response)

            yield f'data: {json.dumps({"complete": True})}\n\n'

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f'data: {json.dumps({"error": str(e)})}\n\n'

    return Response(generate(), mimetype="text/event-stream")


# ─────────────────────────────────────────────
# HISTORY
# ─────────────────────────────────────────────
@chat_bp.route("/history", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_history():
    patient_id = get_jwt_identity()

    history = get_conversation_history(patient_id, 50)
    history.reverse()

    return jsonify({
        "messages": history
    }), 200


@chat_bp.route("/clear-history", methods=["DELETE"])
@jwt_required()
@role_required(UserRole.PATIENT)
def clear_history():
    patient_id = get_jwt_identity()
    redis_conn.delete(f"chat:history:{patient_id}")

    return jsonify({"message": "History cleared"}), 200