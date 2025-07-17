#!/usr/bin/env python
"""
Custom script to import Ohio Churches from the specific text file format.
"""

import os
import sys
import django
import re
from typing import List, Dict, Optional

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_map_project.settings')
django.setup()

from churches.models import Church
from churches.services import ChurchDataService


def parse_ohio_churches_file(file_path: str) -> List[Dict]:
    """
    Parse the Ohio Churches.txt file with the specific format.
    
    Format:
    Church Name
    Address and Directions
    Street Address
    City, State Zip
    Worship Times
    Times...
    Contacts
    Contact info...
    
    (blank lines between churches)
    """
    churches = []
    
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Split by double newlines to separate churches
    church_blocks = content.split('\n\n\n')
    
    for block in church_blocks:
        if not block.strip():
            continue
            
        church_data = parse_church_block(block.strip())
        if church_data:
            churches.append(church_data)
    
    return churches


def parse_church_block(block: str) -> Optional[Dict]:
    """
    Parse a single church block.
    """
    lines = [line.strip() for line in block.split('\n') if line.strip()]
    
    if not lines:
        return None
    
    church_data = {
        'name': '',
        'street_address': '',
        'city': '',
        'state': 'OH',  # Default to Ohio
        'zip_code': '',
        'phone': '',
        'website': '',
        'email': '',
        'service_times': '',
        'is_active': True,
        'latitude': None,
        'longitude': None
    }
    
    # First line is always the church name
    church_data['name'] = lines[0]
    
    # Find sections
    current_section = None
    address_lines = []
    worship_times = []
    contacts = []
    
    for line in lines[1:]:
        # Check for coordinates line
        if line.startswith("coordinates:"):
            coords_str = line.replace("coordinates:", "").strip()
            try:
                lat_str, lng_str = coords_str.split(',')
                church_data['latitude'] = float(lat_str.strip())
                church_data['longitude'] = float(lng_str.strip())
                print(f"Found coordinates for {church_data['name']}: {church_data['latitude']}, {church_data['longitude']}")
            except (ValueError, IndexError) as e:
                print(f"Error parsing coordinates for {church_data['name']}: {coords_str} - {e}")
            continue
        elif line == "Address and Directions":
            current_section = "address"
            continue
        elif line == "Worship Times":
            current_section = "worship"
            continue
        elif line == "Contacts":
            current_section = "contacts"
            continue
        elif line.startswith("Website URL:"):
            church_data['website'] = line.replace("Website URL:", "").strip()
            continue
        
        # Process based on current section
        if current_section == "address":
            address_lines.append(line)
        elif current_section == "worship":
            worship_times.append(line)
        elif current_section == "contacts":
            contacts.append(line)
    
    # Parse address
    if address_lines:
        church_data.update(parse_address(address_lines))
    
    # Parse worship times
    if worship_times:
        church_data['service_times'] = '; '.join(worship_times)
    
    # Parse contacts for phone and email
    if contacts:
        contact_info = parse_contacts(contacts)
        church_data.update(contact_info)
    
    return church_data


def parse_address(address_lines: List[str]) -> Dict:
    """
    Parse address lines to extract street, city, state, zip.
    """
    address_data = {
        'street_address': '',
        'city': '',
        'state': 'OH',
        'zip_code': ''
    }
    
    # Look for the main address components
    street_parts = []
    
    for line in address_lines:
        # Skip "USA" lines
        if line == "USA":
            continue
            
        # Check if line contains city, state, zip pattern
        city_state_zip_match = re.search(r'^(.+?),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)?(?:\s+USA)?$', line)
        if city_state_zip_match:
            address_data['city'] = city_state_zip_match.group(1).strip()
            address_data['state'] = city_state_zip_match.group(2).strip()
            if city_state_zip_match.group(3):
                address_data['zip_code'] = city_state_zip_match.group(3).strip()
        else:
            # Check if it's just a city, state line
            city_state_match = re.search(r'^(.+?),\s*([A-Z]{2})(?:\s+USA)?$', line)
            if city_state_match:
                address_data['city'] = city_state_match.group(1).strip()
                address_data['state'] = city_state_match.group(2).strip()
            else:
                # Assume it's part of the street address
                if not line.startswith('P.O. Box') or not street_parts:
                    street_parts.append(line)
    
    # Join street parts
    if street_parts:
        address_data['street_address'] = ', '.join(street_parts)
    
    return address_data


def parse_contacts(contact_lines: List[str]) -> Dict:
    """
    Parse contact lines to extract phone and email.
    """
    contact_data = {
        'phone': '',
        'email': ''
    }
    
    phones = []
    emails = []
    
    for line in contact_lines:
        # Look for phone numbers
        phone_match = re.search(r'1-(\d{3}-\d{3}-\d{4})', line)
        if phone_match:
            phones.append(f"({phone_match.group(1)[:3]}) {phone_match.group(1)[4:]}")
        
        # Look for emails
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
        if email_match:
            emails.append(email_match.group())
    
    # Take the first phone and email found
    if phones:
        contact_data['phone'] = phones[0]
    if emails:
        contact_data['email'] = emails[0]
    
    return contact_data


def import_churches(churches_data: List[Dict], clear_existing: bool = False) -> Dict:
    """
    Import churches into the database with coordinates.
    """
    if clear_existing:
        print("Clearing existing churches...")
        Church.objects.all().delete()
        print(f"Cleared {Church.objects.count()} existing churches")
    
    # Import churches directly with coordinates
    total = len(churches_data)
    created = 0
    updated = 0
    failed = 0
    failed_records = []
    
    print(f"Starting import of {total} church records with coordinates")
    
    for i, data in enumerate(churches_data, 1):
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
                    'is_active': data.get('is_active', True),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'geocoding_accuracy': 'high' if data.get('latitude') and data.get('longitude') else 'medium'
                }
            )
            
            if was_created:
                created += 1
                coord_info = f" (Coords: {data.get('latitude')}, {data.get('longitude')})" if data.get('latitude') else ""
                print(f"✓ Created: {church.name}{coord_info}")
            else:
                # Update existing church with new data including coordinates
                church.zip_code = data.get('zip_code', church.zip_code)
                church.phone = data.get('phone', church.phone)
                church.website = data.get('website', church.website)
                church.email = data.get('email', church.email)
                church.service_times = data.get('service_times', church.service_times)
                church.is_active = data.get('is_active', church.is_active)
                
                # Update coordinates if provided
                if data.get('latitude') and data.get('longitude'):
                    church.latitude = data.get('latitude')
                    church.longitude = data.get('longitude')
                    church.geocoding_accuracy = 'high'
                
                church.save()
                updated += 1
                coord_info = f" (Coords: {data.get('latitude')}, {data.get('longitude')})" if data.get('latitude') else ""
                print(f"✓ Updated: {church.name}{coord_info}")
            
        except Exception as e:
            failed += 1
            failed_records.append({
                'index': i,
                'data': data,
                'error': str(e)
            })
            print(f"✗ Failed to import record {i}: {str(e)}")
    
    summary = {
        'success': True,
        'message': f'Import completed: {created} created, {updated} updated, {failed} failed',
        'total': total,
        'created': created,
        'updated': updated,
        'failed': failed,
        'failed_records': failed_records
    }
    
    print(summary['message'])
    return summary


def main():
    """
    Main function to run the import.
    """
    file_path = "Ohio Churches.txt"
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found!")
        return
    
    print(f"Parsing Ohio Churches from '{file_path}'...")
    
    try:
        churches_data = parse_ohio_churches_file(file_path)
        print(f"Parsed {len(churches_data)} churches")
        
        # Show preview of first few churches
        print("\nPreview of parsed churches:")
        print("-" * 60)
        for i, church in enumerate(churches_data[:3]):
            print(f"{i+1}. {church['name']}")
            print(f"   Address: {church['street_address']}")
            print(f"   City: {church['city']}, {church['state']} {church['zip_code']}")
            print(f"   Phone: {church['phone']}")
            print(f"   Email: {church['email']}")
            print(f"   Service Times: {church['service_times']}")
            print()
        
        if len(churches_data) > 3:
            print(f"... and {len(churches_data) - 3} more churches")
        
        # Ask for confirmation
        response = input(f"\nImport {len(churches_data)} churches? (y/N): ").strip().lower()
        if response in ['y', 'yes']:
            print("\nImporting churches...")
            result = import_churches(churches_data, clear_existing=True)
            
            print(f"\n✅ Import completed!")
            print(f"   Created: {result['created']} churches")
            print(f"   Updated: {result['updated']} churches")
            print(f"   Failed: {result['failed']} churches")
            
            if result['failed'] > 0:
                print(f"\nFailed records:")
                for failed in result['failed_records'][:5]:  # Show first 5 failures
                    print(f"   - {failed.get('error', 'Unknown error')}")
            
            # Check if coordinates were provided
            churches_with_coords = sum(1 for church in churches_data if church.get('latitude') and church.get('longitude'))
            if churches_with_coords > 0:
                print(f"\n✅ Using provided coordinates for {churches_with_coords} churches!")
                print("No geocoding needed - coordinates were imported directly.")
            else:
                # Offer to geocode if no coordinates provided
                geocode_response = input(f"\nGeocode addresses to get map coordinates? (y/N): ").strip().lower()
                if geocode_response in ['y', 'yes']:
                    print("Starting geocoding process...")
                    service = ChurchDataService()
                    geocode_result = service.geocode_all_churches()
                    
                    print(f"\n✅ Geocoding completed!")
                    print(f"   Successful: {geocode_result['successful']} churches")
                    print(f"   Failed: {geocode_result['failed']} churches")
                    print(f"   Skipped: {geocode_result['skipped']} churches")
        else:
            print("Import cancelled.")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()