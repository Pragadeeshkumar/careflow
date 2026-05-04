from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timezone, date, time
from app.extensions import db
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.models.queue_token import QueueToken, TokenStatus
from app.models.payment import Payment
from app.services.queue_engine import QueueEngine
from app.services.geofence_service import GeofenceService
from app.routes.auth import role_required
from app.services.notification_service import NotificationService
from app.extensions import redis_conn
from app.sockets.events import broadcast_geofence_warning
import json
import logging

logger = logging.getLogger(__name__)

patient_bp = Blueprint("patient", __name__)


@patient_bp.route("/book", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def book_appointment():
    """
    Create a new appointment booking.
    
    JSON body:
    {
        "doctor_id": "doc-uuid",
        "scheduled_date": "2026-05-10",
        "scheduled_time": "14:30",
        "symptoms": "Chest pain and shortness of breath"
    }
    """
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    # Validate required fields
    if not data.get("doctor_id") or not data.get("scheduled_date") or not data.get("scheduled_time"):
        return jsonify({"error": "doctor_id, scheduled_date, scheduled_time required"}), 400
    
    # Verify doctor exists
    doctor = User.query.filter_by(id=data["doctor_id"], role=UserRole.DOCTOR).first()
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    
    # Parse date and time
    try:
        scheduled_date = datetime.fromisoformat(data["scheduled_date"]).date()
        scheduled_time = datetime.fromisoformat(f"1970-01-01T{data['scheduled_time']}").time()
    except ValueError:
        return jsonify({"error": "Invalid date/time format. Use ISO format (YYYY-MM-DD, HH:MM)"}), 400
    
    # Create appointment
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=data["doctor_id"],
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        symptoms=data.get("symptoms"),
        status=AppointmentStatus.PENDING_PAYMENT,
    )
    
    db.session.add(appointment)
    db.session.commit()
    
    logger.info(f"Appointment created: {appointment.id} for patient {patient_id}")
    
    # Create payment record
    payment = Payment(
        patient_id=patient_id,
        appointment_id=appointment.id,
        amount=appointment.booking_fee,
        currency="INR",
    )
    db.session.add(payment)
    db.session.commit()
    
    return jsonify({
        "message": "Appointment created. Proceed to payment.",
        "appointment": appointment.to_dict(),
        "payment": payment.to_dict(),
    }), 201


@patient_bp.route("/appointments/<appointment_id>", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_appointment(appointment_id):
    """Get appointment details."""
    patient_id = get_jwt_identity()
    
    appointment = Appointment.query.filter_by(id=appointment_id, patient_id=patient_id).first()
    if not appointment:
        return jsonify({"error": "Appointment not found"}), 404
    
    result = appointment.to_dict()
    
    # Add queue position if in queue
    if appointment.queue_token:
        position = QueueEngine.get_position(appointment.id)
        result["queue_position"] = position
        result["queue_status"] = appointment.queue_token.status
    
    return jsonify(result), 200


@patient_bp.route("/queue/status", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_queue_status():
    """Get patient's current queue position and status."""
    patient_id = get_jwt_identity()
    
    logger.info(f"Queue status requested by patient {patient_id}")
    
    # Get active queue token
    queue_token = QueueToken.query.filter_by(
        patient_id=patient_id,
        status=TokenStatus.WAITING
    ).first()
    
    if not queue_token:
        all_tokens = QueueToken.query.filter_by(patient_id=patient_id).all()
        logger.info(f"No waiting token for patient {patient_id}. All tokens: {[(t.id, t.status) for t in all_tokens]}")
        return jsonify({
            "in_queue": False,
            "message": "Not currently in queue"
        }), 200
    
    logger.info(f"Queue token found for patient {patient_id}: {queue_token.token_number}")
    
    try:
        position = QueueEngine.get_position(queue_token.appointment_id)
        people_ahead = QueueEngine.get_queue_ahead(queue_token.appointment_id)
    except Exception as e:
        logger.warning(f"Queue engine error (likely Redis): {e}. Using fallback values.")
        position = queue_token.token_number
        people_ahead = 0
    
    # Get appointment details
    appointment = queue_token.appointment
    
    # Build doctor info safely
    doctor_info = None
    if appointment.doctor:
        doctor_info = {
            "id": appointment.doctor.id,
            "name": appointment.doctor.full_name,
            "specialisation": appointment.doctor.specialisation,
        }
    
    logger.info(f"Returning queue status for patient {patient_id}: token#{queue_token.token_number}, position={position}")
    
    return jsonify({
        "in_queue": True,
        "token_number": queue_token.token_number,
        "position": position,
        "people_ahead": people_ahead,
        "status": queue_token.status,
        "doctor": doctor_info,
        "queue_token": queue_token.to_dict(position=position),
    }), 200


@patient_bp.route("/history", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def history():
    """Get all appointments for current patient."""
    patient_id = get_jwt_identity()
    
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(
        Appointment.created_at.desc()
    ).limit(50).all()
    
    result = []
    for apt in appointments:
        apt_dict = apt.to_dict()
        
        # Add queue info if applicable
        if apt.queue_token:
            position = QueueEngine.get_position(apt.id)
            apt_dict["queue_position"] = position
        
        result.append(apt_dict)
    
    return jsonify({
        "total": len(result),
        "appointments": result,
    }), 200


@patient_bp.route("/profile", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_profile():
    """Get patient profile."""
    patient_id = get_jwt_identity()
    user = User.query.get(patient_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify(user.to_dict()), 200


@patient_bp.route("/profile", methods=["PUT"])
@jwt_required()
@role_required(UserRole.PATIENT)
def update_profile():
    """Update patient profile."""
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    user = User.query.get(patient_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Allowed fields
    if "full_name" in data:
        user.full_name = data["full_name"]
    if "phone" in data:
        existing = User.query.filter_by(phone=data["phone"]).first()
        if existing and existing.id != patient_id:
            return jsonify({"error": "Phone already in use"}), 409
        user.phone = data["phone"]
    if "blood_group" in data:
        user.blood_group = data["blood_group"]
    if "date_of_birth" in data:
        user.date_of_birth = data["date_of_birth"]
    if "fcm_token" in data:
        user.fcm_token = data["fcm_token"]
    
    db.session.commit()
    
    logger.info(f"Patient profile updated: {patient_id}")
    
    return jsonify({
        "message": "Profile updated",
        "user": user.to_dict()
    }), 200


@patient_bp.route("/location", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def update_location():
    """
    Update patient's GPS location (called by mobile app periodically).
    
    JSON body:
    {
        "latitude": 19.0760,
        "longitude": 72.8777
    }
    """
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    
    if not data.get("latitude") or not data.get("longitude"):
        return jsonify({"error": "latitude and longitude required"}), 400
    
    user = User.query.get(patient_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.last_lat = data["latitude"]
    user.last_lng = data["longitude"]
    user.last_location_at = datetime.now(timezone.utc)
    
    db.session.commit()
    
    # Check geofence and trigger notification if needed
    from app.services.geofence_service import GeofenceService
    from app.services.notification_service import NotificationService
    
    queue_token = QueueToken.query.filter_by(
        patient_id=patient_id,
        status=TokenStatus.WAITING
    ).first()
    
    if queue_token:
        position = QueueEngine.get_position(queue_token.appointment_id)
        is_violation, alert_type = GeofenceService.check_geofence_violation(
            patient_id, data["latitude"], data["longitude"], position, queue_token.appointment_id
        )
        
        if is_violation and user.fcm_token:
            NotificationService.on_geofence_alert(patient_id, user.fcm_token)
            broadcast_geofence_warning(queue_token.appointment_id)
    
    return jsonify({"message": "Location updated"}), 200


@patient_bp.route("/health-summary", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_health_summary():
    """Get patient's health summary from past appointments."""
    patient_id = get_jwt_identity()
    
    completed_appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        status=AppointmentStatus.COMPLETED
    ).all()
    
    return jsonify({
        "total_visits": len(completed_appointments),
        "appointments": [apt.to_dict() for apt in completed_appointments[-10:]],
    }), 200


@patient_bp.route("/notifications/preferences", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_notification_preferences():
    """Get current patient's notification preferences."""
    patient_id = get_jwt_identity()
    return jsonify({
        "preferences": NotificationService.get_preferences(patient_id)
    }), 200


@patient_bp.route("/notifications/preferences", methods=["PUT"])
@jwt_required()
@role_required(UserRole.PATIENT)
def update_notification_preferences():
    """Update current patient's notification preferences."""
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    preferences = data.get("preferences", data)

    updated = NotificationService.update_preferences(patient_id, preferences)
    return jsonify({
        "message": "Notification preferences updated",
        "preferences": updated,
    }), 200


@patient_bp.route("/notifications/history", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_notification_history():
    """Get current patient's notification history."""
    patient_id = get_jwt_identity()
    raw_items = redis_conn.lrange(f"notification:history:{patient_id}", 0, 49)

    items = []
    for raw in raw_items:
        try:
            items.append(json.loads(raw))
        except Exception:
            logger.warning("Failed to parse notification history item")

    return jsonify({
        "total": len(items),
        "notifications": items,
        "preferences": NotificationService.get_preferences(patient_id),
    }), 200


@patient_bp.route("/notifications/token", methods=["POST"])
@jwt_required()
@role_required(UserRole.PATIENT)
def register_push_token():
    """Register the patient's device push token for notifications."""
    patient_id = get_jwt_identity()
    data = request.get_json() or {}
    token = data.get("fcm_token")

    if not token:
        return jsonify({"error": "fcm_token required"}), 400

    user = User.query.get(patient_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.fcm_token = token
    db.session.commit()

    return jsonify({"message": "Push token registered"}), 200

@patient_bp.route("/notifications/test", methods=["GET"])
@jwt_required()
def test_notification():
    patient_id = get_jwt_identity()

    NotificationService.record_notification(
        patient_id,
        "test",
        "Test Notification",
        "Your system is working"
    )

    return {"message": "sent"}
@patient_bp.route("/geofence", methods=["GET"])
@jwt_required()
@role_required(UserRole.PATIENT)
def get_geofence_info():
    """Return hospital geofence boundary and the patient's current in-zone status."""
    patient_id = get_jwt_identity()
    user = User.query.get(patient_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    boundary = GeofenceService.get_hospital_boundary()
    current_location = None
    if user.last_lat is not None and user.last_lng is not None:
        current_location = {
            "latitude": user.last_lat,
            "longitude": user.last_lng,
            "within_hospital": GeofenceService.is_within_hospital(user.last_lat, user.last_lng),
        }

    return jsonify({
        "boundary": boundary,
        "current_location": current_location,
    }), 200
