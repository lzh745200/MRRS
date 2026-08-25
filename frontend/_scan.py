import re

t = open('src/views/projects/List.vue', encoding='utf-8').read()
lines = t.splitlines()
pat = re.compile(r'handleDelete|el-popconfirm|操作|loadData|projectApi\.|^import |from \'@/api')
for i, l in enumerate(lines, 1):
    if pat.search(l):
        print(f'{i}: {l.strip()[:110]}')
