from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import date, datetime, timezone
from app.extensions import db, socketio
from app.models.user import User, UserRole
from app.models.appointment import Appointment, AppointmentStatus
from app.models.queue_token import QueueToken, QueueType, TokenStatus
from app.services.queue_engine import QueueEngine
from app.routes.auth import role_required
import logging

logger = logging.getLogger(__name__)

queue_bp = Blueprint("queue", __name__)


@queue_bp.route("/status/<appointment_id>", methods=["GET"])
@jwt_required()
def get_queue_status(appointment_id):
    """Get queue position and status for an appointment."""
    user_id = get_jwt_identity()
    
    # Get appointment and verify access
    apt = Appointment.query.get(appointment_id)
    if not apt:
        return jsonify({"error": "Appointment not found"}), 404
    
    user = User.query.get(user_id)
    
    # Patients can only view their own appointments
    if user.role == UserRole.PATIENT and apt.patient_id != user_id:
        return jsonify({"error": "Unauthorized"}), 403
    
    if not apt.queue_token:
        return jsonify({
            "in_queue": False,
            "message": "No queue token issued yet",
        }), 200
    
    position = QueueEngine.get_position(appointment_id)
    people_ahead = QueueEngine.get_queue_ahead(appointment_id)
    
    return jsonify({
        "in_queue": True,
        "appointment_id": appointment_id,
        "token_number": apt.queue_token.token_number,
        "position": position,
        "people_ahead": people_ahead,
        "status": apt.queue_token.status,
        "queue_type": apt.queue_token.queue_type,
        "issued_at": apt.queue_token.issued_at.isoformat(),
    }), 200


@queue_bp.route("/state", methods=["GET"])
@jwt_required()
def get_queue_state():
    """Get full queue state (doctor/receptionist only)."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role not in [UserRole.DOCTOR, UserRole.RECEPTIONIST]:
        return jsonify({"error": "Doctors and receptionists only"}), 403
    
    all_queued = QueueEngine.get_all_queued(limit=100)
    
    return jsonify({
        "total_queued": len(all_queued),
        "queue": all_queued,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@queue_bp.route("/today", methods=["GET"])
@jwt_required()
def get_today_queue():
    """Get today's queue (all tokens issued today)."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role not in [UserRole.DOCTOR, UserRole.RECEPTIONIST]:
        return jsonify({"error": "Doctors and receptionists only"}), 403
    
    today = date.today()
    tokens = QueueToken.query.filter_by(queue_date=today).order_by(
        QueueToken.token_number.asc()
    ).all()
    
    result = []
    for i, token in enumerate(tokens, 1):
        apt = token.appointment
        result.append({
            "token_number": token.token_number,
            "position": i,
            "patient_name": apt.patient.full_name,
            "patient_phone": apt.patient.phone,
            "doctor_name": apt.doctor.full_name if apt.doctor else "Unassigned",
            "status": token.status,
            "queue_type": token.queue_type,
            "symptoms": apt.symptoms,
            "triage_score": apt.triage_score,
        })
    
    return jsonify({
        "date": str(today),
        "total": len(result),
        "queue": result,
    }), 200


@queue_bp.route("/position/<appointment_id>", methods=["GET"])
@jwt_required()
def get_position(appointment_id):
    """Get current position for an appointment."""
    position = QueueEngine.get_position(appointment_id)
    
    if position == 0:
        return jsonify({
            "position": 0,
            "message": "Appointment not in queue",
        }), 200
    
    apt = Appointment.query.get(appointment_id)
    if not apt or not apt.queue_token:
        return jsonify({"error": "Appointment not found"}), 404
    
    return jsonify({
        "appointment_id": appointment_id,
        "token_number": apt.queue_token.token_number,
        "position": position,
        "people_ahead": max(0, position - 1),
    }), 200


@queue_bp.route("/stats", methods=["GET"])
def get_queue_stats():
    """Get queue statistics (public endpoint)."""
    from app.extensions import redis_conn
    
    # Try to get cached stats
    cache_key = "queue:stats"
    cached = redis_conn.hgetall(cache_key)
    
    if cached:
        return jsonify({
            "waiting": int(cached.get("waiting", 0)),
            "called": int(cached.get("called", 0)),
            "completed": int(cached.get("completed", 0)),
            "total_active": int(cached.get("waiting", 0)) + int(cached.get("called", 0)),
        }), 200
    
    # Fallback: query database
    waiting = QueueToken.query.filter_by(status=TokenStatus.WAITING).count()
    called = QueueToken.query.filter_by(status=TokenStatus.CALLED).count()
    completed = QueueToken.query.filter_by(status=TokenStatus.COMPLETED).count()
    
    return jsonify({
        "waiting": waiting,
        "called": called,
        "completed": completed,
        "total_active": waiting + called,
    }), 200


@queue_bp.route("/compare-wait", methods=["GET"])
def compare_wait_times():
    """
    Compare estimated wait times.
    Returns average wait time based on completed appointments.
    """
    from sqlalchemy import func, and_
    from datetime import timedelta
    
    # Get average time from token issuance to completion (last 50 completed)
    completed_tokens = QueueToken.query.filter(
        QueueToken.status == TokenStatus.COMPLETED,
        QueueToken.completed_at.isnot(None)
    ).order_by(QueueToken.completed_at.desc()).limit(50).all()
    
    if not completed_tokens:
        return jsonify({
            "estimated_wait_minutes": 15,  # default estimate
            "message": "Not enough data for estimate",
        }), 200
    
    total_wait = 0
    for token in completed_tokens:
        if token.issued_at and token.completed_at:
            wait = (token.completed_at - token.issued_at).total_seconds() / 60
            total_wait += wait
    
    avg_wait = total_wait / len(completed_tokens) if completed_tokens else 15
    
    return jsonify({
        "estimated_wait_minutes": round(avg_wait),
        "samples": len(completed_tokens),
    }), 200
