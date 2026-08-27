"""前后端 API 对齐度核查：前端所有 request 调用 vs 后端已注册路由。"""
import re
import json
import os

backend = set(json.load(open('/tmp/backend_routes.json', encoding='utf-8')))

Q = '`' + "'" + '"'  # 引号字符类内容：反引号/单引号/双引号
NEG = '[^' + Q + ']'  # 非引号字符（URL 主体）


def norm(p):
    p = re.sub(r'^/api/v1', '', p)
    p = re.sub(r'\{[^}]+\}', '{}', p)
    # 前端模板常带尾斜杠（`/funds/${id}/`），后端路由无尾斜杠 → 统一去掉
    return p.rstrip('/') or '/'


backend_norm = {}
for r in backend:
    m, _, path = r.partition(' ')
    backend_norm.setdefault(norm(path), set()).add(m)

pat = re.compile(
    r"\b(get|post|put|del|delete|patch)\(\s*[" + Q + r"](" + NEG + r"+)"
)

missing = []
checked = 0
for root, dirs, files in os.walk('frontend/src'):
    for f in files:
        if not f.endswith(('.ts', '.vue')):
            continue
        fp = os.path.join(root, f)
        try:
            src = open(fp, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue
        for m, url in pat.findall(src):
            if not url.startswith('/'):
                continue
            if 'api/v1' in url:
                url = url.split('api/v1', 1)[1]
            url = url.split('?', 1)[0]          # 去查询串
            checked += 1
            # 模板字面量 ${id} 视为路径参数 → 参数化归一（与后端 {id} 一致）
            key = norm(re.sub(r'\$\{[^}]+\}', '{}', url))
            verb = 'DELETE' if m.lower() == 'del' else m.upper()
            verbs = backend_norm.get(key)
            if verbs is None and '{}' not in key:
                verbs = set()
                for k, vv in backend_norm.items():
                    if k.startswith(key + '/'):
                        verbs |= vv
            if verb not in (verbs or set()):
                rel = fp.replace('frontend' + os.sep + 'src' + os.sep, '')
                missing.append((rel, verb, url))

seen = set()
uniq = [x for x in missing if not (x[:2] in seen or seen.add(x[:2]))]
print(f'checked frontend calls: {checked}')
print(f'mismatches: {len(uniq)}')
for f, m, u in uniq[:40]:
    print(f'  {m} {u}   <- {f}')
