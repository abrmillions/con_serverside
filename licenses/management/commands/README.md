# License Number Migration Command

This command migrates existing license numbers from the old `CL-YYYY-NNNNNN` format to the new `LIC-YYYY-NNNNNN` format.

## Usage

### Preview Changes (Dry Run)
```bash
python manage.py migrate_license_numbers --dry-run
```

This will show you what changes would be made without actually applying them.

### Apply Migration
```bash
python manage.py migrate_license_numbers
```

This will migrate all licenses with `CL-` prefix to `LIC-` prefix.

### Update Data Field As Well
```bash
python manage.py migrate_license_numbers --update-data
```

This will also update the `licenseNumber` field in the `data` JSON field.

## What It Does

1. Finds all licenses with `CL-YYYY-NNNNNN` format
2. Converts them to `LIC-YYYY-NNNNNN` format (e.g., `CL-2024-001234` → `LIC-2024-001234`)
3. Updates the `license_number` column in the database
4. Optionally updates the `data.licenseNumber` field if `--update-data` is used
5. Skips licenses if the new number already exists (to prevent conflicts)

## Automatic Migration

The system also automatically migrates licenses when they are accessed during verification. If a license with `CL-` format is found, it will be automatically converted to `LIC-` format on-the-fly.

## Backward Compatibility

The verification system accepts both formats:
- Searching for `CL-2024-001234` will find `LIC-2024-001234`
- Searching for `LIC-2024-001234` will find licenses with either format

This ensures smooth transition without breaking existing references.
