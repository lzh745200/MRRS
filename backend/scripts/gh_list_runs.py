import json, os, sys
p = os.path.join(os.environ["TEMP"], "runs.json")
j = json.load(open(p, encoding="utf-8"))
out = []
for r in j["workflow_runs"]:
    out.append(f"{r['head_sha'][:7]}  #{r['run_number']:<3} {r['name']:<26} {r['status']}/{r['conclusion']}  {r['created_at']}  id={r['id']}")
sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
