import json, subprocess, sys

def gh(url):
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    tok = [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]
    r = subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{tok}", url],
                       capture_output=True)
    return json.loads(r.stdout.decode("utf-8"))

wid = sys.argv[1] if len(sys.argv) > 1 else "334373293"  # PR Checks workflow id
j = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/workflows/{wid}/runs?per_page=30")
out = []
for r in j.get("workflow_runs", []):
    out.append(f"#{r['run_number']:<3} {r['head_sha'][:7]} {r['status']}/{r['conclusion']} {r['created_at']}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
