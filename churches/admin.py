from django.contrib import admin
from .models import Church


@admin.register(Church)
class ChurchAdmin(admin.ModelAdmin):
    """
    Admin interface for Church model with optimized display and filtering.
    """
    
    list_display = [
        'name', 
        'city', 
        'state', 
        'has_coordinates', 
        'geocoding_accuracy',
        'is_active',
        'updated_at'
    ]
    
    list_filter = [
        'state',
        'geocoding_accuracy',
        'is_active',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'name',
        'city',
        'state',
        'street_address'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'full_address',
        'coordinates'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active')
        }),
        ('Address', {
            'fields': ('street_address', 'city', 'state', 'zip_code', 'full_address')
        }),
        ('Coordinates', {
            'fields': ('latitude', 'longitude', 'coordinates', 'geocoding_accuracy'),
            'description': 'Geographic coordinates for mapping. Both latitude and longitude must be provided together.'
        }),
        ('Contact Information', {
            'fields': ('phone', 'website', 'email'),
            'classes': ('collapse',)
        }),
        ('Service Information', {
            'fields': ('service_times',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    ordering = ['state', 'city', 'name']
    
    def has_coordinates(self, obj):
        """Display whether the church has coordinates."""
        return obj.has_coordinates
    has_coordinates.boolean = True
    has_coordinates.short_description = 'Has Coordinates'
