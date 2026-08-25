import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def curl(m, u):
    r = subprocess.run(["curl.exe", "-s", "-m", "90", "-X", m, "-u", f"lzh745200:{T}", u],
                       capture_output=True)
    return r.stdout.decode("utf-8", "replace")

for wf in ["pr-checks.yml", "nightly-full.yml"]:
    body = curl("POST", f"https://api.github.com/repos/lzh745200/MRRS/actions/workflows/{wf}/dispatches")
    print(wf, "->", body[:80] or "204")

time.sleep(10)
j = json.loads(curl("GET", "https://api.github.com/repos/lzh745200/MRRS/actions/runs?per_page=6"))
for x in j.get("workflow_runs", []):
    print(f"{x['head_sha'][:7]} #{x['run_number']:<3} {x['name'][:24]:<24} {x['status']}/{x['conclusion']} id={x['id']}")
