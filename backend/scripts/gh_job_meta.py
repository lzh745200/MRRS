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
    try:
        return code.strip(), json.loads(body)
    except Exception:
        return code.strip(), body[:300]

run_id = sys.argv[1] if len(sys.argv) > 1 else "32733413816"
code, j = req("GET", f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/jobs")
out = []
for job in j.get("jobs", []):
    out.append(f"job={job['name']} status={job['status']}/{job['conclusion']}")
    out.append(f"  runner_group={job.get('runner_group_name')} runner_name={job.get('runner_name')}")
    out.append(f"  labels={job.get('labels')}")
    out.append(f"  started={job.get('started_at')} completed={job.get('completed_at')}")
code2, b2 = req("POST", f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/rerun-failed-jobs")
out.append(f"rerun-failed-jobs -> {code2} {json.dumps(b2)[:200] if not isinstance(b2,str) else b2}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
