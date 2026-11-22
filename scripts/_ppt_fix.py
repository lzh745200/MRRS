import zipfile, re, pathlib, os

REPLACEMENTS = [
    ("棘轮 137/146", "棘轮 121/121"),
    ("当前 137（40 个文件）", "当前 121（39 个文件）"),
    ("当前 137（40 个文件；", "当前 121（39 个文件；"),
    ("收敛到 137 处", "收敛到 121 处"),
    ("硬编码色 137（", "硬编码色 121（"),
]


def fix_text(text: str):
    if "硬编码" not in text and "棘轮" not in text:
        return text
    new = text
    for old, rep in REPLACEMENTS:
        new = new.replace(old, rep)
    return new


total = 0
for p in sorted(pathlib.Path("docs").glob("*.pptx")):
    zin = zipfile.ZipFile(p)
    items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    zin.close()
    changed = 0
    out = []
    for info, data in items:
        if info.filename.startswith("ppt/slides/slide") and info.filename.endswith(".xml"):
            s = data.decode("utf-8")
            def sub(m):
                nonlocal changed
                t = m.group(1)
                nt = fix_text(t)
                if nt != t:
                    changed += 1
                return "<a:t>" + nt + "</a:t>"
            s2 = re.sub(r"<a:t>(.*?)</a:t>", sub, s)
            data = s2.encode("utf-8")
        out.append((info, data))
    if changed:
        tmp = p.with_suffix(".pptx.tmp")
        with zipfile.ZipFile(tmp, "w") as zout:
            for info, data in out:
                zout.writestr(info, data)
        os.replace(tmp, p)
        total += changed
    print(p.name, "changed_text_nodes", changed)

print("total", total)
