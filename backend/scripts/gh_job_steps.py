import json, os, subprocess, sys

def gh(url):
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    tok = [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]
    r = subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{tok}", url],
                       capture_output=True)
    return json.loads(r.stdout.decode("utf-8"))

run_id = sys.argv[1] if len(sys.argv) > 1 else "32730427614"
j = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/jobs")
out = []
for job in j.get("jobs", []):
    out.append(f"JOB: {job['name']}  -> {job['status']}/{job['conclusion']}")
    if not job.get("steps"):
        out.append("  (no steps recorded)")
    for s in job.get("steps", []):
        mark = "*" if s["conclusion"] not in ("success", "skipped", None) else " "
        out.append(f" {mark} {s['number']:>2}. {s['name']:<48} {s['status']}/{s['conclusion']}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
