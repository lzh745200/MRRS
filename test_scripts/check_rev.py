import sqlite3
for p, label in ((r'backend/data/rural_revitalization.db', 'main dev db'), (r'backend/data/smoke_test.db', 'smoke db')):
    try:
        c = sqlite3.connect(p)
        v = c.execute('SELECT version_num FROM alembic_version').fetchone()
        print(label, 'alembic version:', v)
        c.close()
    except Exception as e:
        print(label, 'no alembic_version:', e)
