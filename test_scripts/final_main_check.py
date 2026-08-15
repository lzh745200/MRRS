import sqlite3
c = sqlite3.connect(r'backend/data/rural_revitalization.db')
print('main db integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
print('users:', c.execute('SELECT id, username, role, is_active FROM users LIMIT 3').fetchall())
print('villages count:', c.execute('SELECT COUNT(*) FROM supported_villages').fetchone()[0])
print('funds count:', c.execute('SELECT COUNT(*) FROM funds').fetchone()[0])
print('alembic version:', c.execute('SELECT version_num FROM alembic_version').fetchone()[0])
c.close()
