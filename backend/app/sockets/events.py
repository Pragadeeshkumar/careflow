from flask_socketio import emit, join_room, leave_room, rooms
from flask import request
from app.extensions import socketio
from flask_jwt_extended import decode_token
from app.models import User, UserRole, QueueToken
from app.services.queue_engine import QueueEngine
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Track connected users
connected_users = {}  # {user_id: socket_id}


@socketio.on("connect")
def handle_connect(auth):
    """
    Client connects with JWT token.
    auth = {"token": "<jwt>"}
    """
    try:
        if not auth or not auth.get("token"):
            return False
        
        # Decode JWT
        token = auth.get("token")
        decoded = decode_token(token)
        user_id = decoded["sub"]
        
        connected_users[user_id] = {"socket_id": request.sid}
        
        logger.info(f"User connected: {user_id}")
        emit("connection_response", {"message": "Connected", "user_id": user_id})
        
        return True
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False


@socketio.on("disconnect")
def handle_disconnect():
    """User disconnects."""
    # Find and remove user
    for user_id, data in list(connected_users.items()):
        if data["socket_id"] == request.sid:
            del connected_users[user_id]
            logger.info(f"User disconnected: {user_id}")
            break


@socketio.on("join_room")
def on_join_room(data):
    """
    Join a socket.io room.
    data = {"room": "queue", "role": "doctor"}
    """
    room = data.get("room", "queue")
    join_room(room)
    
    logger.info(f"User joined room: {room}")
    emit("room_joined", {"room": room})


@socketio.on("leave_room")
def on_leave_room(data):
    """Leave a socket.io room."""
    room = data.get("room")
    if room:
        leave_room(room)
        logger.info(f"User left room: {room}")


@socketio.on("subscribe_queue")
def on_subscribe_queue(data):
    """
    Subscribe to queue updates.
    Patients subscribe to their own appointment queue.
    Doctors/receptionists subscribe to the general queue.
    """
    appointment_id = data.get("appointment_id")
    user_role = data.get("role")
    
    if appointment_id:
        # Patient: subscribe to their specific appointment/queue position
        room = f"appointment:{appointment_id}"
        join_room(room)
        
        # Send current position
        position = QueueEngine.get_position(appointment_id)
        emit("queue_position_update", {
            "appointment_id": appointment_id,
            "position": position,
            "message": f"You are #{position} in the queue",
        })
        
        logger.info(f"Subscribed to appointment queue: {appointment_id}")
    
    elif user_role in ["doctor", "receptionist"]:
        # Doctor/receptionist: subscribe to all queue updates
        join_room("queue_view")
        
        # Send current full queue
        all_queued = QueueEngine.get_all_queued(limit=50)
        emit("full_queue_update", {
            "queue": all_queued,
            "total": len(all_queued),
        })
        
        logger.info(f"Subscribed to queue view: {user_role}")


@socketio.on("get_queue_position")
def on_get_queue_position(data):
    """
    Real-time query: get current queue position.
    """
    appointment_id = data.get("appointment_id")
    
    if not appointment_id:
        emit("error", {"message": "appointment_id required"})
        return
    
    position = QueueEngine.get_position(appointment_id)
    people_ahead = QueueEngine.get_queue_ahead(appointment_id)
    
    emit("queue_position_update", {
        "appointment_id": appointment_id,
        "position": position,
        "people_ahead": people_ahead,
    })


@socketio.on("request_full_queue")
def on_request_full_queue():
    """Doctor/receptionist requests full queue state."""
    all_queued = QueueEngine.get_all_queued(limit=50)
    
    emit("full_queue_update", {
        "queue": all_queued,
        "total": len(all_queued),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ──────────────────────────────────────────────────────────────
# Broadcast functions (called from routes via socketio.emit)
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
# FIXED Broadcast functions (NO broadcast=True)
# ──────────────────────────────────────────────────────────────

def broadcast_queue_update():
    all_queued = QueueEngine.get_all_queued(limit=50)

    socketio.emit("queue_state_changed", {
        "queue": all_queued,
        "total": len(all_queued),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, room="queue_view")


def broadcast_position_update(appointment_id: str, position: int):
    socketio.emit("queue_position_update", {
        "appointment_id": appointment_id,
        "position": position,
    }, room=f"appointment:{appointment_id}")


def broadcast_patient_called(appointment_id: str, token_number: int, patient_name: str):
    # Patient notification
    socketio.emit("you_are_called", {
        "appointment_id": appointment_id,
        "token_number": token_number,
        "message": f"Token #{token_number} - Please proceed to the doctor",
    }, room=f"appointment:{appointment_id}")

    # Compatibility event
    socketio.emit("patient_called", {
        "appointment_id": appointment_id,
        "token_number": token_number,
        "message": f"Token #{token_number} - Please proceed to the doctor",
    }, room=f"appointment:{appointment_id}")

    # Doctor dashboard
    socketio.emit("patient_called", {
        "appointment_id": appointment_id,
        "token_number": token_number,
        "patient_name": patient_name,
    }, room="queue_view")


def broadcast_geofence_warning(appointment_id: str):
    socketio.emit("geofence_warning", {
        "appointment_id": appointment_id,
        "message": "You have left the hospital geofence while your turn is close.",
    }, room=f"appointment:{appointment_id}")


def broadcast_appointment_completed(appointment_id: str):
    socketio.emit("appointment_completed", {
        "appointment_id": appointment_id,
    })


def broadcast_appointment_cancelled(appointment_id: str):
    socketio.emit("appointment_cancelled", {
        "appointment_id": appointment_id,
    })


def broadcast_token_issued(appointment_id: str, token_number: int, position: int):
    socketio.emit("token_issued_to_you", {
        "appointment_id": appointment_id,
        "token_number": token_number,
        "position": position,
    }, room=f"appointment:{appointment_id}")

    socketio.emit("new_token_in_queue", {
        "appointment_id": appointment_id,
        "token_number": token_number,
        "position": position,
    }, room="queue_view")