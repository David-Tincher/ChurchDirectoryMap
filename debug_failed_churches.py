#!/usr/bin/env python3
"""
Debug script to find which churches failed to import and why.
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'church_map_project.settings')
django.setup()

from import_ohio_churches_with_coords import parse_ohio_churches_file

def debug_churches():
    """
    Debug which churches failed and why.
    """
    churches = parse_ohio_churches_file('Ohio Churches.txt')
    print(f'Total parsed: {len(churches)}')
    print('=' * 80)
    
    failed_churches = []
    successful_churches = []
    
    for i, church in enumerate(churches, 1):
        name = church.get('name', '').strip()
        street_address = church.get('street_address', '').strip()
        city = church.get('city', '').strip()
        state = church.get('state', '').strip()
        
        has_required = bool(name and street_address and city and state)
        
        print(f'{i}. {church["name"]}')
        print(f'   Name: "{name}" (len: {len(name)})')
        print(f'   Street Address: "{street_address}" (len: {len(street_address)})')
        print(f'   City: "{city}" (len: {len(city)})')
        print(f'   State: "{state}" (len: {len(state)})')
        print(f'   Coordinates: {church["latitude"]}, {church["longitude"]}')
        print(f'   Has required fields: {has_required}')
        
        if has_required:
            successful_churches.append(church)
        else:
            failed_churches.append(church)
            print(f'   ❌ FAILED - Missing required fields')
        
        print()
    
    print('=' * 80)
    print(f'Summary:')
    print(f'  Successful: {len(successful_churches)}')
    print(f'  Failed: {len(failed_churches)}')
    
    if failed_churches:
        print(f'\nFailed churches:')
        for church in failed_churches:
            print(f'  - {church["name"]}')
            if not church.get('street_address', '').strip():
                print(f'    Missing street address')
            if not church.get('city', '').strip():
                print(f'    Missing city')
            if not church.get('state', '').strip():
                print(f'    Missing state')

if __name__ == "__main__":
    debug_churches()