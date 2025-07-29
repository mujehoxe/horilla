import sys
import os
from django.core.management.base import BaseCommand
from django.db.models import Q
from employee.models import Employee

# Add the project root to Python path to import our script
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from fetch_hikvision_employees import HikvisionEmployeeAPI

# Configuration
DEVICE_IP = '192.168.70.35'
USERNAME = 'admin'  # Default username, change if different
PASSWORD = 'hik12345'  # Change to your device password

class Command(BaseCommand):
    help = 'Sync Hikvision employees with Horilla database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--create-missing',
            action='store_true',
            help='Create new Employee records for Hikvision employees not found in Horilla',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        create_missing = options['create_missing']
        
        self.stdout.write('Starting Hikvision employee sync...')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Instantiate API client
        api = HikvisionEmployeeAPI(DEVICE_IP, USERNAME, PASSWORD, use_https=True)
        
        # Test connection first
        if not api.test_connection():
            self.stdout.write(self.style.ERROR('Failed to connect to Hikvision device'))
            return
            
        employee_data = api.get_employees(quiet=True)
        
        if not employee_data:
            self.stdout.write(self.style.WARNING('No employee data retrieved from Hikvision'))
            return
            
        self.stdout.write(f'Retrieved {len(employee_data)} employees from Hikvision')
        
        matched_count = 0
        updated_count = 0
        created_count = 0
        unmatched_count = 0

        for emp in employee_data:
            hikvision_id = emp.get('employeeNo')
            hikvision_name = emp.get('name', '').strip()
            
            if not hikvision_name:
                self.stdout.write(f'Skipping employee ID {hikvision_id} - no name')
                continue

            # Try to find existing employee by name matching
            existing_employee = self.find_matching_employee(hikvision_name)
            
            if existing_employee:
                matched_count += 1
                
                # Check if we need to update
                needs_update = (
                    existing_employee.hikvision_employee_id != hikvision_id or 
                    existing_employee.hikvision_employee_name != hikvision_name
                )
                
                if needs_update:
                    if not dry_run:
                        existing_employee.hikvision_employee_id = hikvision_id
                        existing_employee.hikvision_employee_name = hikvision_name
                        existing_employee.save()
                        updated_count += 1
                    
                    prefix = '[DRY RUN] ' if dry_run else ''
                    self.stdout.write(
                        f'{prefix}Updated: {existing_employee.get_full_name()} '
                        f'-> Hikvision ID: {hikvision_id}, Name: {hikvision_name}'
                    )
                else:
                    self.stdout.write(
                        f'Already synced: {existing_employee.get_full_name()} '
                        f'(Hikvision ID: {hikvision_id})'
                    )
            else:
                unmatched_count += 1
                
                if create_missing:
                    if not dry_run:
                        # Create minimal employee record
                        name_parts = hikvision_name.split(' ', 1)
                        first_name = name_parts[0]
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                        
                        new_employee = Employee.objects.create(
                            employee_first_name=first_name,
                            employee_last_name=last_name,
                            email=f'hikvision_{hikvision_id}@placeholder.com',  # Placeholder email
                            hikvision_employee_id=hikvision_id,
                            hikvision_employee_name=hikvision_name,
                            phone='',  # Required field
                        )
                        created_count += 1
                        
                    prefix = '[DRY RUN] ' if dry_run else ''
                    self.stdout.write(
                        f'{prefix}Created new employee: {hikvision_name} '
                        f'(Hikvision ID: {hikvision_id})'
                    )
                else:
                    self.stdout.write(
                        f'No match found for Hikvision employee: {hikvision_name} (ID: {hikvision_id})'
                    )

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write('SYNC SUMMARY:')
        self.stdout.write(f'Total Hikvision employees: {len(employee_data)}')
        self.stdout.write(f'Matched to existing employees: {matched_count}')
        self.stdout.write(f'Updated: {updated_count}')
        self.stdout.write(f'Created: {created_count}')
        self.stdout.write(f'Unmatched: {unmatched_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a dry run - no changes were made.'))
            self.stdout.write('Run without --dry-run to apply changes.')
            
        self.stdout.write('Hikvision employee sync complete.')

    def find_matching_employee(self, hikvision_name):
        """Find existing Horilla employee that matches Hikvision name"""
        
        # Try exact match on full name
        name_parts = hikvision_name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        # Try exact first + last name match
        if last_name:
            employee = Employee.objects.filter(
                employee_first_name__iexact=first_name,
                employee_last_name__iexact=last_name
            ).first()
            if employee:
                return employee
        
        # Try first name only if no last name in Hikvision
        if not last_name:
            employee = Employee.objects.filter(
                employee_first_name__iexact=first_name,
                employee_last_name__isnull=True
            ).first()
            if employee:
                return employee
            
            # Also try where last name is empty string
            employee = Employee.objects.filter(
                employee_first_name__iexact=first_name,
                employee_last_name=''
            ).first()
            if employee:
                return employee
        
        # Try partial matches on first name for common variations
        employee = Employee.objects.filter(
            employee_first_name__icontains=first_name
        ).first()
        if employee:
            return employee
            
        # Try searching in full name concatenation
        employees = Employee.objects.all()
        for emp in employees:
            full_name = emp.get_full_name().strip()
            if full_name.upper() == hikvision_name.upper():
                return emp
                
        return None

