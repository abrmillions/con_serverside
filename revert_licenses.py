#!/usr/bin/env python
"""
Direct script to revert license numbers back to original formats.
Run from backend directory: python revert_licenses.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from licenses.models import License

# Mapping of license IDs to their original formats
# Based on migration history:
revert_map = {
    1: 'LIC-5',           # Was LIC-5
    5: 'LIC-7',           # Was LIC-7
    24: 'CL-2026-000024', # Was CL-2026-000024
    25: 'CL-2026-000025', # Was CL-2026-000025
}

def revert_licenses():
    print("=" * 60)
    print("Reverting License Numbers to Original Formats")
    print("=" * 60)
    
    reverted = []
    skipped = []
    
    for license_id, original_format in revert_map.items():
        try:
            license = License.objects.get(id=license_id)
            old_number = license.license_number
            new_number = original_format
            
            # Check if target already exists
            if License.objects.filter(license_number=new_number).exclude(id=license_id).exists():
                print(f"  [SKIP] License ID {license_id}: Target '{new_number}' already exists")
                skipped.append((license_id, old_number, new_number))
                continue
            
            # Revert the license number
            license.license_number = new_number
            
            # Update data field
            if license.data and isinstance(license.data, dict):
                license.data['licenseNumber'] = new_number
                if 'license_number' in license.data:
                    license.data['license_number'] = new_number
            
            license.save(update_fields=['license_number', 'data'])
            
            print(f"  [OK] License ID {license_id}: '{old_number}' -> '{new_number}'")
            reverted.append((license_id, old_number, new_number))
            
        except License.DoesNotExist:
            print(f"  [ERROR] License ID {license_id} not found")
        except Exception as e:
            print(f"  [ERROR] License ID {license_id}: {str(e)}")
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Successfully reverted: {len(reverted)}")
    print(f"  Skipped: {len(skipped)}")
    print("=" * 60)
    
    if reverted:
        print("\nReverted licenses:")
        for lid, old, new in reverted:
            print(f"  ID {lid}: {old} -> {new}")

if __name__ == '__main__':
    revert_licenses()
