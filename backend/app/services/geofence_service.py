import math
from typing import Tuple, Optional
from app.extensions import redis_conn
import logging

logger = logging.getLogger(__name__)

# Hospital coordinates (example: Mumbai Hospital)
# These should come from config/env variables
HOSPITAL_LAT = 12.8286385
HOSPITAL_LNG = 79.7037373
HOSPITAL_RADIUS_METERS = 200  # 200m radius


class GeofenceService:
    """
    Location-based alerts using Haversine formula.
    Checks if patient is within hospital radius.
    """
    
    @staticmethod
    def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two coordinates in meters.
        lat/lng in decimal degrees.
        """
        R = 6371000  # Earth's radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2) ** 2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def is_within_hospital(lat: float, lng: float) -> bool:
        """Check if coordinates are within hospital radius."""
        distance = GeofenceService.haversine_distance(
            HOSPITAL_LAT, HOSPITAL_LNG, lat, lng
        )
        return distance <= HOSPITAL_RADIUS_METERS
    
    @staticmethod
    def check_geofence_violation(
        patient_id: str,
        current_lat: float,
        current_lng: float,
        queue_position: int,
        appointment_id: str = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if patient left the hospital area while close to their turn.
        
        Returns:
            (is_violation: bool, alert_message: str or None)
        """
        # Only alert if patient is within 4 positions of being called

        print("📍 GEO CHECK:", patient_id, queue_position, current_lat, current_lng)

        if queue_position > 4 or queue_position <= 0:
            return (False, None)
        
        within_radius = GeofenceService.is_within_hospital(current_lat, current_lng)
        
        # Get previous location from Redis
        location_key = f"patient:{patient_id}:last_location"
        prev_location = redis_conn.hgetall(location_key)
        
        if not prev_location or not prev_location.get("lat"):
            # First location update, just store it
            GeofenceService._store_location(patient_id, current_lat, current_lng)
            return (False, None)
        
        prev_lat = float(prev_location["lat"])
        prev_lng = float(prev_location["lng"])
        was_in_radius = GeofenceService.is_within_hospital(prev_lat, prev_lng)
        
        # Violation: was inside, now outside
        if not within_radius:
            INTERVAL_SECONDS = 10
            notif_key = f"geo_notif:{appointment_id}"

            if redis_conn.get(notif_key):
                return (False, None)

            redis_conn.setex(notif_key, INTERVAL_SECONDS, "1")
            logger.warning(f"Geofence violation: patient {patient_id} left hospital area")
            print("🚨 GEOFENCE VIOLATION TRIGGERED")

            # 🔥 SEND NOTIFICATION
            try:
                from app.services.notification_service import NotificationService

                fcm_token = redis_conn.get(f"push_token:{patient_id}")

                if fcm_token:
                    if isinstance(fcm_token, bytes):
                        fcm_token = fcm_token.decode()

                    NotificationService.send_push_notification(
                        fcm_token,
                        title="⚠️ Return to Hospital",
                        body="You are near your turn. Please return to the hospital.",
                        data={
                            "type": "geofence_violation",
                            "appointment_id": appointment_id
                        }
                    )

            except Exception as e:
                logger.error(f"Geofence notification failed: {e}")

            # 🔥 OPTIONAL: SOCKET EVENT
            try:
                from app.sockets.events import broadcast_geofence_warning
                broadcast_geofence_warning(appointment_id)
            except Exception:
                pass

            return (True, "GEOFENCE_VIOLATION")
        
        # Store current location
        GeofenceService._store_location(patient_id, current_lat, current_lng)
        
        return (False, None)
    
    @staticmethod
    def _store_location(patient_id: str, lat: float, lng: float):
        """Store patient's current location in Redis."""
        location_key = f"patient:{patient_id}:last_location"
        redis_conn.hset(location_key, mapping={"lat": lat, "lng": lng})
        redis_conn.expire(location_key, 3600)  # Expire after 1 hour
    
    @staticmethod
    def get_distance_from_hospital(lat: float, lng: float) -> float:
        """Get distance in meters from hospital."""
        return GeofenceService.haversine_distance(
            HOSPITAL_LAT, HOSPITAL_LNG, lat, lng
        )
    
    @staticmethod
    def get_hospital_boundary() -> dict:
        """Return hospital location and radius for client-side geofencing."""
        return {
            "latitude": HOSPITAL_LAT,
            "longitude": HOSPITAL_LNG,
            "radius_meters": HOSPITAL_RADIUS_METERS,
        }