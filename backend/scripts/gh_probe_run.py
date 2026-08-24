import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def curl(m, u, d=None):
    cmd = ["curl.exe", "-s", "-m", "90", "-X", m, "-u", f"lzh745200:{T}"]
    if d is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(d)]
    r = subprocess.run(cmd + [u], capture_output=True)
    try:
        return json.loads(r.stdout.decode("utf-8", "replace"))
    except Exception:
        return {"raw": r.stdout.decode("utf-8", "replace")[:200]}

r = curl("POST", "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/probe.yml/dispatches",
         {"ref": "main"})
print("dispatch:", r.get("raw", "204"))
for i in range(15):
    time.sleep(10)
    j = curl("GET", "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/probe.yml/runs?per_page=1")
    runs = j.get("workflow_runs") or []
    if runs:
        r0 = runs[0]
        print(f"poll{i}: {r0['status']}/{r0['conclusion']} id={r0['id']}")
        if r0["status"] == "completed":
            break
