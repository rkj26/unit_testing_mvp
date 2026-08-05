import json, pathlib, random, subprocess, sys, signal
pool = json.loads(pathlib.Path("apps_pool_hard10.json").read_text())["candidates"]

def run(src, stdin, t=5):
    try:
        p = subprocess.run([sys.executable,"-W","ignore","-c",src], input=stdin,
                           capture_output=True, text=True, timeout=t)
        return p.stdout.strip(), p.returncode
    except Exception:
        return None, -1

def mutate(stdin, rng):
    toks = stdin.split()
    if not toks: return stdin
    out = []
    for t in toks:
        if t.lstrip("-").isdigit() and rng.random() < 0.5:
            v = int(t); out.append(str(max(0, v + rng.choice([-2,-1,1,2]))))
        else: out.append(t)
    return " ".join(out) + "\n"

rng = random.Random(0)
print(f"  {'candidate':22} {'divergence rate on 120 mutations of its own trigger':>10}")
for tid, t in pool.items():
    ref = t["reference_solution"] or t["honest"]["code"]
    for a in t["attack_proposals"]:
        base = a["secret_input"]
        div = n = 0
        for _ in range(60):
            s = mutate(base, rng)
            ao, arc = run(a["code"], s); ro, rrc = run(ref, s)
            if arc == 0 and rrc == 0 and ao is not None and ro is not None:
                n += 1; div += (ao != ro)
        if n: print(f"  {a['candidate_id']:22} {div}/{n} = {div/n:.0%}")
