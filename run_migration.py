#!/usr/bin/env python
"""
Quick script to run the license number migration.
Run this from the backend directory: python run_migration.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print("=" * 60)
    print("Running License Number Migration")
    print("=" * 60)
    print("\nStep 1: Preview changes (dry-run)...")
    call_command('migrate_license_numbers', '--dry-run')
    
    print("\n" + "=" * 60)
    response = input("\nDo you want to apply these changes? (yes/no): ")
    
    if response.lower() in ('yes', 'y'):
        print("\nStep 2: Applying migration...")
        call_command('migrate_license_numbers', '--update-data')
        print("\n✓ Migration completed!")
    else:
        print("\nMigration cancelled.")
