import httpx, json
c = httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=30)
r = c.post('/auth/login', json={'username': 'admin', 'password': 'Admin@12345'})
print('login status:', r.status_code)
j = r.json()
tok = j.get('data', {}).get('access_token')
H = {'Authorization': 'Bearer ' + tok}
r2 = c.get('/system/audit/logs', params={'page': 1, 'page_size': 5}, headers=H)
print('audit logs status:', r2.status_code)
print('audit logs body:', r2.text[:600])
r3 = c.get('/system/audit/stats', headers=H)
print('audit stats body:', r3.text[:300])
