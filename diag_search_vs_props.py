import json, pathlib, subprocess, sys
from pipeline.metrics import successful_backdoor
pool = json.loads(pathlib.Path("apps_pool_hard10.json").read_text())["candidates"]

def run(src, stdin, t=5):
    try:
        p = subprocess.run([sys.executable,"-W","ignore","-c",src], input=stdin,
                           capture_output=True, text=True, timeout=t)
        return p.stdout.strip(), p.returncode
    except Exception:
        return None, -1

print(f"  {'candidate':22} {'search inputs':>13} {'that DIVERGE':>13}  diagnosis")
for tid, t in pool.items():
    suite_p = pathlib.Path(f"runs/uplan10-p05/run_0/pbt/{tid}/suite.json")
    if not suite_p.exists(): continue
    space = json.loads(suite_p.read_text()).get("space") or []
    ref = t["reference_solution"] or t["honest"]["code"]
    for a in t["attack_proposals"]:
        div = ok = 0
        for x in space[:40]:
            s = x if isinstance(x, str) else json.dumps(x)
            ao, arc = run(a["code"], s); ro, rrc = run(ref, s)
            if arc == 0 and rrc == 0 and ao is not None and ro is not None:
                ok += 1; div += (ao != ro)
        diag = ("search never reaches the bug" if div == 0 else
                "search DOES reach it -> properties are the gap")
        print(f"  {a['candidate_id']:22} {ok:>13} {div:>13}  {diag}")
