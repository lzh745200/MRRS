import json, subprocess, sys

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def gh(url):
    r = subprocess.run(["curl.exe", "-sL", "-m", "120", "-u", f"lzh745200:{T}", url],
                       capture_output=True)
    return r.stdout

run_id = sys.argv[1]
jobs = json.loads(gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{run_id}/jobs"))
out = []
for jb in jobs["jobs"]:
    if jb.get("conclusion") != "failure":
        continue
    jid = jb["id"]
    out.append(f"===== JOB {jb['name']} (id={jid}) =====")
    log = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/jobs/{jid}/logs").decode("utf-8", "replace")
    lines = [l for l in log.splitlines() if any(
        k in l.lower() for k in ["error", "✖", "warning", "failed", "##[error]"])]
    out.extend(lines[-40:])
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
