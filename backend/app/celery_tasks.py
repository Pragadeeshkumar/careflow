"""
Celery tasks for background queue and notification management.
Run with: celery -A celery_app worker --loglevel=info
"""

from celery import Celery, Task
from datetime import datetime, timezone, timedelta
from app.models import User, QueueToken, TokenStatus, Appointment
from app.services.queue_engine import QueueEngine
from app.services.geofence_service import GeofenceService
from app.services.notification_service import NotificationService, COUNTDOWN_POSITIONS
from app.extensions import db, redis_conn
from app.sockets.events import broadcast_geofence_warning
import logging

logger = logging.getLogger(__name__)


class FlaskTask(Task):
    def __call__(self, *args, **kwargs):
        from app import create_app
        app = create_app()
        with app.app_context():
            return self.run(*args, **kwargs)

def celery_init_app(app):
    celery = Celery(app.import_name, task_cls=FlaskTask)

    
    celery = Celery(app.import_name, task_cls=FlaskTask)
    celery.conf.update(app.config)
    celery.conf.update(
        broker_url=app.config.get("REDIS_URL", "redis://localhost:6379/0"),
        result_backend=app.config.get("REDIS_URL", "redis://localhost:6379/0"),
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )
    return celery


# ──────────────────────────────────────────────────────────────
# Geofence Monitoring Tasks
# ──────────────────────────────────────────────────────────────

def create_geofence_tasks(celery):
    """Create Celery tasks. Call this after creating the app."""
    
    @celery.task(name="monitor_geofence")
    def monitor_geofence():
        """
        Periodic task (every 30 seconds):
        Check all patients in queue for geofence violations.
        """
        try:
            # Get all waiting queue tokens
            waiting_tokens = QueueToken.query.filter_by(status=TokenStatus.WAITING).all()
            
            for token in waiting_tokens:
                patient = token.patient
                
                # Skip if no location or fcm token
                if not patient.last_lat or not patient.last_lng or not patient.fcm_token:
                    continue
                
                position = QueueEngine.get_position(token.appointment_id)
                
                # Check geofence
                is_violation, alert_type = GeofenceService.check_geofence_violation(
                    patient.id,
                    patient.last_lat,
                    patient.last_lng,
                    position,
                    token.appointment_id
                )
                
                if is_violation:
                    NotificationService.on_geofence_alert(patient.id, patient.fcm_token)
                    broadcast_geofence_warning(token.appointment_id)
                    logger.warning(f"Geofence violation: patient {patient.id}")
            
            logger.info(f"Geofence check completed for {len(waiting_tokens)} patients")
            return {"status": "success", "checked": len(waiting_tokens)}
        
        except Exception as e:
            logger.error(f"Geofence task error: {e}")
            return {"status": "error", "message": str(e)}
    
    
    # ──────────────────────────────────────────────────────────────
    # Queue Position Monitoring Tasks
    # ──────────────────────────────────────────────────────────────
    
    @celery.task(name="check_countdown_notifications")
    def check_countdown_notifications():
        """
        Periodic task (every 15 seconds):
        Check all patients and send countdown notifications when they reach positions 4, 3, 2, 1.
        """
        try:
            waiting_tokens = QueueToken.query.filter_by(status=TokenStatus.WAITING).all()
            notified_count = 0
            
            for token in waiting_tokens:
                patient = token.patient
                
                if not patient.fcm_token:
                    continue
                
                position = QueueEngine.get_position(token.appointment_id)
                
                # Check if at critical positions
                if position in COUNTDOWN_POSITIONS:
                    # Check if we already sent this alert
                    notif_key = f"notif:{token.appointment_id}:position:{position}"
                    
                    if not redis_conn.exists(notif_key):
                        NotificationService.on_countdown_position(
                            token.appointment_id, patient.id, position, patient.fcm_token
                        )
                        token.mark_alert_sent(position)
                        db.session.add(token)
                        notified_count += 1
            
            db.session.commit()
            logger.info(f"Countdown notifications sent to {notified_count} patients")
            return {"status": "success", "notified": notified_count}
        
        except Exception as e:
            logger.error(f"Countdown notification task error: {e}")
            return {"status": "error", "message": str(e)}
    
    
    @celery.task(name="send_appointment_reminders")
    def send_appointment_reminders():
        """
        Periodic task (every 5 minutes):
        Send appointment reminders 30 minutes before scheduled time.
        """
        try:
            now = datetime.now(timezone.utc)
            reminder_time = now + timedelta(minutes=30)
            
            # Get appointments scheduled for the next 30-35 minutes
            upcoming = Appointment.query.filter(
                Appointment.scheduled_time.between(
                    now.time(),
                    reminder_time.time()
                )
            ).all()
            
            reminded_count = 0
            for apt in upcoming:
                if apt.patient.fcm_token:
                    NotificationService.on_appointment_reminder(
                        apt.patient_id, apt.id, apt.patient.fcm_token, minutes_until=30
                    )
                    reminded_count += 1
            
            logger.info(f"Appointment reminders sent to {reminded_count} patients")
            return {"status": "success", "reminded": reminded_count}
        
        except Exception as e:
            logger.error(f"Appointment reminder task error: {e}")
            return {"status": "error", "message": str(e)}
    
    
    @celery.task(name="cleanup_expired_tokens")
    def cleanup_expired_tokens():
        """
        Periodic task (daily at 11:59 PM):
        Clean up old queue tokens from previous day.
        """
        try:
            from datetime import date
            yesterday = date.today()
            
            # Get all tokens from yesterday
            old_tokens = QueueToken.query.filter(
                QueueToken.queue_date < yesterday,
                QueueToken.status.in_([TokenStatus.WAITING, TokenStatus.CALLED])
            ).all()
            
            for token in old_tokens:
                # Mark as expired or remove
                token.status = TokenStatus.CANCELLED
                db.session.add(token)
            
            db.session.commit()
            
            logger.info(f"Cleaned up {len(old_tokens)} expired tokens")
            return {"status": "success", "cleaned": len(old_tokens)}
        
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            return {"status": "error", "message": str(e)}
    
    
    @celery.task(name="sync_queue_to_cache")
    def sync_queue_to_cache():
        """
        Periodic task (every 60 seconds):
        Sync database queue state to Redis cache for performance.
        """
        try:
            # This is mainly for analytics and dashboard caching
            waiting_count = QueueToken.query.filter_by(status=TokenStatus.WAITING).count()
            called_count = QueueToken.query.filter_by(status=TokenStatus.CALLED).count()
            completed_count = QueueToken.query.filter_by(status=TokenStatus.COMPLETED).count()
            
            cache_key = "queue:stats"
            redis_conn.hset(cache_key, mapping={
                "waiting": waiting_count,
                "called": called_count,
                "completed": completed_count,
                "total": waiting_count + called_count,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })
            redis_conn.expire(cache_key, 300)  # 5 min TTL
            
            logger.debug(f"Queue stats synced: {waiting_count} waiting, {called_count} called")
            return {
                "status": "success",
                "waiting": waiting_count,
                "called": called_count,
                "completed": completed_count,
            }
        
        except Exception as e:
            logger.error(f"Cache sync task error: {e}")
            return {"status": "error", "message": str(e)}
    
    
    return celery


from app import create_app

flask_app = create_app()
celery = celery_init_app(flask_app)

# Register tasks
create_geofence_tasks(celery)