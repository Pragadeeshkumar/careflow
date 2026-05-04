from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import Appointment, User, UserRole
from app.services.triage_service import TriageService, get_triage_model
from app.routes.auth import role_required
import logging

logger = logging.getLogger(__name__)

triage_bp = Blueprint("triage", __name__)
triage_model = None


def init_triage_model(app):
    """Initialize triage model from app context."""
    global triage_model
    triage_model = get_triage_model(app)


@triage_bp.route("/analyze", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def analyze_symptoms():
    """
    Analyze patient symptoms and get priority score.
    This is called during appointment booking to determine queue priority.
    
    JSON body:
    {
        "appointment_id": "apt-uuid",
        "symptoms": "Chest pain and shortness of breath"
    }
    """
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    if not data.get("symptoms"):
        return jsonify({"error": "symptoms required"}), 400
    
    appointment_id = data.get("appointment_id")
    
    # If appointment_id provided, verify it belongs to patient
    if appointment_id:
        apt = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
        if not apt:
            return jsonify({"error": "Appointment not found"}), 404
    else:
        apt = None
    
    # Analyze symptoms
    triage_result = TriageService.analyze_symptoms(data["symptoms"], triage_model)
    
    # Save to appointment if provided
    if apt:
        TriageService.save_triage_result(appointment_id, triage_result)
    
    logger.info(f"Triage analysis: patient {patient_id} score={triage_result['priority_score']}")
    
    return jsonify({
        "analysis": triage_result,
        "appointment_id": appointment_id,
    }), 200


@triage_bp.route("/symptoms-guide", methods=["GET"])
def get_symptoms_guide():
    """Get guidance on common symptoms (public endpoint)."""
    return jsonify({
        "emergency_symptoms": [
            "Severe chest pain or pressure",
            "Difficulty breathing or shortness of breath",
            "Sudden severe headache",
            "Weakness or numbness",
            "Loss of consciousness",
            "Severe bleeding",
            "Signs of stroke",
        ],
        "high_priority": [
            "Severe abdominal pain",
            "High fever (>101°F)",
            "Severe allergic reaction",
            "Broken bones or severe injuries",
        ],
        "message": "If you experience emergency symptoms, please call 911 or go to the ER immediately.",
    }), 200


@triage_bp.route("/previous-scores/<patient_id>", methods=["GET"])
@jwt_required()
def get_previous_scores(patient_id):
    """Get patient's previous triage scores (for doctor reference)."""
    requesting_user = get_jwt_identity()
    
    # Only allow doctors/receptionists or the patient themselves
    user = User.query.get(requesting_user)
    if user.role == UserRole.PATIENT and requesting_user != patient_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get completed appointments with triage scores
    appointments = Appointment.query.filter_by(patient_id=patient_id).filter(
        Appointment.triage_score > 0
    ).order_by(Appointment.created_at.desc()).limit(20).all()
    
    return jsonify({
        "total": len(appointments),
        "appointments": [
            {
                "appointment_id": apt.id,
                "triage_score": apt.triage_score,
                "triage_summary": apt.triage_summary,
                "symptoms": apt.symptoms,
                "date": apt.created_at.isoformat(),
            }
            for apt in appointments
        ],
    }), 200
