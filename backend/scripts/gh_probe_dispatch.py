import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()
def curl(method, url, data=None):
    cmd = ["curl.exe", "-s", "-m", "90", "-X", method, "-u", f"lzh745200:{T}"]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    r = subprocess.run(cmd + [url], capture_output=True)
    body = r.stdout.decode("utf-8", "replace")
    try:
        return json.loads(body)
    except Exception:
        return {"raw": body[:300]}

# 1) commit & push probe workflow
subprocess.run(["git", "add", ".github/workflows/probe.yml"], check=True)
subprocess.run(["git", "commit", "-m", "ci: probe runner health (diagnose instant-fail)"], check=True)
p = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
print(p.stdout[-200:], p.stderr[-200:])

# 2) dispatch on main
time.sleep(3)
r = curl("POST", "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/probe.yml/dispatches",
         {"ref": "main"})
print("dispatch resp:", r if "raw" in r else {k: r[k] for k in ()} or "204 ok")

# 3) poll latest probe runs
for i in range(12):
    time.sleep(10)
    j = curl("GET", "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/probe.yml/runs?per_page=1")
    runs = j.get("workflow_runs") or []
    if runs:
        r0 = runs[0]
        print(f"poll{i}: {r0['status']}/{r0['conclusion']}")
        if r0["status"] == "completed":
            print("RUN_ID:", r0["id"])
            break
