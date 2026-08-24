import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

for wf in ["build-windows.yml", "build-arm64.yml"]:
    r = subprocess.run(["curl.exe", "-s", "-m", "60", "-X", "POST", "-u", f"lzh745200:{T}",
                        "-H", "Content-Type: application/json", "-d", '{"ref":"main"}',
                        f"https://api.github.com/repos/lzh745200/MRRS/actions/workflows/{wf}/dispatches"],
                       capture_output=True)
    print(wf, "HTTP", r.stdout.decode()[:80] or "204-no-content")

time.sleep(8)
r = subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{T}",
                    "https://api.github.com/repos/lzh745200/MRRS/actions/runs?per_page=4"],
                   capture_output=True)
j = json.loads(r.stdout.decode("utf-8"))
for x in j.get("workflow_runs", []):
    print(f"{x['head_sha'][:7]} #{x['run_number']:<3} {x['name'][:30]:<30} {x['status']}/{x['conclusion']} id={x['id']}")
