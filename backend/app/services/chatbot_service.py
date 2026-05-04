"""
AI Chatbot Service: Streaming LLM endpoint for patient medical queries.
Uses Gemini with streaming responses.
"""

import google.generativeai as genai
from app.extensions import db
from app.models import User
import logging

logger = logging.getLogger(__name__)


class ChatbotService:
    """Medical chatbot with Gemini streaming."""
    
    SYSTEM_PROMPT = """You are a helpful healthcare assistant AI for CareFlow Hospital. 
Your role is to:
1. Provide general health information and advice
2. Help patients understand their symptoms (NOT diagnose)
3. Guide patients through the appointment process
4. Answer FAQs about hospital services
5. Provide emergency guidance when needed

IMPORTANT CONSTRAINTS:
- Never attempt to diagnose diseases (that's the doctor's job)
- Always encourage patients to consult with a doctor for medical concerns
- Never prescribe medications or specific treatments
- If a patient reports emergency symptoms, urge them to seek immediate medical attention
- Keep responses concise and empathetic
- Redirect complex medical questions to doctors

You are trained on medical knowledge but act as a support assistant, not a doctor."""
    
    @staticmethod
    def initialize(api_key: str, model_name: str):
        """Initialize Gemini model for chatbot."""
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(
            model_name=model_name,
            system_instruction=ChatbotService.SYSTEM_PROMPT,
        )
    
    @staticmethod
    def stream_response(user_message: str, model=None, conversation_history=None) -> str:
        """
        Get streaming response from chatbot.
        
        Args:
            user_message: Patient's query
            model: Gemini model instance
            conversation_history: Previous messages for context
        
        Yields:
            text chunks as they stream
        """
        if not model:
            yield "I'm currently unavailable. Please contact the hospital directly."
            return
        
        try:
            # Build message list for multi-turn conversation
            messages = []
            
            # Add conversation history if provided
            if conversation_history:
                for msg in conversation_history:
                    role = msg["role"]

                    # 🔥 FIX: convert roles for Gemini
                    if role == "assistant":
                        role = "model"
                    elif role != "user":
                        continue  # skip unknown roles

                    messages.append({
                        "role": role,
                        "parts": msg["content"]
                    })
            
            # Add current user message
            messages.append({
                "role": "user",
                "parts": user_message
            })
            
            # Start conversation and stream
            chat = model.start_chat(history=messages)
            response = chat.send_message(user_message)
            
            yield response.text
            
            logger.info(f"Chatbot response completed for query: {user_message[:50]}...")
        
        except Exception as e:
            print("🔥 GEMINI ERROR:", str(e))
            logger.error(f"Chatbot streaming error: {e}")
            yield f"ERROR: {str(e)}"
    
    @staticmethod
    def get_quick_response(question: str, model=None) -> str:
        """
        Get non-streaming response for FAQ or quick answers.
        """
        if not model:
            return "Service unavailable."
        
        try:
            response = model.generate_content(question)
            return response.text if response else "No response generated."
        except Exception as e:
            print("🔥 GEMINI ERROR:", str(e))
            logger.error(f"Chatbot quick response error: {e}")
            return "Error generating response."
    
    @staticmethod
    def handle_emergency_query(user_message: str) -> bool:
        """
        Detect if user is reporting emergency symptoms.
        """
        emergency_keywords = [
            "emergency", "acute", "severe chest pain", "unable to breathe",
            "unconscious", "bleeding heavily", "loss of consciousness",
            "stroke", "heart attack", "overdose", "poisoning", "suicide",
        ]
        
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in emergency_keywords)
    
    @staticmethod
    def emergency_response(user_message: str) -> str:
        """
        Provide emergency guidance.
        """
        return """EMERGENCY ALERT 🚨

If you are experiencing a medical emergency, STOP and:

1. **CALL 911 (or your local emergency number) IMMEDIATELY**
2. **Do not delay** - get to a hospital emergency room

Do NOT rely on this chat for emergency situations.

If you need urgent hospital assistance:
- **Hospital ER Number**: +91-XXX-XXXX-XXXX
- **Ambulance**: 911 or local emergency number

Please seek immediate professional medical help."""

def get_chatbot_model(app):
    api_key = app.config.get("GEMINI_API_KEY")
    model_name = app.config.get("GEMINI_MODEL")

    print("🔑 API KEY:", api_key)
    print("🤖 MODEL:", model_name)

    if not api_key:
        logger.warning("GEMINI_API_KEY not configured")
        return None

    if not model_name:
        model_name = "gemini-1.5-flash-latest"  # fallback

    return ChatbotService.initialize(api_key, model_name)