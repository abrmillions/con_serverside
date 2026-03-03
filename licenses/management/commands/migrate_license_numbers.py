"""
Django management command to migrate existing license numbers from CL- format to LIC- format.

Usage:
    python manage.py migrate_license_numbers
    
    # Dry run (preview changes without applying):
    python manage.py migrate_license_numbers --dry-run
    
    # Update data field as well:
    python manage.py migrate_license_numbers --update-data
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from licenses.models import License
import re


class Command(BaseCommand):
    help = 'Migrate existing license numbers from CL- format to LIC- format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )
        parser.add_argument(
            '--update-data',
            action='store_true',
            help='Also update licenseNumber in the data JSON field',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        update_data = options['update_data']
        
        # Find all licenses with old formats: CL- prefix or LIC-X format (simple format)
        from datetime import date
        today = date.today()
        
        # Get all licenses with CL- or LIC- prefix
        all_licenses = License.objects.filter(
            license_number__isnull=False
        ).exclude(
            license_number=''
        ).filter(
            Q(license_number__startswith='CL-') | Q(license_number__startswith='LIC-')
        )
        
        # Filter out licenses that already have correct LIC-YYYY-NNNNNN format
        correct_pattern = re.compile(r'^LIC-\d{4}-\d{6}$')
        old_format_licenses = [
            lic for lic in all_licenses 
            if not correct_pattern.match(lic.license_number)
        ]
        
        total_count = len(old_format_licenses)
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No licenses with old format found. Nothing to migrate.')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {total_count} license(s) with old format to migrate.')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n=== DRY RUN MODE - No changes will be saved ===\n')
            )
        
        migrated_count = 0
        skipped_count = 0
        errors = []
        
        # Patterns to match different old formats
        cl_pattern = re.compile(r'^CL-(\d{4})-(\d{6})$', re.IGNORECASE)
        lic_simple_pattern = re.compile(r'^LIC-(\d+)$', re.IGNORECASE)  # LIC-5, LIC-123, etc.
        
        try:
            with transaction.atomic():
                for license in old_format_licenses:
                    old_number = license.license_number
                    new_number = None
                    
                    # Try CL-YYYY-NNNNNN format first
                    match = cl_pattern.match(old_number)
                    if match:
                        year = match.group(1)
                        seq = match.group(2)
                        new_number = f'LIC-{year}-{seq}'
                    else:
                        # Try LIC-X simple format (LIC-5, LIC-123, etc.)
                        match = lic_simple_pattern.match(old_number)
                        if match:
                            seq_num = int(match.group(1))
                            # Use issued_date year if available, otherwise current year
                            if license.issued_date:
                                year = str(license.issued_date.year)
                            else:
                                year = str(today.year)
                            # Pad sequence to 6 digits
                            seq = f'{seq_num:06d}'
                            new_number = f'LIC-{year}-{seq}'
                    
                    if not new_number:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Skipping license ID {license.id}: '
                                f'Unexpected format "{old_number}"'
                            )
                        )
                        skipped_count += 1
                        continue
                    
                    # Check if new number already exists
                    if License.objects.filter(license_number=new_number).exclude(id=license.id).exists():
                        self.stdout.write(
                            self.style.ERROR(
                                f'  Skipping license ID {license.id}: '
                                f'New number "{new_number}" already exists'
                            )
                        )
                        skipped_count += 1
                        continue
                    
                    # Update license number
                    if not dry_run:
                        license.license_number = new_number
                        
                        # Update data field if requested
                        if update_data and license.data and isinstance(license.data, dict):
                            if 'licenseNumber' in license.data:
                                license.data['licenseNumber'] = new_number
                            if 'license_number' in license.data:
                                license.data['license_number'] = new_number
                        
                        license.save(update_fields=['license_number', 'data'] if update_data else ['license_number'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  [OK] License ID {license.id}: "{old_number}" -> "{new_number}"'
                        )
                    )
                    migrated_count += 1
                
                if dry_run:
                    # Rollback transaction in dry-run mode
                    transaction.set_rollback(True)
                    self.stdout.write(
                        self.style.WARNING('\n=== DRY RUN COMPLETE - No changes were saved ===')
                    )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nError during migration: {str(e)}')
            )
            errors.append(str(e))
            if not dry_run:
                raise
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Migration Summary:'))
        self.stdout.write(f'  Total licenses found: {total_count}')
        self.stdout.write(f'  Successfully migrated: {migrated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        if errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {len(errors)}'))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\nRun without --dry-run to apply these changes.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully migrated {migrated_count} license number(s)!'
                )
            )
