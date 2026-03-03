import sqlite3

DB = 'backend/db.sqlite3'
EMAIL = 'abrahamabreham011@gmail.com'

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT id, email, username, is_active, is_staff, password FROM users_customuser WHERE lower(email)=lower(?)", (EMAIL.lower(),))
rows = cur.fetchall()
if not rows:
    print('NO_USER')
else:
    for r in rows:
        print('|'.join([str(x) for x in r]))
conn.close()
