import json, subprocess, sys

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()
r = subprocess.run(["curl.exe", "-s", "-m", "60", "-u", f"lzh745200:{T}",
                    "https://api.github.com/repos/lzh745200/MRRS/actions/runners"],
                   capture_output=True)
j = json.loads(r.stdout.decode("utf-8"))
out = [f"total={j['total_count']}"]
for x in j.get("runners", []):
    labels = ",".join(l["name"] for l in x.get("labels", []))
    out.append(f"{x['name']}: {x['status']} [{labels}]")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
