from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timezone
from app.extensions import db, socketio
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.models.queue_token import QueueToken, TokenStatus
from app.services.queue_engine import QueueEngine
from app.services.notification_service import NotificationService
from app.routes.auth import role_required
from app.sockets.events import broadcast_patient_called, broadcast_appointment_completed, broadcast_queue_update
import logging

logger = logging.getLogger(__name__)

doctor_bp = Blueprint("doctor", __name__)


@doctor_bp.route("/queue", methods=["GET"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def view_queue():
    """Get current queue state (both priority and linear)."""
    all_queued = QueueEngine.get_all_queued(limit=100)
    
    # Enrich with appointment and patient details
    enriched = []
    for item in all_queued:
        appointment_id = item["appointment_id"]
        apt = Appointment.query.get(appointment_id)
        token = apt.queue_token if apt and apt.queue_token else None
        
        if apt and token:
            enriched.append({
                "appointment_id": apt.id,
                "position": item["position"],
                "token_number": token.token_number,
                "patient": {
                    "id": apt.patient.id,
                    "name": apt.patient.full_name,
                    "phone": apt.patient.phone,
                },
                "symptoms": apt.symptoms,
                "triage_score": apt.triage_score,
                "is_priority": item["is_priority"] == "1",
                "queue_token": token.to_dict(position=item["position"]),
            })
    
    return jsonify({
        "total_queued": len(enriched),
        "queue": enriched,
    }), 200


@doctor_bp.route("/call_next", methods=["POST"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def call_next():
    """Call the next patient in the queue."""
    appointment_id = QueueEngine.get_next_patient()
    
    if not appointment_id:
        return jsonify({"message": "Queue is empty"}), 200
    
    apt = Appointment.query.get(appointment_id)
    token = apt.queue_token if apt else None
    
    if not apt or not token:
        return jsonify({"error": "Data inconsistency"}), 500
    
    # Mark as called in queue
    QueueEngine.mark_called(appointment_id)
    
    # Update appointment and token status
    token.status = TokenStatus.CALLED
    token.called_at = datetime.now(timezone.utc)
    apt.status = AppointmentStatus.IN_PROGRESS
    db.session.commit()
    
    # Send notification to patient
    if apt.patient.fcm_token:
        NotificationService.on_called(apt.patient.id, token.token_number, apt.patient.fcm_token)

    logger.info(f"Doctor called token #{token.token_number} for appointment {appointment_id}")

    # Broadcast via WebSocket to the specific appointment room and queue viewers
    broadcast_patient_called(appointment_id, token.token_number, apt.patient.full_name)
    broadcast_queue_update()

    return jsonify({
        "message": "Patient called",
        "token_number": token.token_number,
        "patient": apt.patient.to_dict(),
    }), 200


@doctor_bp.route("/complete/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def complete_appointment(appointment_id):
    """Mark appointment as completed."""
    doctor_id = get_jwt_identity()
    data = request.get_json() or {}
    
    apt = Appointment.query.get(appointment_id)
    token = apt.queue_token if apt else None
    
    if not apt or not token:
        return jsonify({"error": "Appointment not found"}), 404
    
    # Optional: check if the calling doctor is the assigned doctor
    # if apt.doctor_id and apt.doctor_id != doctor_id:
    #     return jsonify({"error": "Not your appointment"}), 403
    
    # Mark as completed
    QueueEngine.mark_completed(appointment_id)
    
    apt.status = AppointmentStatus.COMPLETED
    apt.notes = data.get("notes", "")
    apt.doctor_id = doctor_id  # Assign doctor if not assigned
    token.status = TokenStatus.COMPLETED
    token.completed_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    logger.info(f"Appointment completed: {appointment_id} by doctor {doctor_id}")
    
    # Broadcast via WebSocket
    broadcast_appointment_completed(appointment_id)
    broadcast_queue_update()
    
    return jsonify({
        "message": "Appointment completed",
        "appointment": apt.to_dict(),
    }), 200


@doctor_bp.route("/escalate/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def escalate_to_priority(appointment_id):
    """Escalate patient to priority queue (emergency case)."""
    data = request.get_json() or {}
    
    apt = Appointment.query.get(appointment_id)
    token = apt.queue_token if apt else None
    
    if not apt or not token:
        return jsonify({"error": "Appointment not found"}), 404
    
    if token.status != TokenStatus.WAITING:
        return jsonify({"error": "Can only escalate waiting patients"}), 400
    
    # Set high priority score
    token.queue_type = "priority"
    token.priority_score = 100  # Highest priority (will be negative in Redis)
    
    db.session.commit()

    # Move the patient from their current Redis queue into priority.
    QueueEngine.cancel_token(appointment_id)
    QueueEngine.enqueue_patient(appointment_id, apt.patient_id, is_priority=True, priority_score=100)
    
    logger.info(f"Appointment escalated to priority: {appointment_id}")
    
    return jsonify({
        "message": "Patient escalated to priority queue",
        "queue_type": "priority",
    }), 200


@doctor_bp.route("/profile", methods=["GET"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def get_profile():
    """Get doctor profile."""
    doctor_id = get_jwt_identity()
    user = User.query.get(doctor_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify(user.to_dict()), 200


@doctor_bp.route("/patients/<doctor_id>", methods=["GET"])
@jwt_required()
@role_required(UserRole.DOCTOR)
def get_doctor_patients(doctor_id):
    """Get all patients assigned to this doctor."""
    doctor_id_requesting = get_jwt_identity()
    
    # Can only view own patients or if admin
    if doctor_id != doctor_id_requesting:
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Can only view your own patients"}), 403
    
    # Get completed appointments
    appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        status=AppointmentStatus.COMPLETED
    ).order_by(Appointment.updated_at.desc()).limit(50).all()
    
    return jsonify({
        "total": len(appointments),
        "appointments": [apt.to_dict() for apt in appointments],
    }), 200

@doctor_bp.route("/list", methods=["GET"])
def list_doctors():
    """Public endpoint to list all doctors (for patient booking)."""
    doctors = User.query.filter_by(role=UserRole.DOCTOR).all()

    return jsonify([
        {
            "id": d.id,
            "name": d.full_name,
            "specialisation": d.specialisation,
        }
        for d in doctors
    ]), 200
