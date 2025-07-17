from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
import math

# Check if PostGIS is available and database supports it
try:
    from django.contrib.gis.db import models as gis_models
    from django.contrib.gis.geos import Point
    from django.contrib.gis.measure import Distance
    from django.conf import settings
    
    # Check if we're using a GIS-enabled database backend
    db_engine = settings.DATABASES['default']['ENGINE']
    HAS_POSTGIS = 'gis' in db_engine or 'postgis' in db_engine
except (ImportError, KeyError):
    HAS_POSTGIS = False


class Church(models.Model):
    """
    Church model that supports both PostGIS and non-PostGIS configurations.
    Stores church location data with address, coordinates, and contact information.
    """
    
    # Basic church information
    name = models.CharField(
        max_length=200,
        help_text="Official name of the church"
    )
    
    # Address fields
    street_address = models.CharField(
        max_length=300,
        help_text="Street address of the church"
    )
    city = models.CharField(
        max_length=100,
        help_text="City where the church is located"
    )
    state = models.CharField(
        max_length=50,
        help_text="State where the church is located"
    )
    zip_code = models.CharField(
        max_length=10,
        blank=True,
        help_text="ZIP code of the church location"
    )
    
    # Coordinate fields (for non-PostGIS setup)
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90.0),
            MaxValueValidator(90.0)
        ],
        help_text="Latitude coordinate (-90 to 90)"
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180.0),
            MaxValueValidator(180.0)
        ],
        help_text="Longitude coordinate (-180 to 180)"
    )
    
    # PostGIS point field (only used if PostGIS is available)
    if HAS_POSTGIS:
        location = gis_models.PointField(
            null=True,
            blank=True,
            help_text="Geographic location point (PostGIS)"
        )
    
    # Contact information
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Church phone number"
    )
    website = models.URLField(
        blank=True,
        help_text="Church website URL"
    )
    email = models.EmailField(
        blank=True,
        help_text="Church email address"
    )
    
    # Service information
    service_times = models.TextField(
        blank=True,
        help_text="Service times and schedule information"
    )
    
    # Geocoding metadata
    geocoding_accuracy = models.CharField(
        max_length=10,
        choices=[
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium',
        help_text="Accuracy level of geocoded coordinates"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status fields
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the church is currently active"
    )
    
    class Meta:
        verbose_name = "Church"
        verbose_name_plural = "Churches"
        ordering = ['state', 'city', 'name']
        indexes = [
            models.Index(fields=['state', 'city']),
            models.Index(fields=['latitude', 'longitude']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"
    
    def clean(self):
        """
        Custom validation for the Church model.
        """
        super().clean()
        
        # Validate that both latitude and longitude are provided together
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError(
                "Both latitude and longitude must be provided together, or both left empty."
            )
        
        # Validate coordinate ranges
        if self.latitude is not None:
            if not (-90 <= float(self.latitude) <= 90):
                raise ValidationError(
                    "Latitude must be between -90 and 90 degrees."
                )
        
        if self.longitude is not None:
            if not (-180 <= float(self.longitude) <= 180):
                raise ValidationError(
                    "Longitude must be between -180 and 180 degrees."
                )
        
        # Validate required fields
        if not self.name.strip():
            raise ValidationError("Church name is required.")
        
        if not self.street_address.strip():
            raise ValidationError("Street address is required.")
        
        if not self.city.strip():
            raise ValidationError("City is required.")
        
        if not self.state.strip():
            raise ValidationError("State is required.")
    
    def save(self, *args, **kwargs):
        """
        Override save method to sync PostGIS location with lat/lng coordinates.
        """
        # Sync PostGIS location field with latitude/longitude if PostGIS is available
        if HAS_POSTGIS and self.latitude is not None and self.longitude is not None:
            self.location = Point(float(self.longitude), float(self.latitude))
        
        # Call clean method before saving
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    @property
    def full_address(self):
        """
        Returns the complete formatted address.
        """
        address_parts = [self.street_address, self.city, self.state]
        if self.zip_code:
            address_parts.append(self.zip_code)
        return ", ".join(part.strip() for part in address_parts if part.strip())
    
    @property
    def coordinates(self):
        """
        Returns coordinates as a tuple (latitude, longitude) or None if not available.
        """
        if self.latitude is not None and self.longitude is not None:
            return (float(self.latitude), float(self.longitude))
        return None
    
    @property
    def has_coordinates(self):
        """
        Returns True if the church has valid coordinates.
        """
        return self.coordinates is not None
    
    def distance_to(self, other_church):
        """
        Calculate distance to another church using PostGIS if available,
        otherwise use Haversine formula.
        
        Args:
            other_church: Another Church instance
            
        Returns:
            Distance in kilometers, or None if coordinates are missing
        """
        if not self.has_coordinates or not other_church.has_coordinates:
            return None
        
        # Use PostGIS distance calculation if available
        if HAS_POSTGIS and self.location and other_church.location:
            distance = self.location.distance(other_church.location)
            # Convert to kilometers (PostGIS returns distance in degrees by default)
            return distance * 111.32  # Approximate km per degree
        
        # Fallback to Haversine formula for non-PostGIS setup
        return self._haversine_distance(
            self.latitude, self.longitude,
            other_church.latitude, other_church.longitude
        )
    
    def distance_to_point(self, latitude, longitude):
        """
        Calculate distance to a specific point using PostGIS if available,
        otherwise use Haversine formula.
        
        Args:
            latitude: Target latitude
            longitude: Target longitude
            
        Returns:
            Distance in kilometers, or None if coordinates are missing
        """
        if not self.has_coordinates:
            return None
        
        # Use PostGIS distance calculation if available
        if HAS_POSTGIS and self.location:
            target_point = Point(float(longitude), float(latitude))
            distance = self.location.distance(target_point)
            # Convert to kilometers
            return distance * 111.32
        
        # Fallback to Haversine formula
        return self._haversine_distance(
            self.latitude, self.longitude,
            latitude, longitude
        )
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points on Earth
        using the Haversine formula.
        
        Args:
            lat1, lon1: Latitude and longitude of first point
            lat2, lon2: Latitude and longitude of second point
            
        Returns:
            Distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [
            float(lat1), float(lon1), float(lat2), float(lon2)
        ])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of Earth in kilometers
        r = 6371
        
        return c * r
    
    @classmethod
    def find_nearby(cls, latitude, longitude, radius_km=50):
        """
        Find churches within a specified radius of a given point.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_km: Search radius in kilometers (default: 50)
            
        Returns:
            QuerySet of nearby churches
        """
        if HAS_POSTGIS:
            # Use PostGIS for efficient spatial queries
            center_point = Point(float(longitude), float(latitude))
            # Convert km to degrees (approximate)
            radius_degrees = radius_km / 111.32
            return cls.objects.filter(
                location__distance_lte=(center_point, Distance(km=radius_km))
            ).filter(is_active=True)
        else:
            # Fallback: Use bounding box approximation for non-PostGIS
            # This is less accurate but much faster than calculating distance for every church
            lat_delta = radius_km / 111.32  # Approximate degrees per km
            lon_delta = radius_km / (111.32 * math.cos(math.radians(float(latitude))))
            
            return cls.objects.filter(
                latitude__range=(float(latitude) - lat_delta, float(latitude) + lat_delta),
                longitude__range=(float(longitude) - lon_delta, float(longitude) + lon_delta),
                is_active=True
            )
    
    def set_coordinates(self, latitude, longitude, accuracy='medium'):
        """
        Set coordinates for the church with validation.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            accuracy: Geocoding accuracy level ('high', 'medium', 'low')
        """
        from decimal import Decimal
        
        # Validate coordinates
        if not (-90 <= float(latitude) <= 90):
            raise ValueError("Latitude must be between -90 and 90 degrees.")
        
        if not (-180 <= float(longitude) <= 180):
            raise ValueError("Longitude must be between -180 and 180 degrees.")
        
        if accuracy not in ['high', 'medium', 'low']:
            raise ValueError("Accuracy must be 'high', 'medium', or 'low'.")
        
        # Convert to Decimal with proper precision (7 decimal places)
        self.latitude = Decimal(str(latitude)).quantize(Decimal('0.0000001'))
        self.longitude = Decimal(str(longitude)).quantize(Decimal('0.0000001'))
        self.geocoding_accuracy = accuracy
        
        # Update PostGIS location if available
        if HAS_POSTGIS:
            self.location = Point(float(longitude), float(latitude))
