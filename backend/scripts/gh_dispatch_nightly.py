import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

r = subprocess.run(["curl.exe", "-s", "-m", "90", "-X", "POST", "-u", f"lzh745200:{T}",
                    "-H", "Content-Type: application/json", "-d", '{"ref":"main"}',
                    "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/nightly-full.yml/dispatches"],
                   capture_output=True)
print("dispatch:", r.stdout.decode()[:60] or "204")

time.sleep(12)
j = json.loads(subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{T}",
                               "https://api.github.com/repos/lzh745200/MRRS/actions/workflows/nightly-full.yml/runs?per_page=1"],
                              capture_output=True).stdout.decode())
r0 = j["workflow_runs"][0]
print(f"new run: #{r0['run_number']} {r0['status']}/{r0['conclusion']} id={r0['id']}")
