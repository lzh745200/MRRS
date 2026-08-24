import json, subprocess, sys

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def gh(url):
    r = subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{T}", url],
                       capture_output=True)
    return json.loads(r.stdout.decode("utf-8", "replace"))

run_id = sys.argv[1]
run = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}")
out = [f"RUN {run_id}: {run.get('status')}/{run.get('conclusion')} sha={str(run.get('head_sha'))[:7]}"]
jobs = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/jobs").get("jobs", [])
for jb in jobs:
    out.append(f"JOB {jb['name']} -> {jb['status']}/{jb['conclusion']} runner={jb.get('runner_name')}")
    for s in jb.get("steps", []):
        mark = "!" if s["conclusion"] == "failure" else ("." if s["conclusion"] in ("skipped",) else " ")
        out.append(f" {mark}{s['number']:>2} {s['name'][:52]:<52} {s['status']}/{s['conclusion']}")
    if jb.get("conclusion") == "failure":
        log_url = f"https://api.github.com/repos/lzh745200/MRRS/actions/jobs/{jb['id']}/logs"
        rr = subprocess.run(["curl.exe", "-sL", "-m", "120", "-u", f"lzh745200:{T}", log_url],
                            capture_output=True)
        text = rr.stdout.decode("utf-8", "replace")
        errlines = [l for l in text.splitlines()
                    if "##[error]" in l or "npm ERR" in l or "Traceback" in l][:25]
        out.extend(errlines)
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
