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

ids = sys.argv[1:] or ["32730427641", "32730427614", "32730427587"]
for cycle in range(int(sys.argv[1]) if False else 3):
    time.sleep(45)
    out = [f"--- cycle {cycle} ---"]
    done = True
    for rid in ids:
        j = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}")
        r = j
        out.append(f"run {rid}: attempt={r.get('run_attempt')} {r.get('status')}/{r.get('conclusion')}")
        if r.get("status") != "completed":
            done = False
        jobs = gh(f"https://api.github.com/repos/lzh745200/MRRS/actions/runs/{rid}/jobs").get("jobs", [])
        for jb in jobs:
            steps_done = sum(1 for s in jb.get("steps", []) if s["status"] == "completed")
            out.append(f"  {jb['name'][:34]:<34} {jb['status']}/{jb['conclusion']} steps_done={steps_done} runner={jb.get('runner_name')}")
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    if done:
        break
