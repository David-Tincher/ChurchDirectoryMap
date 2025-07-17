"""
Django management command to populate church data from various sources.
This command can import church data from CSV files, JSON files, or other data sources.
"""

import csv
import json
import os
from typing import Dict, List, Optional
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from churches.models import Church
from churches.services import ChurchDataService, GeocodingService


class Command(BaseCommand):
    help = 'Populate church data from external sources (CSV, JSON, or directory scraping)'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--source',
            type=str,
            choices=['csv', 'json', 'sample'],
            default='sample',
            help='Data source type (csv, json, or sample for demo data)'
        )
        
        parser.add_argument(
            '--file',
            type=str,
            help='Path to the data file (required for csv and json sources)'
        )
        
        parser.add_argument(
            '--geocode',
            action='store_true',
            help='Automatically geocode addresses after import'
        )
        
        parser.add_argument(
            '--force-geocode',
            action='store_true',
            help='Force re-geocoding of churches that already have coordinates'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing church data before import (use with caution!)'
        )
    
    def handle(self, *args, **options):
        """Main command handler."""
        try:
            # Validate arguments
            if options['source'] in ['csv', 'json'] and not options['file']:
                raise CommandError(f"--file argument is required when using {options['source']} source")
            
            if options['file'] and not os.path.exists(options['file']):
                raise CommandError(f"File not found: {options['file']}")
            
            # Clear existing data if requested
            if options['clear_existing']:
                if options['dry_run']:
                    self.stdout.write("DRY RUN: Would clear all existing church data")
                else:
                    count = Church.objects.count()
                    Church.objects.all().delete()
                    self.stdout.write(
                        self.style.WARNING(f"Cleared {count} existing church records")
                    )
            
            # Load data based on source type
            if options['source'] == 'csv':
                church_data = self._load_from_csv(options['file'])
            elif options['source'] == 'json':
                church_data = self._load_from_json(options['file'])
            elif options['source'] == 'sample':
                church_data = self._generate_sample_data()
            else:
                raise CommandError(f"Unsupported source type: {options['source']}")
            
            if not church_data:
                self.stdout.write(self.style.WARNING("No church data found to import"))
                return
            
            self.stdout.write(f"Found {len(church_data)} church records to process")
            
            # Show preview in dry run mode
            if options['dry_run']:
                self._show_dry_run_preview(church_data)
                return
            
            # Import the data (without geocoding service if not needed)
            if options['geocode'] or options['force_geocode']:
                # Only create geocoding service if we need it
                data_service = ChurchDataService()
            else:
                # Create data service without geocoding service for import-only operations
                data_service = ChurchDataService(geocoding_service=None)
            
            import_result = data_service.import_church_data(church_data)
            
            # Display import results
            self._display_import_results(import_result)
            
            # Geocode if requested
            if options['geocode'] or options['force_geocode']:
                self.stdout.write("\nStarting geocoding process...")
                geocoding_result = data_service.geocode_all_churches(
                    force_update=options['force_geocode']
                )
                self._display_geocoding_results(geocoding_result)
            
        except Exception as e:
            raise CommandError(f"Command failed: {str(e)}")
    
    def _load_from_csv(self, file_path: str) -> List[Dict]:
        """Load church data from CSV file."""
        church_data = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Try to detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Map CSV columns to church fields
                        church_record = self._map_csv_row(row)
                        if church_record:
                            church_data.append(church_record)
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"Skipping row {row_num}: {str(e)}")
                        )
                        continue
                        
        except Exception as e:
            raise CommandError(f"Error reading CSV file: {str(e)}")
        
        return church_data
    
    def _load_from_json(self, file_path: str) -> List[Dict]:
        """Load church data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                
                # Handle different JSON structures
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Look for common keys that might contain the church list
                    for key in ['churches', 'data', 'records', 'items']:
                        if key in data and isinstance(data[key], list):
                            return data[key]
                    
                    # If it's a single church record, wrap it in a list
                    if 'name' in data:
                        return [data]
                
                raise CommandError("JSON file does not contain valid church data structure")
                
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON file: {str(e)}")
        except Exception as e:
            raise CommandError(f"Error reading JSON file: {str(e)}")
    
    def _generate_sample_data(self) -> List[Dict]:
        """Generate sample church data for testing."""
        return [
            {
                'name': 'New Testament Church of Atlanta',
                'street_address': '123 Peachtree Street',
                'city': 'Atlanta',
                'state': 'Georgia',
                'zip_code': '30309',
                'phone': '(404) 555-0123',
                'website': 'https://ntc-atlanta.org',
                'email': 'info@ntc-atlanta.org',
                'service_times': 'Sunday: 10:00 AM, 6:00 PM; Wednesday: 7:00 PM',
                'is_active': True
            },
            {
                'name': 'New Testament Church of Dallas',
                'street_address': '456 Main Street',
                'city': 'Dallas',
                'state': 'Texas',
                'zip_code': '75201',
                'phone': '(214) 555-0456',
                'website': 'https://ntc-dallas.org',
                'email': 'contact@ntc-dallas.org',
                'service_times': 'Sunday: 9:30 AM, 6:30 PM; Wednesday: 7:30 PM',
                'is_active': True
            },
            {
                'name': 'New Testament Church of Phoenix',
                'street_address': '789 Desert Road',
                'city': 'Phoenix',
                'state': 'Arizona',
                'zip_code': '85001',
                'phone': '(602) 555-0789',
                'website': 'https://ntc-phoenix.org',
                'email': 'hello@ntc-phoenix.org',
                'service_times': 'Sunday: 10:30 AM, 7:00 PM; Wednesday: 7:00 PM',
                'is_active': True
            },
            {
                'name': 'New Testament Church of Seattle',
                'street_address': '321 Pine Avenue',
                'city': 'Seattle',
                'state': 'Washington',
                'zip_code': '98101',
                'phone': '(206) 555-0321',
                'website': 'https://ntc-seattle.org',
                'email': 'info@ntc-seattle.org',
                'service_times': 'Sunday: 11:00 AM, 6:00 PM; Wednesday: 7:00 PM',
                'is_active': True
            },
            {
                'name': 'New Testament Church of Miami',
                'street_address': '654 Ocean Drive',
                'city': 'Miami',
                'state': 'Florida',
                'zip_code': '33101',
                'phone': '(305) 555-0654',
                'website': 'https://ntc-miami.org',
                'email': 'welcome@ntc-miami.org',
                'service_times': 'Sunday: 10:00 AM, 6:30 PM; Wednesday: 7:30 PM',
                'is_active': True
            }
        ]
    
    def _map_csv_row(self, row: Dict) -> Optional[Dict]:
        """Map CSV row to church data structure."""
        # Common CSV column name mappings
        column_mappings = {
            'name': ['name', 'church_name', 'title', 'church'],
            'street_address': ['street_address', 'address', 'street', 'addr'],
            'city': ['city', 'town'],
            'state': ['state', 'province', 'region'],
            'zip_code': ['zip_code', 'zip', 'postal_code', 'zipcode'],
            'phone': ['phone', 'telephone', 'phone_number'],
            'website': ['website', 'url', 'web', 'site'],
            'email': ['email', 'email_address', 'contact_email'],
            'service_times': ['service_times', 'services', 'schedule', 'times'],
        }
        
        church_record = {}
        
        # Map columns using case-insensitive matching
        row_lower = {k.lower().strip(): v.strip() if isinstance(v, str) else v 
                    for k, v in row.items()}
        
        for field, possible_columns in column_mappings.items():
            value = None
            for col in possible_columns:
                if col in row_lower and row_lower[col]:
                    value = row_lower[col]
                    break
            
            if value:
                church_record[field] = value
        
        # Validate required fields
        required_fields = ['name', 'street_address', 'city', 'state']
        missing_fields = [field for field in required_fields if not church_record.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Set default values
        church_record.setdefault('is_active', True)
        
        return church_record
    
    def _show_dry_run_preview(self, church_data: List[Dict]) -> None:
        """Show preview of what would be imported in dry run mode."""
        self.stdout.write(self.style.SUCCESS("DRY RUN - Preview of church data to import:"))
        self.stdout.write("-" * 60)
        
        for i, church in enumerate(church_data[:5], 1):  # Show first 5 records
            self.stdout.write(f"{i}. {church.get('name', 'N/A')}")
            self.stdout.write(f"   Address: {church.get('street_address', 'N/A')}")
            self.stdout.write(f"   City: {church.get('city', 'N/A')}, {church.get('state', 'N/A')}")
            self.stdout.write("")
        
        if len(church_data) > 5:
            self.stdout.write(f"... and {len(church_data) - 5} more records")
        
        self.stdout.write(self.style.WARNING("Use --dry-run=False to actually import the data"))
    
    def _display_import_results(self, result: Dict) -> None:
        """Display import results."""
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            
            if result['created'] > 0:
                self.stdout.write(f"  Created: {result['created']} churches")
            if result['updated'] > 0:
                self.stdout.write(f"  Updated: {result['updated']} churches")
            if result['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"  Failed: {result['failed']} churches"))
                
                # Show failed records
                for failed in result.get('failed_records', [])[:3]:  # Show first 3 failures
                    self.stdout.write(f"    - Record {failed['index']}: {failed['error']}")
                
                if len(result.get('failed_records', [])) > 3:
                    remaining = len(result['failed_records']) - 3
                    self.stdout.write(f"    ... and {remaining} more failures")
        else:
            self.stdout.write(self.style.ERROR(f"✗ Import failed: {result['message']}"))
    
    def _display_geocoding_results(self, result: Dict) -> None:
        """Display geocoding results."""
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            
            if result['successful'] > 0:
                self.stdout.write(f"  Successfully geocoded: {result['successful']} churches")
            if result['skipped'] > 0:
                self.stdout.write(f"  Skipped (already geocoded): {result['skipped']} churches")
            if result['failed'] > 0:
                self.stdout.write(self.style.WARNING(f"  Failed to geocode: {result['failed']} churches"))
                
                # Show failed geocoding
                for failed in result.get('failed_churches', [])[:3]:  # Show first 3 failures
                    self.stdout.write(f"    - {failed['church']}: {failed['error']}")
                
                if len(result.get('failed_churches', [])) > 3:
                    remaining = len(result['failed_churches']) - 3
                    self.stdout.write(f"    ... and {remaining} more failures")
        else:
            self.stdout.write(self.style.ERROR(f"✗ Geocoding failed: {result['message']}"))