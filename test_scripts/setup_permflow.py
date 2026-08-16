import sqlite3, datetime
src = r'backend/data/rural_revitalization.db'
dst = r'backend/data/permflow_test.db'
import shutil, os
if os.path.exists(dst):
    os.remove(dst)
shutil.copy2(src, dst)
c = sqlite3.connect(dst)
now = datetime.datetime.now().isoformat()
# admin 密码重置为已知值（隔离测试库）
import sys
sys.path.insert(0, 'backend')
from app.core.security import hash_password
h = hash_password('Admin@12345')
c.execute('UPDATE users SET hashed_password=?, failed_login_count=0, locked_until=NULL, data_scope=? WHERE username=?', (h, 'all', 'admin'))
# 清空既有测试组织痕迹（主库克隆中组织表可能为空）
c.execute("DELETE FROM organizations WHERE name LIKE '%测试%'")
# 上级组织 org1（admin 所属）
c.execute('UPDATE users SET organization_id=? WHERE username=?', (1, 'admin'))
rows = c.execute('SELECT id, name, code, parent_id, path FROM organizations').fetchall()
print('orgs:', rows)
if not rows:
    cur = c.execute("INSERT INTO organizations (name, code, level, type, org_type, is_active, path, created_at) VALUES (?,?,?,?,?,?,?,?)",
                    ('上级机关', 'UP', 1, 'military', 'root', 1, '/1/', now))
    print('created org1 id', cur.lastrowid)
# 创建下级组织 org2（path 与 API 创建逻辑一致：/1/2/）
cur = c.execute("INSERT INTO organizations (name, code, level, type, org_type, is_active, path, parent_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ('下级单位甲', 'SUB1', 2, 'military', 'sub', 1, '/1/2/', 1, now))
org2 = cur.lastrowid
print('org2 id:', org2)
# 创建下级用户 user2（org2）
c.execute("INSERT INTO users (username, hashed_password, full_name, role, is_active, organization_id, data_scope, created_at) VALUES (?,?,?,?,?,?,?,?)",
          ('subuser1', hash_password('Sub@123456'), '下级用户甲', 'user', 1, org2, 'org', now))
c.execute("INSERT INTO users (username, hashed_password, full_name, role, is_active, organization_id, data_scope, created_at) VALUES (?,?,?,?,?,?,?,?)",
          ('subuser2', hash_password('Sub@123456'), '下级用户乙', 'user', 1, org2, 'org', now))
c.commit()
print('users:', c.execute('SELECT id, username, role, organization_id FROM users').fetchall())
c.close()
