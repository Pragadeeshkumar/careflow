import requests
import json
from datetime import datetime, timezone
from typing import Optional
from app.extensions import redis_conn
import logging

logger = logging.getLogger(__name__)

COUNTDOWN_POSITIONS = [4, 3, 2, 1]  # Notify when approaching these positions


class NotificationService:
    """Firebase Cloud Messaging (FCM) push notification handler."""

    DEFAULT_PREFERENCES = {
        "countdown": True,
        "called": True,
        "geofence": True,
        "payment": True,
        "reminder": True,
    }

    @staticmethod
    def get_preferences(patient_id: str) -> dict:
        """Return notification preferences stored in Redis."""
        saved = redis_conn.hgetall(f"notification:prefs:{patient_id}")
        preferences = NotificationService.DEFAULT_PREFERENCES.copy()

        for name in preferences:
            if name in saved:
                preferences[name] = str(saved[name]).lower() in ["1", "true", "yes", "on"]

        return preferences

    @staticmethod
    def update_preferences(patient_id: str, preferences: dict) -> dict:
        """Persist supported notification preferences."""
        current = NotificationService.get_preferences(patient_id)

        for name in current:
            if name in preferences:
                current[name] = bool(preferences[name])

        redis_conn.hset(
            f"notification:prefs:{patient_id}",
            mapping={name: "1" if enabled else "0" for name, enabled in current.items()},
        )
        return current

    @staticmethod
    def is_enabled(patient_id: str, notification_type: str) -> bool:
        return NotificationService.get_preferences(patient_id).get(notification_type, True)

    @staticmethod
    def record_notification(
        patient_id: str,
        notification_type: str,
        title: str,
        body: str,
        status: str = "sent",
        data: dict = None,
    ):
        """Store notification history for the patient app."""
        item = {
            "type": notification_type,
            "title": title,
            "body": body,
            "status": status,
            "data": data or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        key = f"notification:history:{patient_id}"
        redis_conn.lpush(key, json.dumps(item))
        redis_conn.ltrim(key, 0, 99)
        redis_conn.expire(key, 86400 * 30)
    
    @staticmethod
    def send_push_notification(token: str, title: str, body: str, data: dict = None):
        if not token:
            return False

        payload = {
            "to": token,
            "title": title,
            "body": body,
            "data": data or {}
        }

        try:
            res = requests.post(
                "https://exp.host/--/api/v2/push/send",
                json=payload
            )
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Push error: {e}")
            return False
    
    @staticmethod
    def on_countdown_position(appointment_id: str, patient_id: str, position: int, fcm_token: str):
        """
        Triggered when patient's queue position reaches 4, 3, 2, or 1.
        """
        if position not in COUNTDOWN_POSITIONS:
            return

        if not NotificationService.is_enabled(patient_id, "countdown"):
            return
        
        # Check if we already sent this notification
        notification_key = f"notif:{appointment_id}:position:{position}"
        if redis_conn.exists(notification_key):
            return  # Already sent
        
        title = "You're almost up!"
        body = f"You are #{position} in the queue. Get ready!"
        
        data = {
            "type": "countdown",
            "appointment_id": appointment_id,
            "position": str(position),
        }
        
        success = NotificationService.send_push_notification(
            fcm_token, title, body, data
        )
        
        if success:
            # Mark as sent (expire after 24h)
            redis_conn.setex(notification_key, 86400, "1")
            NotificationService.record_notification(patient_id, "countdown", title, body, data=data)
    
    @staticmethod
    def on_called(patient_id: str, token_number: int, fcm_token: str):
        """
        Sent when doctor calls this patient's token number.
        """
        if not NotificationService.is_enabled(patient_id, "called"):
            return

        title = f"Token #{token_number} Called!"
        body = "Please proceed to the consultation room."
        
        data = {
            "type": "called",
            "token_number": str(token_number),
        }
        
        NotificationService.send_push_notification(fcm_token, title, body, data)
        NotificationService.record_notification(patient_id, "called", title, body, data=data)
    
    @staticmethod
    def on_geofence_alert(patient_id: str, fcm_token: str):
        """
        Sent when patient leaves the hospital radius while close to their turn.
        """
        if not NotificationService.is_enabled(patient_id, "geofence"):
            return

        title = "Don't Leave!"
        body = "You'll lose your place in the queue if you leave the hospital area."
        
        data = {
            "type": "geofence_warning",
        }
        
        NotificationService.send_push_notification(fcm_token, title, body, data)
        NotificationService.record_notification(patient_id, "geofence", title, body, data=data)
    
    @staticmethod
    def on_appointment_reminder(patient_id: str, appointment_id: str, fcm_token: str, minutes_until: int = 30):
        """
        Sent 30 minutes before scheduled appointment time.
        """
        if not NotificationService.is_enabled(patient_id, "reminder"):
            return

        title = "Appointment Reminder"
        body = f"Your appointment is in {minutes_until} minutes. Please check in at reception."
        
        data = {
            "type": "appointment_reminder",
            "appointment_id": appointment_id,
            "minutes_until": str(minutes_until),
        }
        
        NotificationService.send_push_notification(fcm_token, title, body, data)
        NotificationService.record_notification(patient_id, "reminder", title, body, data=data)
    
    @staticmethod
    def on_payment_confirmation(patient_id: str, appointment_id: str, fcm_token: str, amount: float):
        """
        Sent after payment is confirmed.
        """
        if not NotificationService.is_enabled(patient_id, "payment"):
            return

        title = "Payment Confirmed"
        body = f"Your booking fee of ₹{amount} has been received. You are now in the queue."
        
        data = {
            "type": "payment_confirmation",
            "appointment_id": appointment_id,
            "amount": str(amount),
        }
        
        NotificationService.send_push_notification(fcm_token, title, body, data)
        NotificationService.record_notification(patient_id, "payment", title, body, data=data)
    
    @staticmethod
    def log_notification(patient_id: str, notification_type: str, status: str):
        """Log notifications sent to Redis for analytics."""
        key = f"notifications:{patient_id}:{notification_type}"
        redis_conn.incr(key)
        redis_conn.expire(key, 86400 * 30)  # 30 days retention
