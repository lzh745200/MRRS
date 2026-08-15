import subprocess, sqlite3, os, sys
os.environ['DATABASE_URL'] = 'sqlite:///./alembic_fresh_test.db'
os.environ['PYTHONIOENCODING'] = 'utf-8'
r = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], capture_output=True, text=True)
print('alembic exit:', r.returncode)
print(r.stdout[-400:] if r.stdout else '')
print(r.stderr[-400:] if r.stderr else '')
c = sqlite3.connect('alembic_fresh_test.db')
tables = [x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('tables:', len(tables))
print('version:', c.execute('SELECT version_num FROM alembic_version').fetchone()[0])
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
c.close()
os.remove('alembic_fresh_test.db')
print('cleaned up')
