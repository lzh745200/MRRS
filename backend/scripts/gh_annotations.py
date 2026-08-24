import json, subprocess, sys

def gh(url):
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    tok = [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]
    r = subprocess.run(["curl.exe", "-s", "-m", "60", "-u", f"lzh745200:{tok}", url],
                       capture_output=True)
    return json.loads(r.stdout.decode("utf-8"))

sha = subprocess.run(["git", "rev-parse", sys.argv[1] if len(sys.argv) > 1 else "32f8c9b"],
                     capture_output=True, text=True).stdout.strip()
cr = gh(f"https://api.github.com/repos/lzh745200/MRRS/commits/{sha}/check-runs")
out = []
for c in cr.get("check_runs", []):
    out.append(f"CHECK {c['name']} -> {c['status']}/{c['conclusion']}")
    output = c.get("output") or {}
    out.append(f"  title={output.get('title')}")
    summary = (output.get("summary") or "")[:500]
    out.append(f"  summary={summary}")
    for a in output.get("annotations", []) or []:
        out.append(f"  [{a.get('annotation_level')}] {a.get('message','')[:300]}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
