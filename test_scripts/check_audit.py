import sqlite3
c = sqlite3.connect(r'backend/data/smoke_test.db')
print('recent audit rows:')
for row in c.execute("SELECT id, username, action, resource_type, created_at FROM audit_logs ORDER BY id DESC LIMIT 8").fetchall():
    print(row)
print('---')
print('max created_at:', c.execute('SELECT MAX(created_at) FROM audit_logs').fetchone()[0])
print('min created_at:', c.execute('SELECT MIN(created_at) FROM audit_logs').fetchone()[0])
