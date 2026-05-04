"""
AI Triage Service: Analyze patient symptoms using Gemini/Claude
and assign priority scores for queue placement.
"""

import google.generativeai as genai
from app.extensions import db
from app.models import Appointment
import logging
import re

logger = logging.getLogger(__name__)


class TriageService:
    """Symptom analysis and priority scoring using Gemini AI."""
    
    # Symptom keywords for emergency detection
    EMERGENCY_KEYWORDS = [
        "chest pain", "acute", "severe", "emergency", "critical",
        "unable to breathe", "unconscious", "bleeding", "trauma",
        "fever 103", "loss of consciousness", "stroke", "heart attack",
        "seizure", "poisoning", "overdose", "severe allergic",
    ]
    
    @staticmethod
    def initialize(api_key: str, model_name: str = "gemini-1.5-flash"):
        """Initialize Gemini API."""
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model_name)
    
    @staticmethod
    def analyze_symptoms(symptoms_text: str, model=None) -> dict:
        """
        Analyze patient symptoms and return priority score + summary.
        
        Returns:
        {
            "priority_score": 0-10,  # 0=normal, 10=emergency
            "summary": "Clinical summary",
            "recommendation": "Next steps",
            "emergency": bool,
        }
        """
        if not symptoms_text or len(symptoms_text.strip()) < 5:
            return {
                "priority_score": 0,
                "summary": "No symptoms provided",
                "recommendation": "General checkup",
                "emergency": False,
            }
        
        # Quick check for emergency keywords
        emergency_detected = TriageService._check_emergency_keywords(symptoms_text)
        if emergency_detected:
            return {
                "priority_score": 10,
                "summary": f"EMERGENCY DETECTED: {emergency_detected}",
                "recommendation": "Immediate doctor consultation required",
                "emergency": True,
            }
        
        # Use Gemini for detailed analysis
        try:
            if not model:
                return TriageService._analyze_without_ai(symptoms_text)
            
            response = model.generate_content(TriageService._build_triage_prompt(symptoms_text))
            
            if not response or not response.text:
                return TriageService._analyze_without_ai(symptoms_text)
            
            # Parse response
            return TriageService._parse_ai_response(response.text)
        
        except Exception as e:
            logger.error(f"Triage analysis error: {e}")
            return TriageService._analyze_without_ai(symptoms_text)
    
    @staticmethod
    def _check_emergency_keywords(text: str) -> str:
        """Check if symptoms contain emergency keywords."""
        text_lower = text.lower()
        for keyword in TriageService.EMERGENCY_KEYWORDS:
            if keyword in text_lower:
                return keyword
        return None
    
    @staticmethod
    def _build_triage_prompt(symptoms: str) -> str:
        """Build Gemini prompt for triage analysis."""
        return f"""You are a medical triage AI assistant. Analyze the following patient symptoms and provide:
1. Priority Score (0-10, where 0 is routine checkup and 10 is life-threatening emergency)
2. Brief clinical summary (1-2 sentences)
3. Recommendation for next steps

Patient Symptoms:
{symptoms}

IMPORTANT: Respond ONLY with JSON format like this (no markdown, no extra text):
{{
    "priority_score": <number 0-10>,
    "summary": "<clinical summary>",
    "recommendation": "<next steps>",
    "emergency": <true/false>
}}

Be conservative: If unsure, err on the side of higher priority."""
    
    @staticmethod
    def _parse_ai_response(response_text: str) -> dict:
        """Parse Gemini response JSON."""
        try:
            # Extract JSON from response
            import json
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                return TriageService._analyze_without_ai("")
            
            parsed = json.loads(json_match.group())
            
            # Validate and constrain values
            priority = max(0, min(10, int(parsed.get("priority_score", 0))))
            summary = parsed.get("summary", "").strip()[:200]
            recommendation = parsed.get("recommendation", "").strip()[:200]
            emergency = parsed.get("emergency", False) or priority >= 8
            
            return {
                "priority_score": priority,
                "summary": summary,
                "recommendation": recommendation,
                "emergency": emergency,
            }
        
        except Exception as e:
            logger.error(f"Parse response error: {e}")
            return TriageService._analyze_without_ai("")
    
    @staticmethod
    def _analyze_without_ai(symptoms: str) -> dict:
        """Fallback analysis without Gemini."""
        # Simple keyword-based scoring
        text_lower = symptoms.lower() if symptoms else ""
        
        score = 1  # base score
        
        # Increment score based on keywords
        urgent_keywords = ["severe", "acute", "emergency", "urgent", "critical", "worse"]
        moderate_keywords = ["pain", "fever", "discomfort", "difficulty", "problem"]
        
        if any(k in text_lower for k in urgent_keywords):
            score = min(8, score + 4)
        elif any(k in text_lower for k in moderate_keywords):
            score = min(6, score + 2)
        
        return {
            "priority_score": score,
            "summary": f"Patient reported: {symptoms[:100]}...",
            "recommendation": "Consultation with doctor recommended",
            "emergency": score >= 8,
        }
    
    @staticmethod
    def save_triage_result(appointment_id: str, triage_result: dict):
        """Save triage analysis to appointment record."""
        appointment = Appointment.query.get(appointment_id)
        if not appointment:
            logger.error(f"Appointment not found: {appointment_id}")
            return False
        
        appointment.triage_score = triage_result.get("priority_score", 0)
        appointment.triage_summary = triage_result.get("summary", "")
        
        db.session.commit()
        
        logger.info(f"Triage saved: appointment {appointment_id} score={triage_result['priority_score']}")
        return True


def get_triage_model(app):
    """Get initialized Gemini model from app config."""
    api_key = app.config.get("GEMINI_API_KEY")
    model_name = app.config.get("GEMINI_MODEL", "gemini-1.5-flash")
    
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured, will use fallback analysis")
        return None
    
    return TriageService.initialize(api_key, model_name)
