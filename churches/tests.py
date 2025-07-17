from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.management import call_command
from django.core.cache import cache
from decimal import Decimal
import math
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import requests
from .models import Church
from .services import GeocodingService, ChurchDataService, GeocodingError
from .serializers import (
    ChurchSerializer,
    ChurchListSerializer,
    ChurchMapSerializer,
    ChurchSearchSerializer
)


class ChurchModelTest(TestCase):
    """
    Test suite for the Church model functionality.
    """
    
    def setUp(self):
        """
        Set up test data for Church model tests.
        """
        self.valid_church_data = {
            'name': 'Test Church',
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State',
            'zip_code': '12345',
            'latitude': Decimal('40.7128'),
            'longitude': Decimal('-74.0060'),
            'phone': '555-123-4567',
            'website': 'https://testchurch.org',
            'email': 'info@testchurch.org',
            'service_times': 'Sunday 10:00 AM, Wednesday 7:00 PM',
            'geocoding_accuracy': 'high'
        }
    
    def test_church_creation_with_valid_data(self):
        """
        Test creating a church with valid data.
        """
        church = Church.objects.create(**self.valid_church_data)
        
        self.assertEqual(church.name, 'Test Church')
        self.assertEqual(church.street_address, '123 Main St')
        self.assertEqual(church.city, 'Test City')
        self.assertEqual(church.state, 'Test State')
        self.assertEqual(church.zip_code, '12345')
        self.assertEqual(church.latitude, Decimal('40.7128'))
        self.assertEqual(church.longitude, Decimal('-74.0060'))
        self.assertEqual(church.phone, '555-123-4567')
        self.assertEqual(church.website, 'https://testchurch.org')
        self.assertEqual(church.email, 'info@testchurch.org')
        self.assertEqual(church.service_times, 'Sunday 10:00 AM, Wednesday 7:00 PM')
        self.assertEqual(church.geocoding_accuracy, 'high')
        self.assertTrue(church.is_active)
        self.assertIsNotNone(church.created_at)
        self.assertIsNotNone(church.updated_at)
    
    def test_church_str_representation(self):
        """
        Test the string representation of a Church instance.
        """
        church = Church.objects.create(**self.valid_church_data)
        expected_str = "Test Church - Test City, Test State"
        self.assertEqual(str(church), expected_str)
    
    def test_required_field_validation(self):
        """
        Test validation of required fields.
        """
        # Test missing name
        data = self.valid_church_data.copy()
        data['name'] = ''
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test missing street address
        data = self.valid_church_data.copy()
        data['street_address'] = ''
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test missing city
        data = self.valid_church_data.copy()
        data['city'] = ''
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test missing state
        data = self.valid_church_data.copy()
        data['state'] = ''
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
    
    def test_coordinate_validation(self):
        """
        Test validation of coordinate ranges.
        """
        # Test invalid latitude (too high)
        data = self.valid_church_data.copy()
        data['latitude'] = Decimal('91.0')
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test invalid latitude (too low)
        data = self.valid_church_data.copy()
        data['latitude'] = Decimal('-91.0')
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test invalid longitude (too high)
        data = self.valid_church_data.copy()
        data['longitude'] = Decimal('181.0')
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test invalid longitude (too low)
        data = self.valid_church_data.copy()
        data['longitude'] = Decimal('-181.0')
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
    
    def test_coordinate_pair_validation(self):
        """
        Test that latitude and longitude must be provided together.
        """
        # Test latitude without longitude
        data = self.valid_church_data.copy()
        data['longitude'] = None
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test longitude without latitude
        data = self.valid_church_data.copy()
        data['latitude'] = None
        church = Church(**data)
        with self.assertRaises(ValidationError):
            church.full_clean()
        
        # Test both None (should be valid)
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church = Church(**data)
        church.full_clean()  # Should not raise an exception
    
    def test_full_address_property(self):
        """
        Test the full_address property.
        """
        church = Church.objects.create(**self.valid_church_data)
        expected_address = "123 Main St, Test City, Test State, 12345"
        self.assertEqual(church.full_address, expected_address)
        
        # Test without zip code
        data = self.valid_church_data.copy()
        data['zip_code'] = ''
        church = Church.objects.create(**data)
        expected_address = "123 Main St, Test City, Test State"
        self.assertEqual(church.full_address, expected_address)
    
    def test_coordinates_property(self):
        """
        Test the coordinates property.
        """
        church = Church.objects.create(**self.valid_church_data)
        coordinates = church.coordinates
        self.assertEqual(coordinates, (40.7128, -74.0060))
        
        # Test without coordinates
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church = Church.objects.create(**data)
        self.assertIsNone(church.coordinates)
    
    def test_has_coordinates_property(self):
        """
        Test the has_coordinates property.
        """
        church = Church.objects.create(**self.valid_church_data)
        self.assertTrue(church.has_coordinates)
        
        # Test without coordinates
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church = Church.objects.create(**data)
        self.assertFalse(church.has_coordinates)
    
    def test_set_coordinates_method(self):
        """
        Test the set_coordinates method.
        """
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church = Church.objects.create(**data)
        
        # Set valid coordinates
        church.set_coordinates(40.7128, -74.0060, 'high')
        self.assertEqual(church.latitude, Decimal('40.7128000'))
        self.assertEqual(church.longitude, Decimal('-74.0060000'))
        self.assertEqual(church.geocoding_accuracy, 'high')
        
        # Test invalid latitude
        with self.assertRaises(ValueError):
            church.set_coordinates(91.0, -74.0060)
        
        # Test invalid longitude
        with self.assertRaises(ValueError):
            church.set_coordinates(40.7128, 181.0)
        
        # Test invalid accuracy
        with self.assertRaises(ValueError):
            church.set_coordinates(40.7128, -74.0060, 'invalid')
    
    def test_haversine_distance_calculation(self):
        """
        Test the Haversine distance calculation method.
        """
        # Create two churches with known coordinates
        church1_data = self.valid_church_data.copy()
        church1_data['name'] = 'Church 1'
        church1_data['latitude'] = Decimal('40.7128')  # New York
        church1_data['longitude'] = Decimal('-74.0060')
        church1 = Church.objects.create(**church1_data)
        
        church2_data = self.valid_church_data.copy()
        church2_data['name'] = 'Church 2'
        church2_data['latitude'] = Decimal('34.0522')  # Los Angeles
        church2_data['longitude'] = Decimal('-118.2437')
        church2 = Church.objects.create(**church2_data)
        
        # Calculate distance between NYC and LA (approximately 3944 km)
        distance = church1.distance_to(church2)
        self.assertIsNotNone(distance)
        self.assertAlmostEqual(distance, 3944, delta=50)  # Allow 50km tolerance
    
    def test_distance_to_point_method(self):
        """
        Test the distance_to_point method.
        """
        church = Church.objects.create(**self.valid_church_data)
        
        # Distance to same point should be 0
        distance = church.distance_to_point(40.7128, -74.0060)
        self.assertAlmostEqual(distance, 0, delta=0.1)
        
        # Distance to Los Angeles
        distance = church.distance_to_point(34.0522, -118.2437)
        self.assertAlmostEqual(distance, 3944, delta=50)
        
        # Test with church without coordinates
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church_no_coords = Church.objects.create(**data)
        distance = church_no_coords.distance_to_point(34.0522, -118.2437)
        self.assertIsNone(distance)
    
    def test_distance_between_churches_without_coordinates(self):
        """
        Test distance calculation when churches don't have coordinates.
        """
        # Create church without coordinates
        data = self.valid_church_data.copy()
        data['latitude'] = None
        data['longitude'] = None
        church1 = Church.objects.create(**data)
        
        church2 = Church.objects.create(**self.valid_church_data)
        
        # Distance should be None when one church lacks coordinates
        distance = church1.distance_to(church2)
        self.assertIsNone(distance)
    
    def test_find_nearby_churches(self):
        """
        Test the find_nearby class method.
        """
        # Create multiple churches
        church1_data = self.valid_church_data.copy()
        church1_data['name'] = 'Nearby Church 1'
        church1_data['latitude'] = Decimal('40.7128')  # New York
        church1_data['longitude'] = Decimal('-74.0060')
        church1 = Church.objects.create(**church1_data)
        
        church2_data = self.valid_church_data.copy()
        church2_data['name'] = 'Nearby Church 2'
        church2_data['latitude'] = Decimal('40.7589')  # Close to NYC
        church2_data['longitude'] = Decimal('-73.9851')
        church2 = Church.objects.create(**church2_data)
        
        church3_data = self.valid_church_data.copy()
        church3_data['name'] = 'Far Church'
        church3_data['latitude'] = Decimal('34.0522')  # Los Angeles
        church3_data['longitude'] = Decimal('-118.2437')
        church3 = Church.objects.create(**church3_data)
        
        # Find churches near NYC within 50km
        nearby_churches = Church.find_nearby(40.7128, -74.0060, 50)
        nearby_names = [church.name for church in nearby_churches]
        
        self.assertIn('Nearby Church 1', nearby_names)
        self.assertIn('Nearby Church 2', nearby_names)
        self.assertNotIn('Far Church', nearby_names)
    
    def test_find_nearby_excludes_inactive_churches(self):
        """
        Test that find_nearby excludes inactive churches.
        """
        # Create active church
        active_church_data = self.valid_church_data.copy()
        active_church_data['name'] = 'Active Church'
        active_church = Church.objects.create(**active_church_data)
        
        # Create inactive church
        inactive_church_data = self.valid_church_data.copy()
        inactive_church_data['name'] = 'Inactive Church'
        inactive_church_data['is_active'] = False
        inactive_church = Church.objects.create(**inactive_church_data)
        
        # Find nearby churches
        nearby_churches = Church.find_nearby(40.7128, -74.0060, 50)
        nearby_names = [church.name for church in nearby_churches]
        
        self.assertIn('Active Church', nearby_names)
        self.assertNotIn('Inactive Church', nearby_names)
    
    def test_model_ordering(self):
        """
        Test that churches are ordered by state, city, name.
        """
        # Create churches in different states/cities
        church1_data = self.valid_church_data.copy()
        church1_data['name'] = 'B Church'
        church1_data['state'] = 'Alabama'
        church1_data['city'] = 'Birmingham'
        church1 = Church.objects.create(**church1_data)
        
        church2_data = self.valid_church_data.copy()
        church2_data['name'] = 'A Church'
        church2_data['state'] = 'Alabama'
        church2_data['city'] = 'Birmingham'
        church2 = Church.objects.create(**church2_data)
        
        church3_data = self.valid_church_data.copy()
        church3_data['name'] = 'C Church'
        church3_data['state'] = 'California'
        church3_data['city'] = 'Los Angeles'
        church3 = Church.objects.create(**church3_data)
        
        churches = list(Church.objects.all())
        
        # Should be ordered: Alabama churches first (A Church, then B Church), then California
        self.assertEqual(churches[0].name, 'A Church')
        self.assertEqual(churches[1].name, 'B Church')
        self.assertEqual(churches[2].name, 'C Church')
    
    def test_model_indexes(self):
        """
        Test that the model has the expected database indexes.
        """
        # This test verifies that the model meta includes the expected indexes
        indexes = Church._meta.indexes
        
        # Check that we have indexes on state/city and lat/lng
        index_fields = [tuple(index.fields) for index in indexes]
        
        self.assertIn(('state', 'city'), index_fields)
        self.assertIn(('latitude', 'longitude'), index_fields)
    
    def test_geocoding_accuracy_choices(self):
        """
        Test that geocoding accuracy field accepts valid choices.
        """
        valid_accuracies = ['high', 'medium', 'low']
        
        for accuracy in valid_accuracies:
            data = self.valid_church_data.copy()
            data['geocoding_accuracy'] = accuracy
            church = Church.objects.create(**data)
            self.assertEqual(church.geocoding_accuracy, accuracy)
    
    def test_optional_fields_can_be_blank(self):
        """
        Test that optional fields can be left blank.
        """
        minimal_data = {
            'name': 'Minimal Church',
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State'
            # All other fields are optional
        }
        
        church = Church.objects.create(**minimal_data)
        self.assertEqual(church.name, 'Minimal Church')
        self.assertEqual(church.zip_code, '')
        self.assertIsNone(church.latitude)
        self.assertIsNone(church.longitude)
        self.assertEqual(church.phone, '')
        self.assertEqual(church.website, '')
        self.assertEqual(church.email, '')
        self.assertEqual(church.service_times, '')
        self.assertEqual(church.geocoding_accuracy, 'medium')  # Default value
        self.assertTrue(church.is_active)  # Default value


class ChurchModelEdgeCasesTest(TestCase):
    """
    Test edge cases and error conditions for the Church model.
    """
    
    def test_very_long_name_handling(self):
        """
        Test handling of very long church names.
        """
        long_name = 'A' * 200  # Exactly at the limit
        church_data = {
            'name': long_name,
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State'
        }
        
        church = Church.objects.create(**church_data)
        self.assertEqual(church.name, long_name)
        
        # Test name that's too long
        too_long_name = 'A' * 201
        church_data['name'] = too_long_name
        
        with self.assertRaises(Exception):  # Should raise a database error
            Church.objects.create(**church_data)
    
    def test_extreme_coordinate_values(self):
        """
        Test handling of extreme but valid coordinate values.
        """
        # Test extreme valid coordinates
        extreme_data = {
            'name': 'Extreme Church',
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State',
            'latitude': Decimal('90.0'),  # North Pole
            'longitude': Decimal('180.0')  # International Date Line
        }
        
        church = Church.objects.create(**extreme_data)
        self.assertEqual(church.latitude, Decimal('90.0'))
        self.assertEqual(church.longitude, Decimal('180.0'))
        
        # Test other extreme
        extreme_data['latitude'] = Decimal('-90.0')  # South Pole
        extreme_data['longitude'] = Decimal('-180.0')
        extreme_data['name'] = 'Extreme Church 2'
        
        church2 = Church.objects.create(**extreme_data)
        self.assertEqual(church2.latitude, Decimal('-90.0'))
        self.assertEqual(church2.longitude, Decimal('-180.0'))
    
    def test_whitespace_handling_in_required_fields(self):
        """
        Test that whitespace-only values in required fields are rejected.
        """
        # Test whitespace-only name
        church_data = {
            'name': '   ',  # Only whitespace
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State'
        }
        
        church = Church(**church_data)
        with self.assertRaises(ValidationError):
            church.full_clean()
    
    def test_unicode_handling(self):
        """
        Test handling of Unicode characters in text fields.
        """
        unicode_data = {
            'name': 'Église Saint-François',  # French church name
            'street_address': '123 Rue de la Paix',
            'city': 'Montréal',
            'state': 'Québec'
        }
        
        church = Church.objects.create(**unicode_data)
        self.assertEqual(church.name, 'Église Saint-François')
        self.assertEqual(church.city, 'Montréal')
    
    def test_precision_of_decimal_coordinates(self):
        """
        Test that coordinate precision is maintained correctly.
        """
        precise_data = {
            'name': 'Precise Church',
            'street_address': '123 Main St',
            'city': 'Test City',
            'state': 'Test State',
            'latitude': Decimal('40.1234567'),  # 7 decimal places
            'longitude': Decimal('-74.9876543')
        }
        
        church = Church.objects.create(**precise_data)
        self.assertEqual(church.latitude, Decimal('40.1234567'))
        self.assertEqual(church.longitude, Decimal('-74.9876543'))


class GeocodingServiceTest(TestCase):
    """
    Test suite for the GeocodingService functionality.
    """
    
    def setUp(self):
        """
        Set up test data for GeocodingService tests.
        """
        self.api_key = 'test_api_key_12345'
        self.service = GeocodingService(api_key=self.api_key)
        # Clear cache before each test to avoid interference
        cache.clear()
        
        # Sample successful geocoding response
        self.successful_response = {
            'features': [
                {
                    'geometry': {
                        'coordinates': [-74.0060, 40.7128]
                    },
                    'properties': {
                        'label': '123 Main St, New York, NY, USA',
                        'confidence': 0.9,
                        'layer': 'address'
                    }
                }
            ]
        }
        
        # Sample empty response
        self.empty_response = {
            'features': []
        }
    
    def test_service_initialization_with_api_key(self):
        """
        Test that the service initializes correctly with an API key.
        """
        service = GeocodingService(api_key='test_key')
        self.assertEqual(service.api_key, 'test_key')
        self.assertIsNotNone(service.session)
    
    def test_service_initialization_without_api_key_raises_error(self):
        """
        Test that initializing without an API key raises an error.
        """
        with self.assertRaises(GeocodingError):
            GeocodingService(api_key=None)
    
    @patch('churches.services.requests.Session.get')
    def test_successful_geocoding(self, mock_get):
        """
        Test successful geocoding of an address.
        """
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = self.successful_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service.geocode_address('123 Main St, New York, NY')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['latitude'], 40.7128)
        self.assertEqual(result['longitude'], -74.0060)
        self.assertEqual(result['accuracy'], 'high')
        self.assertEqual(result['formatted_address'], '123 Main St, New York, NY, USA')
        
        # Verify API call was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn('text', call_args[1]['params'])
        self.assertEqual(call_args[1]['params']['text'], '123 Main St, New York, NY')
    
    @patch('churches.services.requests.Session.get')
    def test_geocoding_no_results(self, mock_get):
        """
        Test geocoding when no results are found.
        """
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = self.empty_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service.geocode_address('Nonexistent Address')
        
        self.assertFalse(result['success'])
        self.assertIn('No results found', result['error'])
    
    @patch('churches.services.requests.Session.get')
    def test_geocoding_http_error(self, mock_get):
        """
        Test geocoding when HTTP error occurs.
        """
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        result = self.service.geocode_address('123 Main St')
        
        self.assertFalse(result['success'])
        self.assertIn('HTTP error', result['error'])
    
    @patch('churches.services.requests.Session.get')
    def test_geocoding_timeout(self, mock_get):
        """
        Test geocoding when request times out.
        """
        # Mock timeout
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        result = self.service.geocode_address('123 Main St', retries=1)
        
        self.assertFalse(result['success'])
        self.assertIn('timeout', result['error'])
    
    @patch('churches.services.requests.Session.get')
    def test_geocoding_rate_limit_with_retry(self, mock_get):
        """
        Test geocoding with rate limit and successful retry.
        """
        # First call returns rate limit error, second succeeds
        rate_limit_response = Mock()
        rate_limit_error = requests.exceptions.HTTPError()
        rate_limit_error.response = Mock()
        rate_limit_error.response.status_code = 429
        rate_limit_response.raise_for_status.side_effect = rate_limit_error
        
        success_response = Mock()
        success_response.json.return_value = self.successful_response
        success_response.raise_for_status.return_value = None
        
        mock_get.side_effect = [rate_limit_response, success_response]
        
        with patch('churches.services.time.sleep'):  # Mock sleep to speed up test
            result = self.service.geocode_address('123 Main St', retries=2)
        
        self.assertTrue(result['success'])
        self.assertEqual(mock_get.call_count, 2)
    
    @patch('churches.services.requests.Session.get')
    def test_geocoding_invalid_coordinates(self, mock_get):
        """
        Test geocoding when response contains invalid coordinates.
        """
        # Mock response with invalid coordinates
        invalid_response = {
            'features': [
                {
                    'geometry': {
                        'coordinates': [200, 100]  # Invalid longitude and latitude
                    },
                    'properties': {
                        'label': 'Invalid Location',
                        'confidence': 0.5,
                        'layer': 'address'
                    }
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.json.return_value = invalid_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.service.geocode_address('Invalid Address')
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid coordinate ranges', result['error'])
    
    def test_empty_address_handling(self):
        """
        Test handling of empty or whitespace-only addresses.
        """
        result = self.service.geocode_address('')
        self.assertFalse(result['success'])
        self.assertIn('cannot be empty', result['error'])
        
        result = self.service.geocode_address('   ')
        self.assertFalse(result['success'])
        self.assertIn('cannot be empty', result['error'])
    
    def test_accuracy_determination(self):
        """
        Test the accuracy determination logic.
        """
        # High accuracy: address layer with high confidence
        properties = {'layer': 'address', 'confidence': 0.9}
        accuracy = self.service._determine_accuracy(properties)
        self.assertEqual(accuracy, 'high')
        
        # Medium accuracy: street layer
        properties = {'layer': 'street', 'confidence': 0.6}
        accuracy = self.service._determine_accuracy(properties)
        self.assertEqual(accuracy, 'medium')
        
        # Medium accuracy: locality with decent confidence
        properties = {'layer': 'locality', 'confidence': 0.6}
        accuracy = self.service._determine_accuracy(properties)
        self.assertEqual(accuracy, 'medium')
        
        # Low accuracy: low confidence
        properties = {'layer': 'locality', 'confidence': 0.3}
        accuracy = self.service._determine_accuracy(properties)
        self.assertEqual(accuracy, 'low')
    
    @patch('churches.services.cache')
    def test_caching_functionality(self, mock_cache):
        """
        Test that geocoding results are cached properly.
        """
        # Mock cache miss, then cache set
        mock_cache.get.return_value = None
        mock_cache.set.return_value = None
        
        with patch('churches.services.requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = self.successful_response
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            result = self.service.geocode_address('123 Main St')
            
            # Verify cache was checked and result was cached
            mock_cache.get.assert_called_once()
            mock_cache.set.assert_called_once()
    
    @patch('churches.services.cache')
    def test_cache_hit(self, mock_cache):
        """
        Test that cached results are returned without API call.
        """
        # Mock cache hit
        cached_result = {
            'success': True,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 'high'
        }
        mock_cache.get.return_value = cached_result
        
        with patch('churches.services.requests.Session.get') as mock_get:
            result = self.service.geocode_address('123 Main St')
            
            # Verify cached result was returned and no API call was made
            self.assertEqual(result, cached_result)
            mock_get.assert_not_called()
    
    @patch('churches.services.requests.Session.get')
    def test_batch_geocoding(self, mock_get):
        """
        Test batch geocoding functionality.
        """
        # Mock successful responses
        mock_response = Mock()
        mock_response.json.return_value = self.successful_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        addresses = ['123 Main St', '456 Oak Ave', '789 Pine Rd']
        
        with patch('churches.services.time.sleep'):  # Mock sleep to speed up test
            results = self.service.geocode_batch(addresses, delay_between_requests=0.1)
        
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertTrue(result['success'])
        
        # Verify correct number of API calls
        self.assertEqual(mock_get.call_count, 3)
    
    def test_cache_key_generation(self):
        """
        Test that cache keys are generated consistently.
        """
        key1 = self.service._get_cache_key('123 Main St', 'US')
        key2 = self.service._get_cache_key('123 Main St', 'US')
        key3 = self.service._get_cache_key('456 Oak Ave', 'US')
        
        # Same address should generate same key
        self.assertEqual(key1, key2)
        
        # Different address should generate different key
        self.assertNotEqual(key1, key3)
        
        # Keys should start with 'geocoding:'
        self.assertTrue(key1.startswith('geocoding:'))


class ChurchDataServiceTest(TestCase):
    """
    Test suite for the ChurchDataService functionality.
    """
    
    def setUp(self):
        """
        Set up test data for ChurchDataService tests.
        """
        # Create a mock geocoding service
        self.mock_geocoding_service = Mock(spec=GeocodingService)
        self.data_service = ChurchDataService(geocoding_service=self.mock_geocoding_service)
        
        # Sample church data
        self.sample_church_data = [
            {
                'name': 'Test Church 1',
                'street_address': '123 Main St',
                'city': 'Test City',
                'state': 'Test State',
                'zip_code': '12345',
                'phone': '555-123-4567',
                'website': 'https://testchurch1.org',
                'email': 'info@testchurch1.org',
                'service_times': 'Sunday 10:00 AM',
                'is_active': True
            },
            {
                'name': 'Test Church 2',
                'street_address': '456 Oak Ave',
                'city': 'Another City',
                'state': 'Another State',
                'zip_code': '67890',
                'phone': '555-987-6543',
                'website': 'https://testchurch2.org',
                'email': 'contact@testchurch2.org',
                'service_times': 'Sunday 11:00 AM',
                'is_active': True
            }
        ]
    
    def test_import_church_data_success(self):
        """
        Test successful import of church data.
        """
        result = self.data_service.import_church_data(self.sample_church_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['created'], 2)
        self.assertEqual(result['updated'], 0)
        self.assertEqual(result['failed'], 0)
        
        # Verify churches were created
        self.assertEqual(Church.objects.count(), 2)
        
        church1 = Church.objects.get(name='Test Church 1')
        self.assertEqual(church1.street_address, '123 Main St')
        self.assertEqual(church1.city, 'Test City')
        self.assertEqual(church1.state, 'Test State')
    
    def test_import_church_data_update_existing(self):
        """
        Test updating existing church data during import.
        """
        # Create an existing church
        existing_church = Church.objects.create(
            name='Test Church 1',
            street_address='123 Main St',
            city='Test City',
            state='Test State',
            phone='555-000-0000'  # Different phone number
        )
        
        result = self.data_service.import_church_data(self.sample_church_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['created'], 1)  # Only one new church
        self.assertEqual(result['updated'], 1)  # One existing church updated
        self.assertEqual(result['failed'], 0)
        
        # Verify existing church was updated
        updated_church = Church.objects.get(name='Test Church 1')
        self.assertEqual(updated_church.phone, '555-123-4567')  # Should be updated
    
    def test_import_church_data_missing_required_fields(self):
        """
        Test import with missing required fields.
        """
        invalid_data = [
            {
                'name': 'Valid Church',
                'street_address': '123 Main St',
                'city': 'Test City',
                'state': 'Test State'
            },
            {
                'name': '',  # Missing name
                'street_address': '456 Oak Ave',
                'city': 'Test City',
                'state': 'Test State'
            },
            {
                'name': 'Another Church',
                'street_address': '789 Pine Rd',
                # Missing city and state
            }
        ]
        
        result = self.data_service.import_church_data(invalid_data)
        
        self.assertTrue(result['success'])  # Overall success even with some failures
        self.assertEqual(result['total'], 3)
        self.assertEqual(result['created'], 1)  # Only valid church created
        self.assertEqual(result['failed'], 2)  # Two invalid records
        
        # Verify only valid church was created
        self.assertEqual(Church.objects.count(), 1)
        self.assertEqual(Church.objects.first().name, 'Valid Church')
    
    def test_import_empty_data(self):
        """
        Test import with empty data list.
        """
        result = self.data_service.import_church_data([])
        
        self.assertFalse(result['success'])
        self.assertIn('No church data provided', result['message'])
        self.assertEqual(result['total'], 0)
    
    def test_geocode_church_success(self):
        """
        Test successful geocoding of a church.
        """
        # Create church without coordinates
        church = Church.objects.create(
            name='Test Church',
            street_address='123 Main St',
            city='Test City',
            state='Test State'
        )
        
        # Mock successful geocoding
        self.mock_geocoding_service.geocode_address.return_value = {
            'success': True,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 'high'
        }
        
        result = self.data_service.geocode_church(church)
        
        self.assertTrue(result['success'])
        self.assertIn('Successfully geocoded', result['message'])
        
        # Verify church coordinates were updated
        church.refresh_from_db()
        self.assertEqual(float(church.latitude), 40.7128)
        self.assertEqual(float(church.longitude), -74.0060)
        self.assertEqual(church.geocoding_accuracy, 'high')
    
    def test_geocode_church_already_has_coordinates(self):
        """
        Test geocoding a church that already has coordinates.
        """
        # Create church with coordinates
        church = Church.objects.create(
            name='Test Church',
            street_address='123 Main St',
            city='Test City',
            state='Test State',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060')
        )
        
        result = self.data_service.geocode_church(church)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['skipped'])
        self.assertIn('already has coordinates', result['message'])
        
        # Verify geocoding service was not called
        self.mock_geocoding_service.geocode_address.assert_not_called()
    
    def test_geocode_church_failure(self):
        """
        Test geocoding failure for a church.
        """
        # Create church without coordinates
        church = Church.objects.create(
            name='Test Church',
            street_address='123 Nonexistent St',
            city='Nowhere',
            state='NoState'
        )
        
        # Mock geocoding failure
        self.mock_geocoding_service.geocode_address.return_value = {
            'success': False,
            'error': 'Address not found'
        }
        
        result = self.data_service.geocode_church(church)
        
        self.assertFalse(result['success'])
        self.assertIn('Geocoding failed', result['message'])
        self.assertIn('Address not found', result['message'])
        
        # Verify church coordinates were not updated
        church.refresh_from_db()
        self.assertIsNone(church.latitude)
        self.assertIsNone(church.longitude)
    
    def test_geocode_all_churches(self):
        """
        Test geocoding all churches without coordinates.
        """
        # Create churches - some with coordinates, some without
        church1 = Church.objects.create(
            name='Church 1',
            street_address='123 Main St',
            city='Test City',
            state='Test State'
        )
        
        church2 = Church.objects.create(
            name='Church 2',
            street_address='456 Oak Ave',
            city='Test City',
            state='Test State',
            latitude=Decimal('40.7128'),  # Already has coordinates
            longitude=Decimal('-74.0060')
        )
        
        church3 = Church.objects.create(
            name='Church 3',
            street_address='789 Pine Rd',
            city='Test City',
            state='Test State'
        )
        
        # Mock geocoding responses
        self.mock_geocoding_service.geocode_address.side_effect = [
            {
                'success': True,
                'latitude': 40.7128,
                'longitude': -74.0060,
                'accuracy': 'high'
            },
            {
                'success': False,
                'error': 'Address not found'
            }
        ]
        
        result = self.data_service.geocode_all_churches()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 2)  # Only churches without coordinates
        self.assertEqual(result['successful'], 1)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['skipped'], 0)
        
        # Verify geocoding service was called twice (for churches without coordinates)
        self.assertEqual(self.mock_geocoding_service.geocode_address.call_count, 2)
    
    def test_geocode_all_churches_force_update(self):
        """
        Test geocoding all churches with force update.
        """
        # Create church with existing coordinates
        church = Church.objects.create(
            name='Test Church',
            street_address='123 Main St',
            city='Test City',
            state='Test State',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060')
        )
        
        # Mock successful geocoding
        self.mock_geocoding_service.geocode_address.return_value = {
            'success': True,
            'latitude': 41.0000,
            'longitude': -75.0000,
            'accuracy': 'high'
        }
        
        result = self.data_service.geocode_all_churches(force_update=True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['successful'], 1)
        
        # Verify coordinates were updated
        church.refresh_from_db()
        self.assertEqual(float(church.latitude), 41.0000)
        self.assertEqual(float(church.longitude), -75.0000)
    
    def test_geocode_all_churches_no_churches_to_geocode(self):
        """
        Test geocoding when no churches need geocoding.
        """
        # Create church with coordinates
        Church.objects.create(
            name='Test Church',
            street_address='123 Main St',
            city='Test City',
            state='Test State',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060')
        )
        
        result = self.data_service.geocode_all_churches()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total'], 0)
        self.assertIn('No churches need geocoding', result['message'])


class ManagementCommandTest(TestCase):
    """
    Test suite for the populate_churches management command.
    """
    
    def setUp(self):
        """
        Set up test data for management command tests.
        """
        self.sample_csv_data = """name,street_address,city,state,zip_code,phone,website
Test Church 1,123 Main St,Test City,Test State,12345,555-123-4567,https://test1.org
Test Church 2,456 Oak Ave,Another City,Another State,67890,555-987-6543,https://test2.org"""
        
        self.sample_json_data = [
            {
                'name': 'JSON Church 1',
                'street_address': '123 JSON St',
                'city': 'JSON City',
                'state': 'JSON State',
                'zip_code': '11111',
                'phone': '555-111-1111',
                'website': 'https://json1.org'
            },
            {
                'name': 'JSON Church 2',
                'street_address': '456 JSON Ave',
                'city': 'JSON City',
                'state': 'JSON State',
                'zip_code': '22222',
                'phone': '555-222-2222',
                'website': 'https://json2.org'
            }
        ]
    
    def test_populate_churches_sample_data(self):
        """
        Test populating churches with sample data.
        """
        # Run command with sample data
        call_command('populate_churches', source='sample', verbosity=0)
        
        # Verify churches were created
        self.assertEqual(Church.objects.count(), 5)  # Sample data has 5 churches
        
        # Verify specific church
        atlanta_church = Church.objects.get(name='New Testament Church of Atlanta')
        self.assertEqual(atlanta_church.city, 'Atlanta')
        self.assertEqual(atlanta_church.state, 'Georgia')
    
    def test_populate_churches_csv_file(self):
        """
        Test populating churches from CSV file.
        """
        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(self.sample_csv_data)
            csv_file_path = f.name
        
        try:
            # Run command with CSV file
            call_command('populate_churches', source='csv', file=csv_file_path, verbosity=0)
            
            # Verify churches were created
            self.assertEqual(Church.objects.count(), 2)
            
            # Verify specific church
            church1 = Church.objects.get(name='Test Church 1')
            self.assertEqual(church1.street_address, '123 Main St')
            self.assertEqual(church1.phone, '555-123-4567')
            
        finally:
            # Clean up temporary file
            os.unlink(csv_file_path)
    
    def test_populate_churches_json_file(self):
        """
        Test populating churches from JSON file.
        """
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.sample_json_data, f)
            json_file_path = f.name
        
        try:
            # Run command with JSON file
            call_command('populate_churches', source='json', file=json_file_path, verbosity=0)
            
            # Verify churches were created
            self.assertEqual(Church.objects.count(), 2)
            
            # Verify specific church
            church1 = Church.objects.get(name='JSON Church 1')
            self.assertEqual(church1.street_address, '123 JSON St')
            self.assertEqual(church1.phone, '555-111-1111')
            
        finally:
            # Clean up temporary file
            os.unlink(json_file_path)
    
    def test_populate_churches_dry_run(self):
        """
        Test dry run mode doesn't create churches.
        """
        # Run command in dry run mode
        call_command('populate_churches', source='sample', dry_run=True, verbosity=0)
        
        # Verify no churches were created
        self.assertEqual(Church.objects.count(), 0)
    
    def test_populate_churches_clear_existing(self):
        """
        Test clearing existing churches before import.
        """
        # Create existing church
        Church.objects.create(
            name='Existing Church',
            street_address='123 Existing St',
            city='Existing City',
            state='Existing State'
        )
        
        self.assertEqual(Church.objects.count(), 1)
        
        # Run command with clear existing
        call_command('populate_churches', source='sample', clear_existing=True, verbosity=0)
        
        # Verify existing church was cleared and new ones created
        self.assertEqual(Church.objects.count(), 5)  # Sample data churches
        self.assertFalse(Church.objects.filter(name='Existing Church').exists())
    
    @patch('churches.services.GeocodingService')
    def test_populate_churches_with_geocoding(self, MockGeocodingService):
        """
        Test populating churches with automatic geocoding.
        """
        # Mock the geocoding service
        mock_geocoding_instance = Mock()
        mock_geocoding_instance.geocode_address.return_value = {
            'success': True,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 'high'
        }
        MockGeocodingService.return_value = mock_geocoding_instance
        
        # Run command with geocoding
        call_command('populate_churches', source='sample', geocode=True, verbosity=0)
        
        # Verify churches were created and geocoded
        self.assertEqual(Church.objects.count(), 5)
        
        # Verify at least one church has coordinates
        geocoded_churches = Church.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        self.assertGreater(geocoded_churches.count(), 0)
    
    def test_populate_churches_invalid_file_path(self):
        """
        Test command with invalid file path.
        """
        with self.assertRaises(Exception):
            call_command('populate_churches', source='csv', file='/nonexistent/file.csv')
    
    def test_populate_churches_missing_file_argument(self):
        """
        Test command with missing file argument for CSV/JSON sources.
        """
        with self.assertRaises(Exception):
            call_command('populate_churches', source='csv')  # Missing --file argument


class IntegrationTest(TestCase):
    """
    Integration tests that test the complete workflow.
    """
    
    @patch('churches.services.requests.Session.get')
    def test_complete_workflow_import_and_geocode(self, mock_get):
        """
        Test complete workflow: import churches and geocode them.
        """
        # Mock successful geocoding response
        mock_response = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'geometry': {
                        'coordinates': [-74.0060, 40.7128]
                    },
                    'properties': {
                        'label': 'Geocoded Address',
                        'confidence': 0.9,
                        'layer': 'address'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Import sample data
        call_command('populate_churches', source='sample', verbosity=0)
        
        # Verify churches were created without coordinates
        churches_without_coords = Church.objects.filter(
            latitude__isnull=True,
            longitude__isnull=True
        )
        self.assertEqual(churches_without_coords.count(), 5)
        
        # Geocode all churches
        with patch('churches.services.GeocodingService') as MockGeocodingService:
            mock_geocoding_instance = Mock()
            mock_geocoding_instance.geocode_address.return_value = {
                'success': True,
                'latitude': 40.7128,
                'longitude': -74.0060,
                'accuracy': 'high'
            }
            MockGeocodingService.return_value = mock_geocoding_instance
            
            data_service = ChurchDataService()
            result = data_service.geocode_all_churches()
        
        # Verify geocoding was successful
        self.assertTrue(result['success'])
        self.assertEqual(result['successful'], 5)
        
        # Verify all churches now have coordinates
        churches_with_coords = Church.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        self.assertEqual(churches_with_coords.count(), 5)
    
    def test_error_handling_and_recovery(self):
        """
        Test error handling and recovery in various scenarios.
        """
        # Test with invalid church data
        invalid_data = [
            {
                'name': 'Valid Church',
                'street_address': '123 Main St',
                'city': 'Test City',
                'state': 'Test State'
            },
            {
                'name': '',  # Invalid: empty name
                'street_address': '456 Oak Ave',
                'city': 'Test City',
                'state': 'Test State'
            }
        ]
        
        data_service = ChurchDataService()
        result = data_service.import_church_data(invalid_data)
        
        # Should handle errors gracefully
        self.assertTrue(result['success'])
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['failed'], 1)
        
        # Valid church should still be created
        self.assertTrue(Church.objects.filter(name='Valid Church').exists())

class ChurchAPITest(TestCase):
    """
    Test suite for Church API endpoints.
    """
    
    def setUp(self):
        """
        Set up test data for API tests.
        """
        # Create test churches
        self.church1 = Church.objects.create(
            name='Test Church 1',
            street_address='123 Main St',
            city='New York',
            state='New York',
            zip_code='10001',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            phone='555-123-4567',
            website='https://testchurch1.org',
            email='info@testchurch1.org',
            service_times='Sunday 10:00 AM',
            geocoding_accuracy='high'
        )
        
        self.church2 = Church.objects.create(
            name='Test Church 2',
            street_address='456 Oak Ave',
            city='Los Angeles',
            state='California',
            zip_code='90210',
            latitude=Decimal('34.0522'),
            longitude=Decimal('-118.2437'),
            phone='555-987-6543',
            website='https://testchurch2.org',
            service_times='Sunday 11:00 AM',
            geocoding_accuracy='medium'
        )
        
        # Church without coordinates
        self.church3 = Church.objects.create(
            name='Test Church 3',
            street_address='789 Pine Rd',
            city='Chicago',
            state='Illinois',
            zip_code='60601',
            phone='555-555-5555'
        )
        
        # Inactive church
        self.church4 = Church.objects.create(
            name='Inactive Church',
            street_address='999 Inactive St',
            city='Inactive City',
            state='Inactive State',
            is_active=False
        )
    
    def test_church_list_api(self):
        """
        Test the church list API endpoint.
        """
        response = self.client.get('/api/churches/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should return paginated results
        self.assertIn('results', data)
        self.assertIn('count', data)
        
        # Should return 3 active churches
        self.assertEqual(data['count'], 3)
        
        # Check first church data
        church_data = data['results'][0]
        expected_fields = ['id', 'name', 'city', 'state', 'coordinates', 'phone', 'website']
        for field in expected_fields:
            self.assertIn(field, church_data)
        
        # Check coordinates format
        if church_data['coordinates']:
            self.assertIn('lat', church_data['coordinates'])
            self.assertIn('lng', church_data['coordinates'])
    
    def test_church_list_api_filtering(self):
        """
        Test filtering in the church list API.
        """
        # Filter by state
        response = self.client.get('/api/churches/?state=New York')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'Test Church 1')
        
        # Filter by city
        response = self.client.get('/api/churches/?city=Los Angeles')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['name'], 'Test Church 2')
        
        # Filter by has_coordinates
        response = self.client.get('/api/churches/?has_coordinates=true')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)  # Only churches with coordinates
    
    def test_church_detail_api(self):
        """
        Test the church detail API endpoint.
        """
        response = self.client.get(f'/api/churches/{self.church1.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check all expected fields are present
        expected_fields = [
            'id', 'name', 'street_address', 'city', 'state', 'zip_code',
            'full_address', 'latitude', 'longitude', 'coordinates',
            'has_coordinates', 'phone', 'website', 'email', 'service_times',
            'geocoding_accuracy', 'is_active', 'created_at', 'updated_at'
        ]
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check specific values
        self.assertEqual(data['name'], 'Test Church 1')
        self.assertEqual(data['city'], 'New York')
        self.assertEqual(data['state'], 'New York')
        self.assertTrue(data['has_coordinates'])
        self.assertEqual(data['coordinates']['lat'], 40.7128)
        self.assertEqual(data['coordinates']['lng'], -74.0060)
    
    def test_church_detail_api_not_found(self):
        """
        Test church detail API with non-existent church.
        """
        response = self.client.get('/api/churches/99999/')
        self.assertEqual(response.status_code, 404)
    
    def test_church_detail_api_inactive_church(self):
        """
        Test church detail API with inactive church.
        """
        response = self.client.get(f'/api/churches/{self.church4.id}/')
        self.assertEqual(response.status_code, 404)
    
    def test_church_map_api(self):
        """
        Test the church map API endpoint.
        """
        response = self.client.get('/api/churches/map/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should return list without pagination
        self.assertIsInstance(data, list)
        
        # Should only return churches with coordinates
        self.assertEqual(len(data), 2)
        
        # Check minimal fields are present
        for church_data in data:
            expected_fields = ['id', 'name', 'city', 'state', 'coordinates']
            for field in expected_fields:
                self.assertIn(field, church_data)
            
            # All churches should have coordinates
            self.assertIsNotNone(church_data['coordinates'])
            self.assertIn('lat', church_data['coordinates'])
            self.assertIn('lng', church_data['coordinates'])
    
    def test_church_search_api_by_coordinates(self):
        """
        Test church search API with coordinates.
        """
        # Search near New York (should find Test Church 1)
        response = self.client.get('/api/churches/search/?lat=40.7128&lng=-74.0060&radius=10')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('results', data)
        self.assertGreater(data['count'], 0)
        
        # Check that distance is included
        church_data = data['results'][0]
        self.assertIn('distance', church_data)
        self.assertIsNotNone(church_data['distance'])
    
    def test_church_search_api_by_text(self):
        """
        Test church search API with text query.
        """
        # Search by church name
        response = self.client.get('/api/churches/search/?q=Test Church 1')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('results', data)
        self.assertGreater(data['count'], 0)
        self.assertEqual(data['results'][0]['name'], 'Test Church 1')
        
        # Search by city
        response = self.client.get('/api/churches/search/?q=Los Angeles')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertGreater(data['count'], 0)
        self.assertEqual(data['results'][0]['city'], 'Los Angeles')
    
    @patch('churches.views.GeocodingService')
    def test_church_search_api_geocoding(self, MockGeocodingService):
        """
        Test church search API with geocoding fallback.
        """
        # Mock geocoding service
        mock_geocoding_instance = Mock()
        mock_geocoding_instance.geocode_address.return_value = {
            'success': True,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 'high'
        }
        MockGeocodingService.return_value = mock_geocoding_instance
        
        # Search with address that doesn't match any church names
        response = self.client.get('/api/churches/search/?q=123 Unknown Street, New York')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should have attempted geocoding
        mock_geocoding_instance.geocode_address.assert_called_once()
    
    def test_church_search_api_no_results(self):
        """
        Test church search API with no matching results.
        """
        response = self.client.get('/api/churches/search/?q=Nonexistent Church')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['count'], 0)
        self.assertEqual(len(data['results']), 0)
    
    def test_church_search_api_invalid_coordinates(self):
        """
        Test church search API with invalid coordinates.
        """
        response = self.client.get('/api/churches/search/?lat=invalid&lng=also_invalid')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should return empty results for invalid coordinates
        self.assertEqual(data['count'], 0)
    
    def test_church_stats_api(self):
        """
        Test the church statistics API endpoint.
        """
        response = self.client.get('/api/churches/stats/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check expected fields
        expected_fields = ['total_churches', 'churches_with_coordinates', 'geocoding_percentage', 'states']
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check values
        self.assertEqual(data['total_churches'], 3)  # 3 active churches
        self.assertEqual(data['churches_with_coordinates'], 2)  # 2 with coordinates
        self.assertEqual(data['geocoding_percentage'], 66.7)  # 2/3 * 100
        
        # Check state statistics
        self.assertIn('states', data)
        self.assertIn('New York', data['states'])
        self.assertIn('California', data['states'])
        self.assertIn('Illinois', data['states'])
        
        # Check state data structure
        ny_stats = data['states']['New York']
        self.assertIn('total', ny_stats)
        self.assertIn('with_coordinates', ny_stats)
        self.assertIn('geocoding_percentage', ny_stats)


class ChurchSerializerTest(TestCase):
    """
    Test suite for Church serializers.
    """
    
    def setUp(self):
        """
        Set up test data for serializer tests.
        """
        self.church_with_coords = Church.objects.create(
            name='Test Church',
            street_address='123 Main St',
            city='Test City',
            state='Test State',
            zip_code='12345',
            latitude=Decimal('40.7128'),
            longitude=Decimal('-74.0060'),
            phone='555-123-4567',
            website='https://testchurch.org',
            email='info@testchurch.org',
            service_times='Sunday 10:00 AM',
            geocoding_accuracy='high'
        )
        
        self.church_without_coords = Church.objects.create(
            name='Test Church 2',
            street_address='456 Oak Ave',
            city='Another City',
            state='Another State'
        )
    
    def test_church_serializer(self):
        """
        Test the full ChurchSerializer.
        """
        serializer = ChurchSerializer(self.church_with_coords)
        data = serializer.data
        
        # Check all expected fields are present
        expected_fields = [
            'id', 'name', 'street_address', 'city', 'state', 'zip_code',
            'full_address', 'latitude', 'longitude', 'coordinates',
            'has_coordinates', 'phone', 'website', 'email', 'service_times',
            'geocoding_accuracy', 'is_active', 'created_at', 'updated_at'
        ]
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check coordinates format
        self.assertIsNotNone(data['coordinates'])
        self.assertEqual(data['coordinates']['lat'], 40.7128)
        self.assertEqual(data['coordinates']['lng'], -74.0060)
        self.assertTrue(data['has_coordinates'])
    
    def test_church_serializer_without_coordinates(self):
        """
        Test ChurchSerializer with church that has no coordinates.
        """
        serializer = ChurchSerializer(self.church_without_coords)
        data = serializer.data
        
        self.assertIsNone(data['coordinates'])
        self.assertFalse(data['has_coordinates'])
        self.assertIsNone(data['latitude'])
        self.assertIsNone(data['longitude'])
    
    def test_church_list_serializer(self):
        """
        Test the ChurchListSerializer.
        """
        serializer = ChurchListSerializer(self.church_with_coords)
        data = serializer.data
        
        # Check only expected fields are present
        expected_fields = ['id', 'name', 'city', 'state', 'coordinates', 'phone', 'website']
        self.assertEqual(set(data.keys()), set(expected_fields))
        
        # Check coordinates format
        self.assertIsNotNone(data['coordinates'])
        self.assertEqual(data['coordinates']['lat'], 40.7128)
        self.assertEqual(data['coordinates']['lng'], -74.0060)
    
    def test_church_map_serializer(self):
        """
        Test the ChurchMapSerializer.
        """
        serializer = ChurchMapSerializer(self.church_with_coords)
        data = serializer.data
        
        # Check only minimal fields are present
        expected_fields = ['id', 'name', 'city', 'state', 'coordinates']
        self.assertEqual(set(data.keys()), set(expected_fields))
        
        # Check coordinates format
        self.assertIsNotNone(data['coordinates'])
        self.assertEqual(data['coordinates']['lat'], 40.7128)
        self.assertEqual(data['coordinates']['lng'], -74.0060)
    
    def test_church_search_serializer(self):
        """
        Test the ChurchSearchSerializer.
        """
        # Add distance attribute to simulate search result
        self.church_with_coords.distance = 5.2
        
        serializer = ChurchSearchSerializer(self.church_with_coords)
        data = serializer.data
        
        # Check expected fields are present
        expected_fields = [
            'id', 'name', 'street_address', 'city', 'state', 'zip_code',
            'coordinates', 'distance', 'phone', 'website', 'service_times'
        ]
        for field in expected_fields:
            self.assertIn(field, data)
        
        # Check distance is included
        self.assertEqual(data['distance'], 5.2)
        
        # Check coordinates format
        self.assertIsNotNone(data['coordinates'])
        self.assertEqual(data['coordinates']['lat'], 40.7128)
        self.assertEqual(data['coordinates']['lng'], -74.0060)
    
    def test_church_search_serializer_without_distance(self):
        """
        Test ChurchSearchSerializer without distance attribute.
        """
        serializer = ChurchSearchSerializer(self.church_with_coords)
        data = serializer.data
        
        # Distance should be None if not set
        self.assertIsNone(data['distance'])


class OpenRouteServiceAPITest(TestCase):
    """
    Test suite for OpenRouteService integration API endpoints.
    """
    
    def setUp(self):
        """
        Set up test data for OpenRouteService API tests.
        """
        # Sample successful geocoding response
        self.successful_geocoding_response = {
            'features': [
                {
                    'geometry': {
                        'coordinates': [-74.0060, 40.7128]
                    },
                    'properties': {
                        'label': '123 Main St, New York, NY, USA',
                        'confidence': 0.9,
                        'layer': 'address'
                    }
                }
            ]
        }
        
        # Sample successful directions response
        self.successful_directions_response = {
            'routes': [
                {
                    'summary': {
                        'distance': 5000.0,  # meters
                        'duration': 600.0    # seconds
                    },
                    'geometry': 'encoded_geometry_string',
                    'segments': [
                        {
                            'steps': [
                                {'instruction': 'Head north on Main St'},
                                {'instruction': 'Turn right on Oak Ave'}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Sample successful reverse geocoding response
        self.successful_reverse_geocoding_response = {
            'features': [
                {
                    'properties': {
                        'label': '123 Main St, New York, NY 10001, USA',
                        'housenumber': '123',
                        'street': 'Main St',
                        'locality': 'New York',
                        'region': 'NY',
                        'country': 'USA',
                        'postalcode': '10001',
                        'confidence': 0.95,
                        'layer': 'address'
                    }
                }
            ]
        }
    
    @patch('churches.views.GeocodingService')
    def test_geocoding_api_success(self, MockGeocodingService):
        """
        Test successful geocoding API request.
        """
        # Mock the geocoding service
        mock_geocoding_instance = Mock()
        mock_geocoding_instance.geocode_address.return_value = {
            'success': True,
            'latitude': 40.7128,
            'longitude': -74.0060,
            'accuracy': 'high',
            'formatted_address': '123 Main St, New York, NY, USA',
            'confidence': 0.9
        }
        MockGeocodingService.return_value = mock_geocoding_instance
        
        # Make API request
        response = self.client.post('/api/geocoding/', {
            'address': '123 Main St, New York, NY'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertTrue(data['success'])
        self.assertIn('coordinates', data)
        self.assertEqual(data['coordinates']['latitude'], 40.7128)
        self.assertEqual(data['coordinates']['longitude'], -74.0060)
        self.assertEqual(data['accuracy'], 'high')
        self.assertEqual(data['formatted_address'], '123 Main St, New York, NY, USA')
        self.assertEqual(data['confidence'], 0.9)
    
    def test_geocoding_api_missing_address(self):
        """
        Test geocoding API with missing address.
        """
        response = self.client.post('/api/geocoding/', {}, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Address is required', data['error'])
    
    @patch('churches.views.GeocodingService')
    def test_geocoding_api_service_error(self, MockGeocodingService):
        """
        Test geocoding API when service returns error.
        """
        # Mock the geocoding service to return error
        mock_geocoding_instance = Mock()
        mock_geocoding_instance.geocode_address.return_value = {
            'success': False,
            'error': 'No results found for address'
        }
        MockGeocodingService.return_value = mock_geocoding_instance
        
        response = self.client.post('/api/geocoding/', {
            'address': 'Nonexistent Address'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)
    
    @patch('churches.services.requests.Session.post')
    def test_directions_api_success(self, mock_post):
        """
        Test successful directions API request.
        """
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = self.successful_directions_response
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        # Make API request
        response = self.client.post('/api/directions/', {
            'start': {'latitude': 40.7128, 'longitude': -74.0060},
            'end': {'latitude': 34.0522, 'longitude': -118.2437},
            'profile': 'driving-car'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertTrue(data['success'])
        self.assertEqual(data['distance'], 5000.0)
        self.assertEqual(data['duration'], 600.0)
        self.assertEqual(data['geometry'], 'encoded_geometry_string')
        self.assertIsInstance(data['instructions'], list)
        self.assertEqual(len(data['instructions']), 2)
    
    def test_directions_api_missing_coordinates(self):
        """
        Test directions API with missing coordinates.
        """
        response = self.client.post('/api/directions/', {
            'start': {'latitude': 40.7128, 'longitude': -74.0060}
            # Missing 'end' coordinates
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Both start and end coordinates are required', data['error'])
    
    def test_directions_api_invalid_coordinates(self):
        """
        Test directions API with invalid coordinates.
        """
        response = self.client.post('/api/directions/', {
            'start': {'latitude': 'invalid', 'longitude': -74.0060},
            'end': {'latitude': 34.0522, 'longitude': -118.2437}
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Coordinates must be valid numbers', data['error'])
    
    def test_directions_api_incomplete_coordinates(self):
        """
        Test directions API with incomplete coordinate data.
        """
        response = self.client.post('/api/directions/', {
            'start': {'latitude': 40.7128},  # Missing longitude
            'end': {'latitude': 34.0522, 'longitude': -118.2437}
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Invalid coordinates provided', data['error'])
    
    @patch('churches.services.requests.Session.get')
    def test_reverse_geocoding_api_success(self, mock_get):
        """
        Test successful reverse geocoding API request.
        """
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = self.successful_reverse_geocoding_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Make API request
        response = self.client.post('/api/reverse-geocoding/', {
            'latitude': 40.7128,
            'longitude': -74.0060
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertTrue(data['success'])
        self.assertEqual(data['address'], '123 Main St, New York, NY 10001, USA')
        self.assertEqual(data['confidence'], 0.95)
        
        # Check address components
        components = data['components']
        self.assertEqual(components['house_number'], '123')
        self.assertEqual(components['street'], 'Main St')
        self.assertEqual(components['locality'], 'New York')
        self.assertEqual(components['region'], 'NY')
        self.assertEqual(components['country'], 'USA')
        self.assertEqual(components['postal_code'], '10001')
    
    def test_reverse_geocoding_api_missing_coordinates(self):
        """
        Test reverse geocoding API with missing coordinates.
        """
        response = self.client.post('/api/reverse-geocoding/', {
            'latitude': 40.7128
            # Missing longitude
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Both latitude and longitude are required', data['error'])
    
    def test_reverse_geocoding_api_invalid_coordinates(self):
        """
        Test reverse geocoding API with invalid coordinates.
        """
        response = self.client.post('/api/reverse-geocoding/', {
            'latitude': 'invalid',
            'longitude': -74.0060
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Coordinates must be valid numbers', data['error'])
    
    @patch('churches.services.requests.Session.get')
    def test_reverse_geocoding_api_no_results(self, mock_get):
        """
        Test reverse geocoding API when no results are found.
        """
        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {'features': []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        response = self.client.post('/api/reverse-geocoding/', {
            'latitude': 0.0,
            'longitude': 0.0
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error', data)


class OpenRouteServiceIntegrationTest(TestCase):
    """
    Integration tests for OpenRouteService services.
    """
    
    @patch('churches.services.requests.Session.get')
    def test_directions_service_integration(self, mock_get):
        """
        Test DirectionsService integration.
        """
        from churches.services import DirectionsService
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'routes': [
                {
                    'summary': {
                        'distance': 1000.0,
                        'duration': 120.0
                    },
                    'geometry': 'test_geometry',
                    'segments': [
                        {
                            'steps': [
                                {'instruction': 'Start journey'}
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        
        # Mock the POST request for directions
        with patch('churches.services.requests.Session.post') as mock_post:
            mock_post.return_value = mock_response
            
            # Test with mocked API key
            with patch('churches.services.getattr') as mock_getattr:
                mock_getattr.return_value = 'test_api_key'
                
                service = DirectionsService()
                result = service.get_directions(
                    start_coords=(-74.0060, 40.7128),
                    end_coords=(-118.2437, 34.0522)
                )
                
                self.assertTrue(result['success'])
                self.assertEqual(result['distance'], 1000.0)
                self.assertEqual(result['duration'], 120.0)
                self.assertEqual(result['geometry'], 'test_geometry')
    
    @patch('churches.services.requests.Session.get')
    def test_reverse_geocoding_service_integration(self, mock_get):
        """
        Test ReverseGeocodingService integration.
        """
        from churches.services import ReverseGeocodingService
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        'label': 'Test Address',
                        'housenumber': '123',
                        'street': 'Test St',
                        'locality': 'Test City',
                        'region': 'Test State',
                        'country': 'Test Country',
                        'postalcode': '12345',
                        'confidence': 0.8,
                        'layer': 'address'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test with mocked API key
        with patch('churches.services.getattr') as mock_getattr:
            mock_getattr.return_value = 'test_api_key'
            
            service = ReverseGeocodingService()
            result = service.reverse_geocode(40.7128, -74.0060)
            
            self.assertTrue(result['success'])
            self.assertEqual(result['address'], 'Test Address')
            self.assertEqual(result['confidence'], 0.8)
            
            # Check components
            components = result['components']
            self.assertEqual(components['house_number'], '123')
            self.assertEqual(components['street'], 'Test St')
            self.assertEqual(components['locality'], 'Test City')
    
    def test_service_initialization_without_api_key(self):
        """
        Test that services raise error when no API key is provided.
        """
        from churches.services import DirectionsService, ReverseGeocodingService, GeocodingError
        
        with patch('churches.services.getattr') as mock_getattr:
            mock_getattr.return_value = None
            
            with self.assertRaises(GeocodingError):
                DirectionsService()
            
            with self.assertRaises(GeocodingError):
                ReverseGeocodingService()
    
    @patch('churches.services.requests.Session.get')
    def test_service_error_handling(self, mock_get):
        """
        Test error handling in services.
        """
        from churches.services import ReverseGeocodingService
        
        # Mock HTTP error
        mock_get.side_effect = requests.exceptions.HTTPError("404 Not Found")
        
        with patch('churches.services.getattr') as mock_getattr:
            mock_getattr.return_value = 'test_api_key'
            
            service = ReverseGeocodingService()
            result = service.reverse_geocode(40.7128, -74.0060)
            
            self.assertFalse(result['success'])
            self.assertIn('error', result)
    
    @patch('churches.services.requests.Session.get')
    def test_service_caching(self, mock_get):
        """
        Test that services cache results properly.
        """
        from churches.services import ReverseGeocodingService
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            'features': [
                {
                    'properties': {
                        'label': 'Cached Address',
                        'confidence': 0.9,
                        'layer': 'address'
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with patch('churches.services.getattr') as mock_getattr:
            mock_getattr.return_value = 'test_api_key'
            
            service = ReverseGeocodingService()
            
            # First call should make HTTP request
            result1 = service.reverse_geocode(40.7128, -74.0060)
            self.assertTrue(result1['success'])
            self.assertEqual(mock_get.call_count, 1)
            
            # Second call should use cache (no additional HTTP request)
            result2 = service.reverse_geocode(40.7128, -74.0060)
            self.assertTrue(result2['success'])
            # Should still be 1 because second call used cache
            self.assertEqual(mock_get.call_count, 1)