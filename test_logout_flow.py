import json
import time
from urllib import request, error

BASE = 'http://127.0.0.1:8000'

def http_post(path, data):
    url = BASE + path
    data_bytes = json.dumps(data).encode('utf-8')
    req = request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.getcode(), json.loads(resp.read().decode('utf-8'))
    except error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'detail': body}
    except Exception as e:
        return None, {'detail': str(e)}


def wait_for_server(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = request.urlopen(BASE + '/', timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    if not wait_for_server(20):
        print('Server not reachable at', BASE)
        return 2

    email = f'testuser_{int(time.time())}@example.com'
    password = 'TestPass123!'
    user_payload = {
        'email': email,
        'username': email.split('@')[0],
        'password': password,
        'password_confirm': password,
        'first_name': 'Test',
    }

    print('Registering user:', email)
    code, resp = http_post('/api/users/', user_payload)
    print('Register response:', code, resp)

    print('Logging in...')
    code, token_resp = http_post('/api/users/token/', {'email': email, 'password': password})
    print('Token response:', code, token_resp)

    if not token_resp or 'refresh' not in token_resp:
        print('Failed to obtain tokens; aborting logout test.')
        return 3

    refresh = token_resp['refresh']
    print('Calling logout with refresh token...')
    code, logout_resp = http_post('/api/users/logout/', {'refresh': refresh})
    print('Logout response:', code, logout_resp)

    print('Attempting token refresh (should fail if blacklisted)...')
    code, refresh_resp = http_post('/api/users/token/refresh/', {'refresh': refresh})
    print('Refresh attempt response:', code, refresh_resp)

    print('Test complete.')


if __name__ == '__main__':
    raise SystemExit(main())
