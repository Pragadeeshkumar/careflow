from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone, date
from app.extensions import db, socketio
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.models.queue_token import QueueToken, TokenStatus, QueueType
from app.models.payment import Payment, PaymentStatus
from app.services.queue_engine import QueueEngine
from app.services.notification_service import NotificationService
from app.routes.auth import role_required
from app.sockets.events import broadcast_token_issued, broadcast_queue_update, broadcast_appointment_cancelled
import logging

logger = logging.getLogger(__name__)

receptionist_bp = Blueprint("receptionist", __name__)


@receptionist_bp.route("/appointments", methods=["GET"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def list_appointments():
    """Get all appointments for a given date."""
    date_str = request.args.get("date", default=str(date.today()))
    status = request.args.get("status")  # optional filter
    
    query = Appointment.query.filter_by(scheduled_date=date_str)
    
    if status:
        query = query.filter_by(status=status)
    
    appointments = query.order_by(Appointment.scheduled_time.asc()).all()
    
    # Enrich with payment and queue info
    result = []
    for apt in appointments:
        apt_dict = apt.to_dict()
        
        if apt.payment:
            apt_dict["payment"] = apt.payment.to_dict()
        
        if apt.queue_token:
            position = QueueEngine.get_position(apt.id)
            apt_dict["queue_position"] = position
        
        result.append(apt_dict)
    
    return jsonify({
        "total": len(result),
        "appointments": result
    }), 200


@receptionist_bp.route("/issue_token/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def issue_queue_token(appointment_id):
    """
    Issue a queue token to a patient (after payment).
    
    JSON body:
    {
        "is_priority": false,  # optional, defaults to false
        "priority_score": 0    # optional, for priority cases
    }
    """
    data = request.get_json() or {}
    
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404
    
    # Check if already has token
    if apt.queue_token:
        return jsonify({"error": "Token already issued"}), 400
    
    # Check if payment is confirmed
    if apt.status not in [AppointmentStatus.CONFIRMED, AppointmentStatus.IN_QUEUE]:
        return jsonify({"error": f"Cannot issue token. Status: {apt.status}"}), 400
    
    # Determine if priority
    is_priority = data.get("is_priority", False)
    priority_score = data.get("priority_score", 0)
    
    # For automatic priority: if triage_score exists and is high
    if apt.triage_score and apt.triage_score >= 7:
        is_priority = True
        priority_score = apt.triage_score
    
    # Get next token number for today
    today = date.today()
    max_token = db.session.query(db.func.max(QueueToken.token_number)).filter_by(
        queue_date=today
    ).scalar() or 0
    next_token_number = max_token + 1
    
    # Create queue token
    queue_type = QueueType.PRIORITY if is_priority else QueueType.LINEAR
    token = QueueToken(
        patient_id=apt.patient_id,
        appointment_id=appointment_id,
        doctor_id=apt.doctor_id,
        token_number=next_token_number,
        queue_date=today,
        queue_type=queue_type,
        status=TokenStatus.WAITING,
        priority_score=priority_score if is_priority else 1000 + next_token_number,
    )
    
    db.session.add(token)
    apt.status = AppointmentStatus.IN_QUEUE
    db.session.commit()
    
    # Add to queue engine
    result = QueueEngine.enqueue_patient(
        appointment_id, apt.patient_id, is_priority, priority_score
    )
    
    # Send notification to patient
    if apt.patient.fcm_token:
        NotificationService.on_payment_confirmation(
            apt.patient_id, appointment_id, apt.patient.fcm_token, float(apt.booking_fee)
        )
    
    logger.info(f"Queue token issued: #{next_token_number} for appointment {appointment_id}")
    
    # Broadcast via WebSocket
    broadcast_token_issued(appointment_id, next_token_number, result["position"])
    broadcast_queue_update()
    
    return jsonify({
        "message": "Queue token issued",
        "token_number": next_token_number,
        "position": result["position"],
        "queue_token": token.to_dict(position=result["position"]),
    }), 201


@receptionist_bp.route("/confirm_payment/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def confirm_payment(appointment_id):
    """Mark payment as confirmed (after cash/manual payment)."""
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404

    if apt.status == AppointmentStatus.COMPLETED:
        return jsonify({"error": "Cannot modify completed appointment"}), 400

    # Update payment status
    if apt.payment:
        apt.payment.status = PaymentStatus.PAID
        apt.payment.paid_at = datetime.now(timezone.utc)
    
    apt.status = AppointmentStatus.CONFIRMED
    db.session.commit()
    
    logger.info(f"Payment confirmed for appointment {appointment_id}")
    
    return jsonify({
        "message": "Payment confirmed. Ready to issue queue token.",
        "appointment": apt.to_dict(),
    }), 200


@receptionist_bp.route("/cancel/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def cancel_appointment(appointment_id):
    """Cancel an appointment and refund if paid."""
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404
    
    if apt.status == AppointmentStatus.COMPLETED:
        return jsonify({"error": "Cannot cancel completed appointment"}), 400
    
    # If has queue token, remove from queue
    if apt.queue_token:
        QueueEngine.cancel_token(appointment_id)
        apt.queue_token.status = TokenStatus.CANCELLED
    
    apt.status = AppointmentStatus.CANCELLED
    
    # Mark payment as refunded if it was paid
    if apt.payment and apt.payment.status == PaymentStatus.PAID:
        apt.payment.status = PaymentStatus.REFUNDED
    
    db.session.commit()
    
    logger.info(f"Appointment cancelled: {appointment_id}")
    
    broadcast_queue_update()
    broadcast_appointment_cancelled(appointment_id)
    
    return jsonify({"message": "Appointment cancelled"}), 200


@receptionist_bp.route("/no_show/<appointment_id>", methods=["POST"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def mark_no_show(appointment_id):
    """Mark patient as no-show (skipped their turn)."""
    apt = Appointment.query.get(appointment_id)
    token = apt.queue_token if apt else None
    
    if not apt or not token:
        return jsonify({"error": "Appointment not found"}), 404
    
    token.status = TokenStatus.SKIPPED
    apt.status = AppointmentStatus.NO_SHOW
    
    # Remove from queue
    QueueEngine.cancel_token(appointment_id)
    
    db.session.commit()
    
    logger.info(f"Patient marked as no-show: {appointment_id}")
    
    broadcast_queue_update()
    broadcast_appointment_cancelled(appointment_id)
    
    return jsonify({"message": "Patient marked as no-show"}), 200


@receptionist_bp.route("/queue/status", methods=["GET"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def get_queue_status():
    """Get current queue status (combined view)."""
    all_queued = QueueEngine.get_all_queued(limit=50)
    
    # Enrich with patient and appointment details
    enriched = []
    for item in all_queued:
        apt = Appointment.query.get(item["appointment_id"])
        if apt:
            enriched.append({
                "position": item["position"],
                "token_number": apt.queue_token.token_number if apt.queue_token else None,
                "patient_name": apt.patient.full_name,
                "patient_phone": apt.patient.phone,
                "doctor_name": apt.doctor.full_name if apt.doctor else "Unassigned",
                "is_priority": item["is_priority"] == "1",
                "status": apt.queue_token.status if apt.queue_token else None,
            })
    
    return jsonify({
        "total_queued": len(enriched),
        "queue": enriched,
    }), 200


@receptionist_bp.route("/appointments/<appointment_id>/details", methods=["GET"])
@jwt_required()
@role_required(UserRole.RECEPTIONIST)
def get_appointment_details(appointment_id):
    """Get detailed appointment info for receptionist."""
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404
    
    result = apt.to_dict()
    result["patient"] = apt.patient.to_dict()
    result["doctor"] = apt.doctor.to_dict() if apt.doctor else None
    result["payment"] = apt.payment.to_dict() if apt.payment else None
    
    if apt.queue_token:
        position = QueueEngine.get_position(apt.id)
        result["queue_token"] = apt.queue_token.to_dict(position=position)
    
    return jsonify(result), 200
