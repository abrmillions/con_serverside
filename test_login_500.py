import requests
import json

url = "http://127.0.0.1:8000/api/users/token/"
# Use the user we just created in the previous test
email = "test_807675a5@gmail.com" 
payload = {
    "email": email,
    "password": "password123"
}

try:
    # Try JSON
    print("Trying JSON login...")
    response = requests.post(url, json=payload)
    print(f"JSON Status Code: {response.status_code}")
    print(f"JSON Response: {response.text}")
    
    # Try Form-encoded
    print("\nTrying Form-encoded login...")
    response = requests.post(url, data=payload)
    print(f"Form Status Code: {response.status_code}")
    print(f"Form Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
