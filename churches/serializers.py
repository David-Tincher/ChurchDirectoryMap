"""
Serializers for the churches API endpoints.
"""

from rest_framework import serializers
from .models import Church


class ChurchSerializer(serializers.ModelSerializer):
    """
    Serializer for Church model with all fields for detailed views.
    """
    coordinates = serializers.SerializerMethodField()
    full_address = serializers.ReadOnlyField()
    has_coordinates = serializers.ReadOnlyField()
    
    class Meta:
        model = Church
        fields = [
            'id',
            'name',
            'street_address',
            'city',
            'state',
            'zip_code',
            'full_address',
            'latitude',
            'longitude',
            'coordinates',
            'has_coordinates',
            'phone',
            'website',
            'email',
            'service_times',
            'geocoding_accuracy',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_coordinates(self, obj):
        """
        Return coordinates as a dictionary with lat/lng keys for frontend convenience.
        """
        if obj.has_coordinates:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude)
            }
        return None


class ChurchListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for church list views with essential fields only.
    """
    coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = Church
        fields = [
            'id',
            'name',
            'city',
            'state',
            'coordinates',
            'phone',
            'website'
        ]
    
    def get_coordinates(self, obj):
        """
        Return coordinates as a dictionary with lat/lng keys.
        """
        if obj.has_coordinates:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude)
            }
        return None


class ChurchMapSerializer(serializers.ModelSerializer):
    """
    Serializer optimized for map display with essential fields for popups.
    """
    coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = Church
        fields = [
            'id',
            'name',
            'street_address',
            'city',
            'state',
            'zip_code',
            'coordinates',
            'phone',
            'website',
            'email',
            'service_times'
        ]
    
    def get_coordinates(self, obj):
        """
        Return coordinates as a dictionary with lat/lng keys.
        """
        if obj.has_coordinates:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude)
            }
        return None


class ChurchSearchSerializer(serializers.ModelSerializer):
    """
    Serializer for search results with distance information.
    """
    coordinates = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    
    class Meta:
        model = Church
        fields = [
            'id',
            'name',
            'street_address',
            'city',
            'state',
            'zip_code',
            'coordinates',
            'distance',
            'phone',
            'website',
            'service_times'
        ]
    
    def get_coordinates(self, obj):
        """
        Return coordinates as a dictionary with lat/lng keys.
        """
        if obj.has_coordinates:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude)
            }
        return None
    
    def get_distance(self, obj):
        """
        Return distance from search point if available.
        This will be set by the view when performing location-based searches.
        """
        return getattr(obj, 'distance', None)