import sqlite3
DB = 'backend/db.sqlite3'
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT id, name, file, application_id, uploader_id FROM documents_document ORDER BY id DESC LIMIT 50")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
