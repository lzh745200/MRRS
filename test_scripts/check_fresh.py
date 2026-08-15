import sqlite3, os
p = r'backend/data/alembic_fresh_test.db'
if os.path.exists(p):
    c = sqlite3.connect(p)
    tables = [x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print('tables:', len(tables))
    print('version:', c.execute('SELECT version_num FROM alembic_version').fetchone()[0])
    print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
    print('sample tables:', tables[:12])
    c.close()
    os.remove(p)
    print('cleaned up')
else:
    print('fresh db file not found')
