import requests
import sys

url = 'http://localhost:3000/api/users/token/'

for pwd in ['12345678', 'wrongpass']:
    try:
        r = requests.post(url, json={'email':'abrahamabreham011@gmail.com','password':pwd}, timeout=5)
        print('PWD:', pwd, 'STATUS:', r.status_code, 'BODY:', r.text)
    except Exception as e:
        print('ERROR', e)
