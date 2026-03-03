"""
Django management command to revert license numbers back to old formats.

This will convert:
- LIC-YYYY-NNNNNN back to LIC-X (simple format) if it was originally LIC-X
- LIC-YYYY-NNNNNN back to CL-YYYY-NNNNNN if it was originally CL- format

Usage:
    python manage.py revert_license_numbers --dry-run    # Preview changes
    python manage.py revert_license_numbers             # Apply reversion
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from licenses.models import License
import re


class Command(BaseCommand):
    help = 'Revert license numbers back to old formats (LIC-X or CL-YYYY-NNNNNN)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )
        parser.add_argument(
            '--to-lic-x',
            action='store_true',
            help='Revert to LIC-X format (simple format) instead of CL- format',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        to_lic_x = options['to_lic_x']
        
        # Find all licenses with new LIC-YYYY-NNNNNN format
        new_format_licenses = License.objects.filter(
            license_number__isnull=False
        ).exclude(
            license_number=''
        ).filter(
            license_number__regex=r'^LIC-\d{4}-\d{6}$'
        )
        
        # Convert to list and check which ones were migrated
        licenses_to_revert = []
        for lic in new_format_licenses:
            # Check if this was migrated from CL- format (check data field or pattern)
            # If it was CL-2026-000024, it became LIC-2026-000024
            # If it was LIC-5, it became LIC-2026-000005
            
            # Try to determine original format from data field
            original_format = None
            if lic.data and isinstance(lic.data, dict):
                # Check if data has old format stored
                old_num = lic.data.get('originalLicenseNumber') or lic.data.get('original_license_number')
                if old_num:
                    original_format = old_num
                else:
                    # Check if sequence suggests it was LIC-X (small number padded)
                    match = re.match(r'^LIC-(\d{4})-(\d{6})$', lic.license_number)
                    if match:
                        year = match.group(1)
                        seq = match.group(2)
                        seq_int = int(seq)
                        # If sequence is small and matches year, likely was LIC-X
                        if seq_int < 1000 and year == '2026':
                            original_format = f'LIC-{seq_int}'
                        else:
                            # Likely was CL- format
                            original_format = f'CL-{year}-{seq}'
            
            if original_format:
                licenses_to_revert.append((lic, original_format))
        
        total_count = len(licenses_to_revert)
        
        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No licenses found that need reversion.')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {total_count} license(s) to revert.')
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n=== DRY RUN MODE - No changes will be saved ===\n')
            )
        
        migrated_count = 0
        skipped_count = 0
        errors = []
        
        try:
            with transaction.atomic():
                for license, original_format in licenses_to_revert:
                    old_number = license.license_number
                    new_number = original_format
                    
                    # If to_lic_x flag is set and it was CL- format, convert to LIC-X instead
                    if to_lic_x and new_number.startswith('CL-'):
                        match = re.match(r'^CL-(\d{4})-(\d{6})$', new_number)
                        if match:
                            seq_int = int(match.group(2))
                            new_number = f'LIC-{seq_int}'
                    
                    # Check if new number already exists
                    if License.objects.filter(license_number=new_number).exclude(id=license.id).exists():
                        self.stdout.write(
                            self.style.ERROR(
                                f'  Skipping license ID {license.id}: '
                                f'Target number "{new_number}" already exists'
                            )
                        )
                        skipped_count += 1
                        continue
                    
                    # Revert license number
                    if not dry_run:
                        license.license_number = new_number
                        
                        # Update data field
                        if license.data and isinstance(license.data, dict):
                            if 'licenseNumber' in license.data:
                                license.data['licenseNumber'] = new_number
                            if 'license_number' in license.data:
                                license.data['license_number'] = new_number
                        
                        license.save(update_fields=['license_number', 'data'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  [REVERT] License ID {license.id}: "{old_number}" -> "{new_number}"'
                        )
                    )
                    migrated_count += 1
                
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(
                        self.style.WARNING('\n=== DRY RUN COMPLETE - No changes were saved ===')
                    )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\nError during reversion: {str(e)}')
            )
            errors.append(str(e))
            if not dry_run:
                raise
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('Reversion Summary:'))
        self.stdout.write(f'  Total licenses found: {total_count}')
        self.stdout.write(f'  Successfully reverted: {migrated_count}')
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
                    f'\nSuccessfully reverted {migrated_count} license number(s)!'
                )
            )
