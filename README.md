# Backend Django scaffold

This folder contains a minimal Django REST backend scaffold for the Construction License System.

Quick start (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd backend
python manage.py migrate
python manage.py createsuperuser  # optional
python manage.py runserver
```

Endpoints:

- `POST /api/users/register/` — register a new user
- `POST /api/users/token/` — obtain JWT (username & password)
- `POST /api/users/token/refresh/` — refresh JWT
- `GET/POST/PUT/DELETE /api/licenses/` — license CRUD (authenticated)

Notes:

- Update `SECRET_KEY` and `DEBUG` for production in environment variables.
- This scaffold uses SQLite by default. Update `DATABASES` in `backend_project/settings.py` for other DBs.
