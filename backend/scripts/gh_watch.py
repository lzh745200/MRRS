import json, subprocess, sys, time

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()

def gh(url):
    r = subprocess.run(["curl.exe", "-s", "-m", "90", "-u", f"lzh745200:{T}", url],
                       capture_output=True)
    return json.loads(r.stdout.decode("utf-8", "replace"))

ids = sys.argv[1:]
deadline = time.time() * 1 + 75 * 60
while time.time() < deadline:
    out = []
    alldone = True
    for rid in ids:
        r = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}")
        st = f"{r.get('status')}/{r.get('conclusion')}"
        out.append(f"run {rid}: {st} attempt={r.get('run_attempt')}")
        if r.get("status") != "completed":
            alldone = False
        jobs = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}/jobs").get("jobs", [])
        for jb in jobs:
            failed_step = next((s["name"] for s in jb.get("steps", [])
                                if s.get("conclusion") == "failure"), "")
            out.append(f"   {jb['name'][:36]:<36} {jb['status']}/{jb['conclusion']}"
                       + (f" FAIL_STEP={failed_step}" if failed_step else ""))
    sys.stdout.buffer.write(("\n".join(out) + "\n\n").encode("utf-8"))
    sys.stdout.buffer.flush()
    if alldone:
        break
    time.sleep(90)
