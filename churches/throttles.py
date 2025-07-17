"""
Custom throttle classes for OpenRouteService integration APIs.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class GeocodingRateThrottle(AnonRateThrottle):
    """
    Custom throttle for geocoding API endpoints.
    Limits requests to prevent abuse of the OpenRouteService API.
    """
    scope = 'geocoding'


class DirectionsRateThrottle(AnonRateThrottle):
    """
    Custom throttle for directions API endpoints.
    More restrictive than geocoding due to higher computational cost.
    """
    scope = 'directions'


class ReverseGeocodingRateThrottle(AnonRateThrottle):
    """
    Custom throttle for reverse geocoding API endpoints.
    """
    scope = 'reverse_geocoding'


class GeocodingUserRateThrottle(UserRateThrottle):
    """
    User-specific throttle for geocoding API endpoints.
    Allows higher limits for authenticated users.
    """
    scope = 'geocoding'


class DirectionsUserRateThrottle(UserRateThrottle):
    """
    User-specific throttle for directions API endpoints.
    """
    scope = 'directions'


class ReverseGeocodingUserRateThrottle(UserRateThrottle):
    """
    User-specific throttle for reverse geocoding API endpoints.
    """
    scope = 'reverse_geocoding'