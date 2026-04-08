import requests
import json
import uuid

url = "http://127.0.0.1:8000/api/users/register/"
email = f"test_{uuid.uuid4().hex[:8]}@gmail.com"
payload = {
    "email": email,
    "username": email,
    "password": "password123",
    "confirmPassword": "password123",
    "fullName": "Abraham Million Tadesse",
    "phone": "0921402053",
    "role": "applicant"
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
