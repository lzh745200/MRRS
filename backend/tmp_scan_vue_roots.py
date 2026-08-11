# -*- coding: utf-8 -*-
"""临时脚本：检测 .vue 模板顶层多根/顶层 v-if-v-else 模式（用后删除）"""
import os
import re

SRC = r"C:\military-Rural Revitalization-system\frontend\src"

def find_template(src_text):
    """提取 <template> 块（首个顶层 template）"""
    m = re.search(r"<template>", src_text)
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(src_text) and depth > 0:
        open_m = re.search(r"<template(?:\s[^>]*)?>", src_text[i:])
        close_m = re.search(r"</template>", src_text[i:])
        if not open_m and not close_m:
            break
        if open_m and (not close_m or open_m.start() < close_m.start()):
            depth += 1
            i += open_m.end()
        else:
            depth -= 1
            i += close_m.end()
    return src_text[start:i]

issues = []
for dirpath, dirnames, filenames in os.walk(SRC):
    for fn in filenames:
        if not fn.endswith(".vue"):
            continue
        path = os.path.join(dirpath, fn)
        src = open(path, encoding="utf-8").read()
        tpl = find_template(src)
        if not tpl:
            continue
        # 顶层元素：非注释、非 template、非空白的内容行
        lines = tpl.splitlines()
        # 找顶层 v-else（行首无缩进或缩进最小层级的 v-else）
        min_indent = min((len(l) - len(l.lstrip())) for l in lines if l.strip() and not l.strip().startswith("<!--"))
        for l in lines:
            stripped = l.strip()
            if not stripped:
                continue
            indent = len(l) - len(l.lstrip())
            if stripped.startswith("v-else") and indent == min_indent:
                issues.append((path, "顶层 v-else（多根条件分支）", stripped[:60]))
            # 顶层 <div v-if 后紧跟顶层 <div v-else 的兄弟（用行号推断）
        # 顶层多个根元素检测：统计顶层开标签数量
        top_level = []
        for l in lines:
            stripped = l.strip()
            if not stripped or stripped.startswith("<!--"):
                continue
            indent = len(l) - len(l.lstrip())
            if indent == min_indent:
                top_level.append(stripped[:70])
        # 去掉 <template> 包装本身
        top_level = [t for t in top_level if not t.startswith("<template")]
        if len(top_level) > 1:
            issues.append((path, f"顶层多根({len(top_level)}): {top_level[0]} / {top_level[1]}"))

for p, kind, detail in issues:
    print(f"{os.path.relpath(p, SRC)}: {kind} -> {detail}")
print(f"\n共 {len(issues)} 处")
