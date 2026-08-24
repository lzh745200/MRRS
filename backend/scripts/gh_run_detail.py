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

for rid in sys.argv[1:]:
    r = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}")
    out = [f"id={rid} name={r.get('name')!r} event={r.get('event')} attempt={r.get('run_attempt')} "
           f"{r.get('status')}/{r.get('conclusion')}",
           f"   path={r.get('path')} created={r.get('created_at')} updated={r.get('updated_at')}",
           f"   jobs_url_jobs_count_check"]
    jobs = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}/jobs")
    out.append(f"   total_jobs={jobs.get('total_count')}")
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
