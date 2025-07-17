from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from django.db.models import Q
from .models import Church
from .serializers import (
    ChurchSerializer, 
    ChurchListSerializer, 
    ChurchMapSerializer,
    ChurchSearchSerializer
)
from .services import GeocodingService, GeocodingError, DirectionsService, ReverseGeocodingService
from .throttles import GeocodingRateThrottle, DirectionsRateThrottle, ReverseGeocodingRateThrottle
import logging

logger = logging.getLogger(__name__)


def index(request):
    """
    Main map page view.
    Renders the interactive church map interface.
    """
    return render(request, 'churches/index.html')


class ChurchListAPIView(generics.ListAPIView):
    """
    API endpoint for retrieving all church locations.
    Supports filtering by state, city, and active status.
    """
    serializer_class = ChurchListSerializer
    
    def get_queryset(self):
        """
        Filter churches based on query parameters.
        """
        queryset = Church.objects.filter(is_active=True).order_by('state', 'city', 'name')
        
        # Filter by state
        state = self.request.query_params.get('state', None)
        if state:
            queryset = queryset.filter(state__icontains=state)
        
        # Filter by city
        city = self.request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Filter by churches with coordinates only (for map display)
        has_coordinates = self.request.query_params.get('has_coordinates', None)
        if has_coordinates and has_coordinates.lower() == 'true':
            queryset = queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False
            )
        
        return queryset


class ChurchDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving individual church information.
    """
    queryset = Church.objects.filter(is_active=True)
    serializer_class = ChurchSerializer
    lookup_field = 'id'


class ChurchMapAPIView(generics.ListAPIView):
    """
    Optimized API endpoint for map display with minimal data.
    Only returns churches with valid coordinates.
    """
    serializer_class = ChurchMapSerializer
    pagination_class = None  # Disable pagination for map data
    
    def get_queryset(self):
        """
        Return only active churches with valid coordinates.
        """
        return Church.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).order_by('state', 'city', 'name')


class ChurchSearchAPIView(generics.ListAPIView):
    """
    API endpoint for location-based church search.
    Supports searching by address, city, state, or coordinates.
    """
    serializer_class = ChurchSearchSerializer
    
    def get_queryset(self):
        """
        Search churches based on location parameters.
        """
        # Get search parameters
        query = self.request.query_params.get('q', '')
        lat = self.request.query_params.get('lat', None)
        lng = self.request.query_params.get('lng', None)
        radius = self.request.query_params.get('radius', 50)  # Default 50km radius
        
        try:
            radius = float(radius)
        except (ValueError, TypeError):
            radius = 50
        
        queryset = Church.objects.filter(is_active=True)
        
        # If coordinates are provided, search by proximity
        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                
                # Find nearby churches using the model's find_nearby method
                nearby_churches = Church.find_nearby(lat, lng, radius)
                
                # Add distance information to each church
                for church in nearby_churches:
                    church.distance = church.distance_to_point(lat, lng)
                
                return nearby_churches
                
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid coordinates provided: lat={lat}, lng={lng}, error={e}")
                return queryset.none()
        
        # If text query is provided, search by text and then geocode
        elif query:
            # First try text-based search
            text_results = queryset.filter(
                Q(name__icontains=query) |
                Q(city__icontains=query) |
                Q(state__icontains=query) |
                Q(street_address__icontains=query)
            )
            
            # If we have results, return them
            if text_results.exists():
                return text_results
            
            # If no text results, try geocoding the query
            try:
                geocoding_service = GeocodingService()
                geocode_result = geocoding_service.geocode_address(query)
                
                if geocode_result['success']:
                    lat = geocode_result['latitude']
                    lng = geocode_result['longitude']
                    
                    # Find nearby churches
                    nearby_churches = Church.find_nearby(lat, lng, radius)
                    
                    # Add distance information
                    for church in nearby_churches:
                        church.distance = church.distance_to_point(lat, lng)
                    
                    return nearby_churches
                else:
                    logger.warning(f"Geocoding failed for query '{query}': {geocode_result.get('error')}")
                    
            except GeocodingError as e:
                logger.error(f"Geocoding service error for query '{query}': {e}")
        
        # Return empty queryset if no valid search parameters
        return queryset.none()


@api_view(['GET'])
def church_stats(request):
    """
    API endpoint for church statistics.
    Returns counts by state and overall statistics.
    """
    try:
        # Overall statistics
        total_churches = Church.objects.filter(is_active=True).count()
        churches_with_coordinates = Church.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        ).count()
        
        # Statistics by state
        state_stats = {}
        states = Church.objects.filter(is_active=True).values_list('state', flat=True).distinct()
        
        for state in states:
            state_count = Church.objects.filter(is_active=True, state=state).count()
            state_with_coords = Church.objects.filter(
                is_active=True,
                state=state,
                latitude__isnull=False,
                longitude__isnull=False
            ).count()
            
            state_stats[state] = {
                'total': state_count,
                'with_coordinates': state_with_coords,
                'geocoding_percentage': round((state_with_coords / state_count * 100), 1) if state_count > 0 else 0
            }
        
        return Response({
            'total_churches': total_churches,
            'churches_with_coordinates': churches_with_coordinates,
            'geocoding_percentage': round((churches_with_coordinates / total_churches * 100), 1) if total_churches > 0 else 0,
            'states': state_stats
        })
        
    except Exception as e:
        logger.error(f"Error generating church statistics: {e}")
        return Response(
            {'error': 'Failed to generate statistics'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# OpenRouteService Integration API Views

@api_view(['POST'])
@throttle_classes([GeocodingRateThrottle])
def geocoding_api(request):
    """
    API endpoint for address-to-coordinate conversion using OpenRouteService.
    
    POST /api/geocoding/
    {
        "address": "123 Main St, New York, NY",
        "country": "US"  // optional
    }
    """
    try:
        address = request.data.get('address', '').strip()
        country = request.data.get('country', 'US')
        
        if not address:
            return Response(
                {'error': 'Address is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the existing geocoding service
        geocoding_service = GeocodingService()
        result = geocoding_service.geocode_address(address, country=country)
        
        if result['success']:
            return Response({
                'success': True,
                'coordinates': {
                    'latitude': result['latitude'],
                    'longitude': result['longitude']
                },
                'accuracy': result['accuracy'],
                'formatted_address': result['formatted_address'],
                'confidence': result.get('confidence', 0)
            })
        else:
            return Response(
                {'success': False, 'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Geocoding API error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@throttle_classes([DirectionsRateThrottle])
def directions_api(request):
    """
    API endpoint for getting directions between two points using OpenRouteService.
    
    POST /api/directions/
    {
        "start": {"latitude": 40.7128, "longitude": -74.0060},
        "end": {"latitude": 34.0522, "longitude": -118.2437},
        "profile": "driving-car"  // optional: driving-car, foot-walking, cycling-regular
    }
    """
    try:
        start = request.data.get('start', {})
        end = request.data.get('end', {})
        profile = request.data.get('profile', 'driving-car')
        
        # Validate input
        if not start or not end:
            return Response(
                {'error': 'Both start and end coordinates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_lat = start.get('latitude')
        start_lng = start.get('longitude')
        end_lat = end.get('latitude')
        end_lng = end.get('longitude')
        
        if None in [start_lat, start_lng, end_lat, end_lng]:
            return Response(
                {'error': 'Invalid coordinates provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_lat = float(start_lat)
            start_lng = float(start_lng)
            end_lat = float(end_lat)
            end_lng = float(end_lng)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordinates must be valid numbers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the directions service
        directions_service = DirectionsService()
        result = directions_service.get_directions(
            start_coords=(start_lng, start_lat),
            end_coords=(end_lng, end_lat),
            profile=profile
        )
        
        if result['success']:
            return Response({
                'success': True,
                'distance': result['distance'],  # meters
                'duration': result['duration'],  # seconds
                'geometry': result['geometry'],
                'instructions': result.get('instructions', [])
            })
        else:
            return Response(
                {'success': False, 'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Directions API error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@throttle_classes([ReverseGeocodingRateThrottle])
def reverse_geocoding_api(request):
    """
    API endpoint for coordinate-to-address conversion using OpenRouteService.
    
    POST /api/reverse-geocoding/
    {
        "latitude": 40.7128,
        "longitude": -74.0060
    }
    """
    try:
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response(
                {'error': 'Both latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Coordinates must be valid numbers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use the reverse geocoding service
        reverse_geocoding_service = ReverseGeocodingService()
        result = reverse_geocoding_service.reverse_geocode(latitude, longitude)
        
        if result['success']:
            return Response({
                'success': True,
                'address': result['address'],
                'components': result['components'],
                'confidence': result.get('confidence', 0)
            })
        else:
            return Response(
                {'success': False, 'error': result['error']},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Reverse geocoding API error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )