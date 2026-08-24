import json
import pathlib

data = json.loads(pathlib.Path('coverage/coverage-final.json').read_text(encoding='utf-8'))
out = []
for k, f in data.items():
    lm = f['l']
    unl = sorted(int(line) for line, n in lm.items() if n == 0)
    if unl:
        out.append(f"FILE {k.split('src')[-1]}")
        # 压缩连续区间
        ranges = []
        s = e = unl[0]
        for x in unl[1:]:
            if x == e + 1:
                e = x
            else:
                ranges.append((s, e)); s = e = x
        ranges.append((s, e))
        out.append('uncovered lines: ' + ', '.join(f'{a}-{b}' if a != b else str(a) for a, b in ranges))
pathlib.Path('_unc2.txt').write_text('\n'.join(out), encoding='utf-8')
print('files with uncovered lines:', sum(1 for o in out if o.startswith('FILE')))
