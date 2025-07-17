#!/usr/bin/env python
"""
Script to fix church addresses and improve geocoding accuracy.
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_map_project.settings')
django.setup()

from churches.models import Church
from churches.services import ChurchDataService


def fix_addresses():
    """
    Fix problematic addresses for better geocoding accuracy.
    """
    fixes = [
        {
            'name': 'Family Church of Christ',
            'street_address': '1302 Leo St',  # Remove website URL
            'city': 'Dayton',
            'state': 'OH',
            'zip_code': '45404'
        },
        {
            'name': 'Goshen Church of Christ', 
            'street_address': '1869 Mulberry Street',  # Remove website URL
            'city': 'Goshen',
            'state': 'OH',
            'zip_code': '45122'
        },
        {
            'name': 'Hamilton Church of Christ',
            # P.O. Box addresses are problematic, let's try to find a better address
            # This church is in West Chester, OH - let's use a more specific address
            'street_address': '4844 Tylersville Rd',  # From contact info in original data
            'city': 'West Chester',
            'state': 'OH',
            'zip_code': '45069'
        },
        {
            'name': 'Chesapeake Church of Christ',
            'street_address': '901 3rd Avenue',
            'city': 'Chesapeake',
            'state': 'OH',
            'zip_code': '45619'  # Adding likely zip code for Chesapeake, OH
        },
        {
            'name': 'Proctorville Church of Christ',
            'street_address': '505 State Street',
            'city': 'Proctorville', 
            'state': 'OH',
            'zip_code': '45669'  # From original data
        },
        {
            'name': 'Sharonville Church of Christ',
            'street_address': '11560 Lippleman Road',
            'city': 'Sharonville',
            'state': 'OH', 
            'zip_code': '45241'  # Adding likely zip code for Sharonville, OH
        }
    ]
    
    updated_count = 0
    
    for fix in fixes:
        try:
            church = Church.objects.get(name=fix['name'])
            
            # Update address fields
            church.street_address = fix['street_address']
            church.city = fix['city']
            church.state = fix['state']
            church.zip_code = fix['zip_code']
            
            # Clear coordinates so they'll be re-geocoded
            church.latitude = None
            church.longitude = None
            church.geocoding_accuracy = 'medium'
            
            church.save()
            updated_count += 1
            print(f"✓ Fixed address for: {church.name}")
            print(f"  New address: {church.full_address}")
            
        except Church.DoesNotExist:
            print(f"✗ Church not found: {fix['name']}")
        except Exception as e:
            print(f"✗ Error updating {fix['name']}: {str(e)}")
    
    print(f"\nUpdated {updated_count} church addresses")
    return updated_count


def main():
    """
    Main function to fix addresses and re-geocode.
    """
    print("Fixing church addresses for better geocoding accuracy...")
    
    # Fix the addresses
    updated_count = fix_addresses()
    
    if updated_count > 0:
        # Re-geocode the updated churches
        print(f"\nRe-geocoding {updated_count} churches with fixed addresses...")
        
        service = ChurchDataService()
        result = service.geocode_all_churches()
        
        print(f"\n✅ Re-geocoding completed!")
        print(f"   Successful: {result['successful']} churches")
        print(f"   Failed: {result['failed']} churches")
        print(f"   Skipped: {result['skipped']} churches")
        
        if result['failed'] > 0:
            print(f"\nFailed churches:")
            for failed in result['failed_churches']:
                print(f"   - {failed['church']}: {failed['error']}")
    
    print("\n🎯 Refresh your browser to see the improved church locations!")


if __name__ == "__main__":
    main()