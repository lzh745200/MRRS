import json, subprocess, sys

def tok():
    creds = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n",
                           capture_output=True, text=True).stdout
    return [l[9:] for l in creds.splitlines() if l.startswith("password=")][0]

T = tok()
r = subprocess.run(["curl.exe", "-s", "-m", "60", "-X", "POST",
                    "-u", f"lzh745200:{T}",
                    "https://api.github.com/repos/lzh745200/MRRS/actions/runners/registration-token"],
                   capture_output=True)
j = json.loads(r.stdout.decode("utf-8"))
print(j.get("token", j))
