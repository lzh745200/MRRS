# -*- coding: utf-8 -*-
"""轮询 GitHub Actions 三条流水线（v1.12.2 安装包构建 + main PR Checks）直至完成。"""
import json
import time
import urllib.request

API = "https://api.github.com/repos/lzh745200/MRRS/actions/runs?per_page=10"
TARGETS = {"Build Windows Installer (x64)", "Build Self-Contained ARM64 Debian Package"}
CREATED_SINCE = "2026-09-11T14:3"


def get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


done = {}
deadline = time.time() + 3300
while time.time() < deadline:
    finished = True
    try:
        data = get(API)
    except Exception as exc:
        print("POLL_ERR", exc, flush=True)
        time.sleep(45)
        continue
    for w in data.get("workflow_runs", []):
        name = w["name"]
        matched = name in TARGETS or (
            name == "PR Checks" and w["head_branch"] == "main" and w["created_at"] >= CREATED_SINCE
        )
        if not matched:
            continue
        if w["status"] != "completed":
            finished = False
        else:
            done[name] = (w["conclusion"], w["html_url"])
    if finished and done:
        break
    time.sleep(45)

for k, v in sorted(done.items()):
    print(k, "|", v[0], "|", v[1])
print("DONE_COUNT", len(done))
