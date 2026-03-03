"""
Moved E2E helper into tools folder.
Run with: `python backend/tools/e2e_test.py` from repo root.
"""
import json
import time
from urllib import request, error

BASE = 'http://127.0.0.1:8000'


def http_request(path, method='GET', data=None, headers=None):
    url = BASE + path
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    data_bytes = None
    if data is not None:
        data_bytes = json.dumps(data).encode('utf-8')
    req = request.Request(url, data=data_bytes, headers=hdrs, method=method)
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            if body:
                return resp.getcode(), json.loads(body)
            return resp.getcode(), None
    except error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'detail': e.reason}
    except Exception as e:
        return None, {'detail': str(e)}


def wait_for_server(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        code, _ = http_request('/')
        if code and code < 600:
            return True
        time.sleep(0.5)
    return False


if not wait_for_server(20):
    print('Server not reachable at', BASE)
    exit(2)

# Register
email = f'e2e_{int(time.time())}@example.com'
password = 'E2ePass123!'
register_payload = {
    'email': email,
    'username': email.split('@')[0],
    'password': password,
    'password_confirm': password,
    'first_name': 'E2E',
}
print('Registering user', email)
code, resp = http_request('/api/users/', method='POST', data=register_payload)
print('Register:', code, resp)

# Login
print('Logging in')
code, token = http_request('/api/users/token/', method='POST', data={'email': email, 'password': password})
print('Token:', code, token)
if not token or 'access' not in token:
    print('Login failed; aborting E2E')
    exit(3)

access = token['access']
refresh = token.get('refresh')
headers = {'Authorization': f'Bearer {access}'}

# Create application
app_payload = {
    'license_type': 'contractor',
    'subtype': 'grade-a',
    'data': {
        'licenseType': 'General',
        'businessType': 'Construction',
        'registrationNumber': 'REG12345',
        'taxId': 'TAX123',
        'yearsInBusiness': 5,
        'workScopes': ['electrical', 'plumbing'],
    }
}
print('Creating application')
code, app_resp = http_request('/api/applications/', method='POST', data=app_payload, headers=headers)
print('Create application:', code, app_resp)

if not app_resp or 'id' not in app_resp:
    print('Application creation failed; aborting')
    exit(4)

app_id = app_resp['id']

# Upload a dummy document via documents upload endpoint (if file upload supported, skip binary here)
print('Uploading dummy document via documents endpoint')
code, doc_resp = http_request('/api/documents/upload/', method='POST', data={'name': 'dummy', 'application': app_id}, headers=headers)
print('Document upload response:', code, doc_resp)

# Fetch application
print('Fetching application detail')
code, detail = http_request(f'/api/applications/{app_id}/', method='GET', headers=headers)
print('Application detail:', code, detail)

# Simulate download by saving JSON
filename = f'application_{app_id}.json'
with open(filename, 'w', encoding='utf-8') as f:
    json.dump(detail, f, indent=2)
print('Saved application JSON to', filename)

print('E2E test complete')
