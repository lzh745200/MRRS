import json, subprocess, sys

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def req(method, url):
    r = subprocess.run(["curl.exe", "-s", "-m", "60", "-X", method, "-u", f"lzh745200:{T}",
                        "-w", "\n%{http_code}", url], capture_output=True)
    body, _, code = r.stdout.decode("utf-8", "replace").rpartition("\n")
    return code.strip(), body[:400]

# 对最新失败 run 触发 rerun，观察响应体中的官方原因
run_id = sys.argv[1] if len(sys.argv) > 1 else "32730427614"
code, body = req("POST", f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/rerun")
print(f"rerun -> HTTP {code}\n{body}")

# 新版账单用量端点
for u in [
    "https://api.github.com/users/lzh745200/billing/usage",
    "https://api.github.com/users/lzh745200/settings/billing/shared-storage",
    "https://api.github.com/repos/lzh745200/MRRS/actions/permissions/workflow",
]:
    code, body = req("GET", u)
    print(f"\n{code} {u}\n{body}")
