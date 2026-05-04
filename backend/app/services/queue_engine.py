import json
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from app.extensions import redis_conn


QUEUE_KEY_PREFIX = "queue"
PRIORITY_QUEUE = f"{QUEUE_KEY_PREFIX}:priority"          # Sorted set: appointment_id -> score
LINEAR_QUEUE = f"{QUEUE_KEY_PREFIX}:linear"              # List: [appointment_id, ...]
QUEUE_STATE_KEY = f"{QUEUE_KEY_PREFIX}:state"            # Hash: appointment_id -> JSON state
QUEUE_POSITION_KEY = f"{QUEUE_KEY_PREFIX}:position"      # Hash: appointment_id -> position


class QueueEngine:
    """Core queue management with O(log N) inserts and instant position lookups."""
    
    @staticmethod
    def enqueue_patient(
        appointment_id: str, 
        patient_id: str,
        is_priority: bool = False, 
        priority_score: float = 0.0
    ) -> dict:
        """
        Adds a patient to the appropriate queue (priority or linear).
        
        Priority queue uses a Redis sorted set with:
        - Score: negative priority_score (lower score = higher priority)
        - Member: appointment_id
        
        Linear queue uses a Redis list (FIFO).
        """
        timestamp = time.time()
        
        # Store initial state in Redis hash
        state = {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "is_priority": "1" if is_priority else "0",
            "priority_score": priority_score,
            "enqueued_at": timestamp,
            "status": "waiting",
        }
        redis_conn.hset(QUEUE_STATE_KEY, appointment_id, json.dumps(state))
        
        if is_priority:
            # For priority queue: negate score so ZRANGE returns highest priority first
            # Use negative priority_score as primary sort, timestamp as tiebreaker
            redis_score = (-priority_score * 1000) + (timestamp / 1e6)
            redis_conn.zadd(PRIORITY_QUEUE, {appointment_id: redis_score})
            queue_type = "priority"
        else:
            # For linear queue: append to list (FIFO)
            redis_conn.rpush(LINEAR_QUEUE, appointment_id)
            queue_type = "linear"
        
        # Recalculate all positions
        QueueEngine._update_all_positions()
        
        return {
            "queue": queue_type,
            "status": "enqueued",
            "appointment_id": appointment_id,
            "position": QueueEngine.get_position(appointment_id),
        }
    
    @staticmethod
    def get_next_patient() -> Optional[str]:
        """
        Gets the next patient to be called.
        Checks priority queue first (highest priority), then linear queue.
        Returns appointment_id or None if both queues empty.
        """
        # Check priority queue first (ZRANGE returns in ascending order, so [0] is lowest score = highest priority)
        priority_result = redis_conn.zrange(PRIORITY_QUEUE, 0, 0)
        if priority_result:
            appointment_id = priority_result[0]
            redis_conn.zrem(PRIORITY_QUEUE, appointment_id)
            return appointment_id
        
        # If priority queue empty, check linear queue
        linear_result = redis_conn.lpop(LINEAR_QUEUE)
        if linear_result:
            return linear_result
        
        return None
    
    @staticmethod
    def mark_called(appointment_id: str) -> dict:
        from app.models import QueueToken
        from app.services.notification_service import NotificationService

        state = QueueEngine._get_state(appointment_id)
        if not state:
            return {"error": "Appointment not found", "code": 404}

        state["status"] = "called"
        redis_conn.hset(QUEUE_STATE_KEY, appointment_id, json.dumps(state))

        # remove from queues
        redis_conn.zrem(PRIORITY_QUEUE, appointment_id)
        redis_conn.lrem(LINEAR_QUEUE, 0, appointment_id)

        # ✅ SAFE DB ACCESS (inside function)
        token = QueueToken.query.filter_by(
            appointment_id=appointment_id
        ).first()

        token_number = token.token_number if token else 0

        # ✅ PUSH
        patient_id = state["patient_id"]
        fcm_token = redis_conn.get(f"push_token:{patient_id}")

        if fcm_token:
            if isinstance(fcm_token, bytes):
                fcm_token = fcm_token.decode()

            NotificationService.on_called(
                patient_id,
                token_number,
                fcm_token
            )

        QueueEngine._update_all_positions()
        from app.sockets.events import broadcast_queue_update
        broadcast_queue_update()
        return {"status": "success"}
        
    @staticmethod
    def mark_completed(appointment_id: str) -> dict:
        """Mark appointment as completed (seen by doctor)."""
        state = QueueEngine._get_state(appointment_id)
        if not state:
            return {"error": "Appointment not found in queue", "code": 404}
        
        state["status"] = "completed"
        state["completed_at"] = time.time()
        redis_conn.hset(QUEUE_STATE_KEY, appointment_id, json.dumps(state))
        
        # Clean up positions
        redis_conn.hdel(QUEUE_POSITION_KEY, appointment_id)
        
        return {"status": "success", "appointment_id": appointment_id}
    
    @staticmethod
    def get_position(appointment_id: str) -> Optional[int]:
        """Get the current queue position for a patient. Returns 0 if not in queue."""
        pos_str = redis_conn.hget(QUEUE_POSITION_KEY, appointment_id)
        return int(pos_str) if pos_str else 0
    
    @staticmethod
    def get_queue_state(appointment_id: str) -> Optional[dict]:
        """Get full state for an appointment."""
        state_json = redis_conn.hget(QUEUE_STATE_KEY, appointment_id)
        if not state_json:
            return None
        return json.loads(state_json)
    
    @staticmethod
    def get_queue_ahead(appointment_id: str) -> int:
        """Get count of patients ahead in the queue."""
        pos = QueueEngine.get_position(appointment_id)
        return max(0, pos - 1)
    
    @staticmethod
    def get_all_queued(limit: int = 100) -> list:
        """Get all currently queued appointments with positions."""
        # Combine both queues
        priority_ids = redis_conn.zrange(PRIORITY_QUEUE, 0, limit)
        linear_ids = redis_conn.lrange(LINEAR_QUEUE, 0, limit - len(priority_ids))
        
        all_ids = list(priority_ids) + linear_ids
        result = []
        
        for i, app_id in enumerate(all_ids, 1):
            state = QueueEngine._get_state(app_id)
            if state:
                state["position"] = i
                result.append(state)
        
        return result
    
    @staticmethod
    def cancel_token(appointment_id: str) -> dict:
        """Remove a patient from the queue."""
        state = QueueEngine._get_state(appointment_id)
        if not state:
            return {"error": "Appointment not found", "code": 404}
        
        state["status"] = "cancelled"
        redis_conn.hset(QUEUE_STATE_KEY, appointment_id, json.dumps(state))
        
        # Remove from queues
        redis_conn.zrem(PRIORITY_QUEUE, appointment_id)
        redis_conn.lrem(LINEAR_QUEUE, 0, appointment_id)
        redis_conn.hdel(QUEUE_POSITION_KEY, appointment_id)
        
        QueueEngine._update_all_positions()
        
        return {"status": "success", "appointment_id": appointment_id}
    
    # ─────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────
    
    @staticmethod
    def _get_state(appointment_id: str) -> Optional[dict]:
        """Fetch and parse state from Redis."""
        state_json = redis_conn.hget(QUEUE_STATE_KEY, appointment_id)
        if not state_json:
            return None
        return json.loads(state_json)
    
    @staticmethod
    def _update_all_positions():
        """Recalculate and cache all queue positions."""
        priority_ids = redis_conn.zrange(PRIORITY_QUEUE, 0, -1)
        linear_ids = redis_conn.lrange(LINEAR_QUEUE, 0, -1)
        
        all_ids = list(priority_ids) + linear_ids
        
        # Clear old positions
        redis_conn.delete(QUEUE_POSITION_KEY)
        
        from app.services.notification_service import NotificationService
        from app.sockets.events import broadcast_queue_update

        INTERVAL_SECONDS = 5  # 🔥 control notification frequency

        for i, app_id in enumerate(all_ids, 1):
            redis_conn.hset(QUEUE_POSITION_KEY, app_id, i)

            state = QueueEngine._get_state(app_id)
            if not state:
                continue

            patient_id = state["patient_id"]
            people_ahead = i - 1

            # 🔥 HANDLE PREVIOUS POSITION (IMPORTANT FIX)
            prev_key = f"prev_pos:{app_id}"
            prev_pos = redis_conn.get(prev_key)

            if prev_pos:
                if isinstance(prev_pos, bytes):
                    prev_pos = prev_pos.decode()
                prev_pos = int(prev_pos)
            else:
                prev_pos = i

            redis_conn.setex(prev_key, 300, i)  # expires in 5 min

            prev_ahead = prev_pos - 1
            curr_ahead = people_ahead

            trigger_points = [4, 3, 2, 1, 0]  # ✅ added 0 also

            triggered_point = None

            for point in trigger_points:
                if prev_ahead > point >= curr_ahead:
                    triggered_point = point
                    break

            if triggered_point is None:
                continue

            people_ahead = triggered_point


            # 🔑 get push token
            fcm_token = redis_conn.get(f"push_token:{patient_id}")
            if not fcm_token:
                continue

            if isinstance(fcm_token, bytes):
                fcm_token = fcm_token.decode()

            print(f"📢 QUEUE NOTIFY → {app_id} | ahead={people_ahead}")

            # 🔔 dynamic message
            if people_ahead == 0:
                title = "📢 Please Proceed"
                body = "Doctor is ready for you now"

            elif people_ahead == 1:
                title = "🚨 You're Next"
                body = "Please be ready, your turn is next!"

            else:
                title = "🕐 Queue Update"
                body = f"{people_ahead} patients ahead of you"

            # 🔔 send notification
            # 🔥 USE CORRECT FUNCTION
            if people_ahead in [4, 3, 2, 1]:
                NotificationService.on_countdown_position(
                    app_id,
                    patient_id,
                    people_ahead,
                    fcm_token
                )

            # 🔥 HANDLE "CALLED" (ahead = 0)
            elif people_ahead == 0:
                NotificationService.on_called(
                    patient_id,
                    0,  # token number optional
                    fcm_token
                )

        # 🔄 realtime UI update
        broadcast_queue_update()

    @staticmethod
    def clear_expired_queues(date_str: str = None):
        """Clear queues for a given date (useful for end-of-day cleanup)."""
        # This could be enhanced to track by date, for now just clears all
        redis_conn.delete(PRIORITY_QUEUE)
        redis_conn.delete(LINEAR_QUEUE)
        redis_conn.delete(QUEUE_POSITION_KEY)
        redis_conn.delete(QUEUE_STATE_KEY)

def get_patient_position(appointment_id: str) -> int:
    """
    Returns the 1-indexed position of the patient across both queues.
    Priority queue members are ahead of all linear queue members.
    """
    # Check if in priority queue
    priority_rank = redis_conn.zrank(PRIORITY_QUEUE, appointment_id)
    if priority_rank is not None:
        return priority_rank + 1
        
    # Check if in linear queue
    # LPOS is O(N), but we need it. Available in Redis 6.0.6+
    try:
        linear_rank = redis_conn.execute_command('LPOS', LINEAR_QUEUE, appointment_id)
        if linear_rank is not None:
            priority_count = redis_conn.zcard(PRIORITY_QUEUE)
            return priority_count + int(linear_rank) + 1
    except Exception:
        # Fallback if LPOS is not available (older redis)
        items = redis_conn.lrange(LINEAR_QUEUE, 0, -1)
        try:
            linear_rank = items.index(appointment_id)
            priority_count = redis_conn.zcard(PRIORITY_QUEUE)
            return priority_count + linear_rank + 1
        except ValueError:
            pass
            
    return -1

def get_queue_state() -> dict:
    """
    Returns the full state of both queues.
    """
    priority_items = redis_conn.zrange(PRIORITY_QUEUE, 0, -1)
    linear_items = redis_conn.lrange(LINEAR_QUEUE, 0, -1)
    
    return {
        "priority_queue": priority_items,
        "linear_queue": linear_items,
        "total": len(priority_items) + len(linear_items)
    }

def remove_from_queue(appointment_id: str) -> bool:
    """
    Removes patient from either queue (if they cancel or are marked complete early).
    """
    removed = redis_conn.zrem(PRIORITY_QUEUE, appointment_id)
    if removed > 0:
        return True
        
    removed = redis_conn.lrem(LINEAR_QUEUE, 0, appointment_id)
    if removed > 0:
        return True
        
    return False

def clear_queues():
    """
    Clears all queues.
    """
    redis_conn.delete(PRIORITY_QUEUE)
    redis_conn.delete(LINEAR_QUEUE)
