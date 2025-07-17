"""
Services for church data management and geocoding functionality.
"""

import requests
import time
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from decimal import Decimal
import hashlib

logger = logging.getLogger(__name__)


class GeocodingError(Exception):
    """Custom exception for geocoding-related errors."""
    pass


class GeocodingService:
    """
    Service class for geocoding addresses using OpenRouteService API.
    Provides address-to-coordinate conversion with error handling and retry logic.
    """
    
    # OpenRouteService geocoding endpoint
    BASE_URL = "https://api.openrouteservice.org/geocode/search"
    
    # Default configuration
    DEFAULT_TIMEOUT = 10  # seconds
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1  # seconds
    CACHE_TIMEOUT = 86400 * 7  # 7 days in seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the geocoding service.
        
        Args:
            api_key: OpenRouteService API key. If not provided, will try to get from settings.
        """
        self.api_key = api_key or getattr(settings, 'OPENROUTESERVICE_API_KEY', None)
        if not self.api_key:
            raise GeocodingError(
                "OpenRouteService API key is required. Set OPENROUTESERVICE_API_KEY in settings."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'ChurchMapProject/1.0'
        })
    
    def geocode_address(
        self, 
        address: str, 
        country: str = 'US',
        timeout: int = None,
        retries: int = None,
        use_cache: bool = True
    ) -> Dict:
        """
        Geocode a single address to coordinates.
        
        Args:
            address: The address string to geocode
            country: Country code to limit search (default: 'US')
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            use_cache: Whether to use cached results
            
        Returns:
            Dict containing geocoding results with keys:
            - 'success': bool indicating if geocoding was successful
            - 'latitude': float latitude coordinate (if successful)
            - 'longitude': float longitude coordinate (if successful)
            - 'accuracy': str accuracy level ('high', 'medium', 'low')
            - 'formatted_address': str formatted address from geocoder
            - 'error': str error message (if unsuccessful)
            
        Raises:
            GeocodingError: If geocoding fails after all retries
        """
        if not address or not address.strip():
            return {
                'success': False,
                'error': 'Address cannot be empty'
            }
        
        address = address.strip()
        timeout = timeout or self.DEFAULT_TIMEOUT
        retries = retries or self.DEFAULT_RETRIES
        
        # Check cache first
        if use_cache:
            cached_result = self._get_cached_result(address, country)
            if cached_result:
                logger.info(f"Using cached geocoding result for: {address}")
                return cached_result
        
        # Prepare request parameters
        params = {
            'text': address,
            'boundary.country': country,
            'size': 1,  # Only return the best match
            'layers': 'address,venue'  # Focus on addresses and venues
        }
        
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                logger.info(f"Geocoding attempt {attempt + 1}/{retries + 1} for: {address}")
                
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=timeout
                )
                
                # Check for HTTP errors
                response.raise_for_status()
                
                # Parse response
                data = response.json()
                result = self._parse_geocoding_response(data, address)
                
                # Cache successful results
                if result['success'] and use_cache:
                    self._cache_result(address, country, result)
                
                return result
                
            except requests.exceptions.Timeout as e:
                last_error = f"Request timeout: {str(e)}"
                logger.warning(f"Geocoding timeout for {address}: {last_error}")
                
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response and e.response.status_code == 429:  # Rate limit
                    last_error = "Rate limit exceeded"
                    logger.warning(f"Rate limit hit for {address}, attempt {attempt + 1}")
                    if attempt < retries:
                        time.sleep(self.DEFAULT_RETRY_DELAY * (attempt + 1))  # Exponential backoff
                        continue
                else:
                    status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'
                    last_error = f"HTTP error {status_code}: {str(e)}"
                    logger.error(f"HTTP error geocoding {address}: {last_error}")
                    break
                    
            except requests.exceptions.RequestException as e:
                last_error = f"Request error: {str(e)}"
                logger.error(f"Request error geocoding {address}: {last_error}")
                
            except (ValueError, KeyError) as e:
                last_error = f"Response parsing error: {str(e)}"
                logger.error(f"Response parsing error for {address}: {last_error}")
                break
                
            # Wait before retry (except for the last attempt)
            if attempt < retries:
                time.sleep(self.DEFAULT_RETRY_DELAY)
        
        # All attempts failed
        error_msg = f"Geocoding failed after {retries + 1} attempts: {last_error}"
        logger.error(f"Failed to geocode {address}: {error_msg}")
        
        return {
            'success': False,
            'error': error_msg
        }
    
    def geocode_batch(
        self, 
        addresses: List[str], 
        country: str = 'US',
        delay_between_requests: float = 0.1
    ) -> List[Dict]:
        """
        Geocode multiple addresses with rate limiting.
        
        Args:
            addresses: List of address strings to geocode
            country: Country code to limit search
            delay_between_requests: Delay in seconds between requests
            
        Returns:
            List of geocoding result dictionaries
        """
        results = []
        
        for i, address in enumerate(addresses):
            logger.info(f"Geocoding batch progress: {i + 1}/{len(addresses)}")
            
            result = self.geocode_address(address, country=country)
            results.append(result)
            
            # Rate limiting delay
            if i < len(addresses) - 1 and delay_between_requests > 0:
                time.sleep(delay_between_requests)
        
        return results
    
    def _parse_geocoding_response(self, data: Dict, original_address: str) -> Dict:
        """
        Parse the OpenRouteService geocoding response.
        
        Args:
            data: JSON response from OpenRouteService
            original_address: Original address that was geocoded
            
        Returns:
            Parsed geocoding result dictionary
        """
        try:
            features = data.get('features', [])
            
            if not features:
                return {
                    'success': False,
                    'error': 'No results found for address'
                }
            
            # Get the best match (first result)
            feature = features[0]
            geometry = feature.get('geometry', {})
            properties = feature.get('properties', {})
            
            # Extract coordinates
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) < 2:
                return {
                    'success': False,
                    'error': 'Invalid coordinates in response'
                }
            
            longitude, latitude = coordinates[0], coordinates[1]
            
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return {
                    'success': False,
                    'error': f'Invalid coordinate ranges: lat={latitude}, lon={longitude}'
                }
            
            # Determine accuracy based on geocoding confidence and layer
            accuracy = self._determine_accuracy(properties)
            
            # Get formatted address
            formatted_address = properties.get('label', original_address)
            
            return {
                'success': True,
                'latitude': float(latitude),
                'longitude': float(longitude),
                'accuracy': accuracy,
                'formatted_address': formatted_address,
                'confidence': properties.get('confidence', 0),
                'layer': properties.get('layer', 'unknown')
            }
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return {
                'success': False,
                'error': f'Error parsing geocoding response: {str(e)}'
            }
    
    def _determine_accuracy(self, properties: Dict) -> str:
        """
        Determine geocoding accuracy based on response properties.
        
        Args:
            properties: Properties from geocoding response
            
        Returns:
            Accuracy level: 'high', 'medium', or 'low'
        """
        confidence = properties.get('confidence', 0)
        layer = properties.get('layer', '').lower()
        
        # High accuracy: address-level results with high confidence
        if layer in ['address', 'venue'] and confidence >= 0.8:
            return 'high'
        
        # Medium accuracy: street layer or decent confidence
        elif layer == 'street' or confidence >= 0.5:
            return 'medium'
        
        # Low accuracy: everything else
        else:
            return 'low'
    
    def _get_cache_key(self, address: str, country: str) -> str:
        """
        Generate a cache key for the geocoding result.
        
        Args:
            address: Address string
            country: Country code
            
        Returns:
            Cache key string
        """
        # Create a hash of the address and country for consistent caching
        content = f"{address.lower().strip()}:{country.lower()}"
        hash_object = hashlib.md5(content.encode())
        return f"geocoding:{hash_object.hexdigest()}"
    
    def _get_cached_result(self, address: str, country: str) -> Optional[Dict]:
        """
        Retrieve cached geocoding result.
        
        Args:
            address: Address string
            country: Country code
            
        Returns:
            Cached result dictionary or None if not found
        """
        cache_key = self._get_cache_key(address, country)
        return cache.get(cache_key)
    
    def _cache_result(self, address: str, country: str, result: Dict) -> None:
        """
        Cache a geocoding result.
        
        Args:
            address: Address string
            country: Country code
            result: Result dictionary to cache
        """
        cache_key = self._get_cache_key(address, country)
        cache.set(cache_key, result, self.CACHE_TIMEOUT)
    
    def clear_cache(self) -> None:
        """
        Clear all cached geocoding results.
        Note: This is a simple implementation that clears the entire cache.
        In production, you might want a more targeted approach.
        """
        cache.clear()
        logger.info("Geocoding cache cleared")


class ChurchDataService:
    """
    Service class for managing church data import and geocoding operations.
    """
    
    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        """
        Initialize the church data service.
        
        Args:
            geocoding_service: GeocodingService instance. If None, will create one when needed.
        """
        self.geocoding_service = geocoding_service
    
    def geocode_church(self, church, force_update: bool = False) -> Dict:
        """
        Geocode a single church instance.
        
        Args:
            church: Church model instance
            force_update: If True, re-geocode even if church already has coordinates
            
        Returns:
            Dictionary with geocoding results and status
        """
        if church.has_coordinates and not force_update:
            return {
                'success': True,
                'message': 'Church already has coordinates',
                'skipped': True
            }
        
        # Create geocoding service if not provided
        if not self.geocoding_service:
            self.geocoding_service = GeocodingService()
        
        # Geocode the church address
        result = self.geocoding_service.geocode_address(church.full_address)
        
        if result['success']:
            try:
                # Update church coordinates
                church.set_coordinates(
                    result['latitude'],
                    result['longitude'],
                    result['accuracy']
                )
                church.save()
                
                return {
                    'success': True,
                    'message': f'Successfully geocoded to ({result["latitude"]}, {result["longitude"]})',
                    'latitude': result['latitude'],
                    'longitude': result['longitude'],
                    'accuracy': result['accuracy']
                }
                
            except (ValueError, ValidationError) as e:
                return {
                    'success': False,
                    'message': f'Error saving coordinates: {str(e)}'
                }
        else:
            return {
                'success': False,
                'message': f'Geocoding failed: {result.get("error", "Unknown error")}'
            }
    
    def geocode_all_churches(self, force_update: bool = False) -> Dict:
        """
        Geocode all churches that don't have coordinates.
        
        Args:
            force_update: If True, re-geocode churches that already have coordinates
            
        Returns:
            Summary dictionary with statistics
        """
        from .models import Church
        
        # Get churches to geocode
        if force_update:
            churches = Church.objects.filter(is_active=True)
        else:
            churches = Church.objects.filter(
                is_active=True,
                latitude__isnull=True,
                longitude__isnull=True
            )
        
        total_churches = churches.count()
        if total_churches == 0:
            return {
                'success': True,
                'message': 'No churches need geocoding',
                'total': 0,
                'successful': 0,
                'failed': 0,
                'skipped': 0
            }
        
        logger.info(f"Starting geocoding for {total_churches} churches")
        
        successful = 0
        failed = 0
        skipped = 0
        failed_churches = []
        
        for i, church in enumerate(churches, 1):
            logger.info(f"Processing church {i}/{total_churches}: {church.name}")
            
            result = self.geocode_church(church, force_update=force_update)
            
            if result['success']:
                if result.get('skipped'):
                    skipped += 1
                else:
                    successful += 1
                    logger.info(f"✓ {church.name}: {result['message']}")
            else:
                failed += 1
                failed_churches.append({
                    'church': str(church),
                    'error': result['message']
                })
                logger.error(f"✗ {church.name}: {result['message']}")
            
            # Small delay to be respectful to the API
            if i < total_churches:
                time.sleep(0.1)
        
        summary = {
            'success': True,
            'message': f'Geocoding completed: {successful} successful, {failed} failed, {skipped} skipped',
            'total': total_churches,
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'failed_churches': failed_churches
        }
        
        logger.info(summary['message'])
        return summary
    
    def import_church_data(self, church_data: List[Dict]) -> Dict:
        """
        Import church data from a list of dictionaries.
        
        Args:
            church_data: List of dictionaries containing church information
            
        Returns:
            Import summary dictionary
        """
        from .models import Church
        
        if not church_data:
            return {
                'success': False,
                'message': 'No church data provided',
                'total': 0,
                'created': 0,
                'updated': 0,
                'failed': 0
            }
        
        total = len(church_data)
        created = 0
        updated = 0
        failed = 0
        failed_records = []
        
        logger.info(f"Starting import of {total} church records")
        
        for i, data in enumerate(church_data, 1):
            try:
                # Extract required fields
                name = data.get('name', '').strip()
                street_address = data.get('street_address', '').strip()
                city = data.get('city', '').strip()
                state = data.get('state', '').strip()
                
                if not all([name, street_address, city, state]):
                    failed += 1
                    failed_records.append({
                        'index': i,
                        'data': data,
                        'error': 'Missing required fields (name, street_address, city, state)'
                    })
                    continue
                
                # Try to find existing church
                church, was_created = Church.objects.get_or_create(
                    name=name,
                    street_address=street_address,
                    city=city,
                    state=state,
                    defaults={
                        'zip_code': data.get('zip_code', ''),
                        'phone': data.get('phone', ''),
                        'website': data.get('website', ''),
                        'email': data.get('email', ''),
                        'service_times': data.get('service_times', ''),
                        'is_active': data.get('is_active', True)
                    }
                )
                
                if was_created:
                    created += 1
                    logger.info(f"✓ Created: {church.name}")
                else:
                    # Update existing church with new data
                    church.zip_code = data.get('zip_code', church.zip_code)
                    church.phone = data.get('phone', church.phone)
                    church.website = data.get('website', church.website)
                    church.email = data.get('email', church.email)
                    church.service_times = data.get('service_times', church.service_times)
                    church.is_active = data.get('is_active', church.is_active)
                    church.save()
                    updated += 1
                    logger.info(f"✓ Updated: {church.name}")
                
            except Exception as e:
                failed += 1
                failed_records.append({
                    'index': i,
                    'data': data,
                    'error': str(e)
                })
                logger.error(f"✗ Failed to import record {i}: {str(e)}")
        
        summary = {
            'success': True,
            'message': f'Import completed: {created} created, {updated} updated, {failed} failed',
            'total': total,
            'created': created,
            'updated': updated,
            'failed': failed,
            'failed_records': failed_records
        }
        
        logger.info(summary['message'])
        return summary


class DirectionsService:
    """
    Service class for getting directions using OpenRouteService API.
    """
    
    # OpenRouteService directions endpoint
    BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
    
    # Default configuration
    DEFAULT_TIMEOUT = 15  # seconds
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1  # seconds
    CACHE_TIMEOUT = 86400  # 1 day in seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the directions service.
        
        Args:
            api_key: OpenRouteService API key. If not provided, will try to get from settings.
        """
        self.api_key = api_key or getattr(settings, 'OPENROUTESERVICE_API_KEY', None)
        if not self.api_key:
            raise GeocodingError(
                "OpenRouteService API key is required. Set OPENROUTESERVICE_API_KEY in settings."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'ChurchMapProject/1.0'
        })
    
    def get_directions(
        self, 
        start_coords: Tuple[float, float], 
        end_coords: Tuple[float, float],
        profile: str = 'driving-car',
        format_type: str = 'json',
        use_cache: bool = True
    ) -> Dict:
        """
        Get directions between two points.
        
        Args:
            start_coords: Starting coordinates (longitude, latitude)
            end_coords: Ending coordinates (longitude, latitude)
            profile: Routing profile ('driving-car', 'foot-walking', etc.)
            format_type: Response format ('json', 'geojson')
            use_cache: Whether to use cached results
            
        Returns:
            Dict containing directions results with keys:
            - 'success': bool indicating if request was successful
            - 'routes': list of route objects (if successful)
            - 'distance': total distance in meters
            - 'duration': total duration in seconds
            - 'geometry': route geometry
            - 'error': str error message (if unsuccessful)
        """
        try:
            # Validate coordinates
            start_lng, start_lat = start_coords
            end_lng, end_lat = end_coords
            
            if not (-180 <= start_lng <= 180) or not (-90 <= start_lat <= 90):
                return {'success': False, 'error': 'Invalid start coordinates'}
            
            if not (-180 <= end_lng <= 180) or not (-90 <= end_lat <= 90):
                return {'success': False, 'error': 'Invalid end coordinates'}
            
            # Check cache first
            if use_cache:
                cached_result = self._get_cached_directions(start_coords, end_coords, profile)
                if cached_result:
                    logger.info(f"Using cached directions result")
                    return cached_result
            
            # Prepare request data
            request_data = {
                'coordinates': [
                    [start_lng, start_lat],
                    [end_lng, end_lat]
                ],
                'format': format_type,
                'instructions': True,
                'geometry': True
            }
            
            # Update URL for different profiles
            url = self.BASE_URL.replace('driving-car', profile)
            
            last_error = None
            
            for attempt in range(self.DEFAULT_RETRIES + 1):
                try:
                    logger.info(f"Directions attempt {attempt + 1}/{self.DEFAULT_RETRIES + 1}")
                    
                    response = self.session.post(
                        url,
                        json=request_data,
                        timeout=self.DEFAULT_TIMEOUT
                    )
                    
                    # Check for HTTP errors
                    response.raise_for_status()
                    
                    # Parse response
                    data = response.json()
                    result = self._parse_directions_response(data)
                    
                    # Cache successful results
                    if result['success'] and use_cache:
                        self._cache_directions(start_coords, end_coords, profile, result)
                    
                    return result
                    
                except requests.exceptions.Timeout as e:
                    last_error = f"Request timeout: {str(e)}"
                    logger.warning(f"Directions timeout: {last_error}")
                    
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        last_error = "Rate limit exceeded"
                        logger.warning(f"Rate limit hit, attempt {attempt + 1}")
                        if attempt < self.DEFAULT_RETRIES:
                            time.sleep(self.DEFAULT_RETRY_DELAY * (attempt + 1))
                            continue
                    else:
                        status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'
                        last_error = f"HTTP error {status_code}: {str(e)}"
                        logger.error(f"HTTP error getting directions: {last_error}")
                        break
                        
                except requests.exceptions.RequestException as e:
                    last_error = f"Request error: {str(e)}"
                    logger.error(f"Request error getting directions: {last_error}")
                    
                except (ValueError, KeyError) as e:
                    last_error = f"Response parsing error: {str(e)}"
                    logger.error(f"Response parsing error: {last_error}")
                    break
                    
                # Wait before retry (except for the last attempt)
                if attempt < self.DEFAULT_RETRIES:
                    time.sleep(self.DEFAULT_RETRY_DELAY)
            
            # All attempts failed
            error_msg = f"Directions failed after {self.DEFAULT_RETRIES + 1} attempts: {last_error}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _parse_directions_response(self, data: Dict) -> Dict:
        """
        Parse the OpenRouteService directions response.
        
        Args:
            data: JSON response from OpenRouteService
            
        Returns:
            Parsed directions result dictionary
        """
        try:
            routes = data.get('routes', [])
            
            if not routes:
                return {
                    'success': False,
                    'error': 'No routes found'
                }
            
            # Get the first (best) route
            route = routes[0]
            summary = route.get('summary', {})
            
            return {
                'success': True,
                'routes': routes,
                'distance': summary.get('distance', 0),  # meters
                'duration': summary.get('duration', 0),  # seconds
                'geometry': route.get('geometry', ''),
                'instructions': route.get('segments', [{}])[0].get('steps', []) if route.get('segments') else []
            }
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return {
                'success': False,
                'error': f'Error parsing directions response: {str(e)}'
            }
    
    def _get_cache_key(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], profile: str) -> str:
        """
        Generate a cache key for the directions result.
        """
        content = f"{start_coords[0]:.6f},{start_coords[1]:.6f}:{end_coords[0]:.6f},{end_coords[1]:.6f}:{profile}"
        hash_object = hashlib.md5(content.encode())
        return f"directions:{hash_object.hexdigest()}"
    
    def _get_cached_directions(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], profile: str) -> Optional[Dict]:
        """
        Retrieve cached directions result.
        """
        cache_key = self._get_cache_key(start_coords, end_coords, profile)
        return cache.get(cache_key)
    
    def _cache_directions(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], profile: str, result: Dict) -> None:
        """
        Cache a directions result.
        """
        cache_key = self._get_cache_key(start_coords, end_coords, profile)
        cache.set(cache_key, result, self.CACHE_TIMEOUT)


class ReverseGeocodingService:
    """
    Service class for reverse geocoding using OpenRouteService API.
    Converts coordinates to addresses.
    """
    
    # OpenRouteService reverse geocoding endpoint
    BASE_URL = "https://api.openrouteservice.org/geocode/reverse"
    
    # Default configuration
    DEFAULT_TIMEOUT = 10  # seconds
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1  # seconds
    CACHE_TIMEOUT = 86400 * 7  # 7 days in seconds
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the reverse geocoding service.
        
        Args:
            api_key: OpenRouteService API key. If not provided, will try to get from settings.
        """
        self.api_key = api_key or getattr(settings, 'OPENROUTESERVICE_API_KEY', None)
        if not self.api_key:
            raise GeocodingError(
                "OpenRouteService API key is required. Set OPENROUTESERVICE_API_KEY in settings."
            )
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'User-Agent': 'ChurchMapProject/1.0'
        })
    
    def reverse_geocode(
        self, 
        latitude: float, 
        longitude: float,
        size: int = 1,
        use_cache: bool = True
    ) -> Dict:
        """
        Reverse geocode coordinates to get address information.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            size: Number of results to return
            use_cache: Whether to use cached results
            
        Returns:
            Dict containing reverse geocoding results with keys:
            - 'success': bool indicating if reverse geocoding was successful
            - 'address': str formatted address (if successful)
            - 'components': dict with address components
            - 'error': str error message (if unsuccessful)
        """
        try:
            # Validate coordinates
            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return {
                    'success': False,
                    'error': f'Invalid coordinate ranges: lat={latitude}, lon={longitude}'
                }
            
            # Check cache first
            if use_cache:
                cached_result = self._get_cached_result(latitude, longitude)
                if cached_result:
                    logger.info(f"Using cached reverse geocoding result for: {latitude}, {longitude}")
                    return cached_result
            
            # Prepare request parameters
            params = {
                'point.lat': latitude,
                'point.lon': longitude,
                'size': size,
                'layers': 'address,venue,street'
            }
            
            last_error = None
            
            for attempt in range(self.DEFAULT_RETRIES + 1):
                try:
                    logger.info(f"Reverse geocoding attempt {attempt + 1}/{self.DEFAULT_RETRIES + 1} for: {latitude}, {longitude}")
                    
                    response = self.session.get(
                        self.BASE_URL,
                        params=params,
                        timeout=self.DEFAULT_TIMEOUT
                    )
                    
                    # Check for HTTP errors
                    response.raise_for_status()
                    
                    # Parse response
                    data = response.json()
                    result = self._parse_reverse_geocoding_response(data)
                    
                    # Cache successful results
                    if result['success'] and use_cache:
                        self._cache_result(latitude, longitude, result)
                    
                    return result
                    
                except requests.exceptions.Timeout as e:
                    last_error = f"Request timeout: {str(e)}"
                    logger.warning(f"Reverse geocoding timeout: {last_error}")
                    
                except requests.exceptions.HTTPError as e:
                    if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                        last_error = "Rate limit exceeded"
                        logger.warning(f"Rate limit hit, attempt {attempt + 1}")
                        if attempt < self.DEFAULT_RETRIES:
                            time.sleep(self.DEFAULT_RETRY_DELAY * (attempt + 1))
                            continue
                    else:
                        status_code = e.response.status_code if hasattr(e, 'response') and e.response else 'unknown'
                        last_error = f"HTTP error {status_code}: {str(e)}"
                        logger.error(f"HTTP error reverse geocoding: {last_error}")
                        break
                        
                except requests.exceptions.RequestException as e:
                    last_error = f"Request error: {str(e)}"
                    logger.error(f"Request error reverse geocoding: {last_error}")
                    
                except (ValueError, KeyError) as e:
                    last_error = f"Response parsing error: {str(e)}"
                    logger.error(f"Response parsing error: {last_error}")
                    break
                    
                # Wait before retry (except for the last attempt)
                if attempt < self.DEFAULT_RETRIES:
                    time.sleep(self.DEFAULT_RETRY_DELAY)
            
            # All attempts failed
            error_msg = f"Reverse geocoding failed after {self.DEFAULT_RETRIES + 1} attempts: {last_error}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _parse_reverse_geocoding_response(self, data: Dict) -> Dict:
        """
        Parse the OpenRouteService reverse geocoding response.
        
        Args:
            data: JSON response from OpenRouteService
            
        Returns:
            Parsed reverse geocoding result dictionary
        """
        try:
            features = data.get('features', [])
            
            if not features:
                return {
                    'success': False,
                    'error': 'No address found for coordinates'
                }
            
            # Get the best match (first result)
            feature = features[0]
            properties = feature.get('properties', {})
            
            # Get formatted address
            address = properties.get('label', 'Address not available')
            
            # Extract address components
            components = {
                'house_number': properties.get('housenumber', ''),
                'street': properties.get('street', ''),
                'locality': properties.get('locality', ''),
                'region': properties.get('region', ''),
                'country': properties.get('country', ''),
                'postal_code': properties.get('postalcode', ''),
                'confidence': properties.get('confidence', 0),
                'layer': properties.get('layer', 'unknown')
            }
            
            return {
                'success': True,
                'address': address,
                'components': components,
                'confidence': properties.get('confidence', 0)
            }
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            return {
                'success': False,
                'error': f'Error parsing reverse geocoding response: {str(e)}'
            }
    
    def _get_cache_key(self, latitude: float, longitude: float) -> str:
        """
        Generate a cache key for the reverse geocoding result.
        """
        content = f"{latitude:.6f},{longitude:.6f}"
        hash_object = hashlib.md5(content.encode())
        return f"reverse_geocoding:{hash_object.hexdigest()}"
    
    def _get_cached_result(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Retrieve cached reverse geocoding result.
        """
        cache_key = self._get_cache_key(latitude, longitude)
        return cache.get(cache_key)
    
    def _cache_result(self, latitude: float, longitude: float, result: Dict) -> None:
        """
        Cache a reverse geocoding result.
        """
        cache_key = self._get_cache_key(latitude, longitude)
        cache.set(cache_key, result, self.CACHE_TIMEOUT)