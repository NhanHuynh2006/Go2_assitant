"""Tuong thich nguoc: chay lai vai luot va so tung so voi results/dev3, dev1 (truoc khi ALGO sua)."""
import os, sys; R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, R)
import fastsim, csv, glob
A = {}
for d in ('dev3', 'dev1'):
    for f in glob.glob(f'{R}/results/{d}/w*.csv'):
        for r in csv.DictReader(open(f)): A.setdefault((r['world'], r['config']), (r['success'], r['time'], r['travel']))
for seed in map(int, sys.argv[1].split(',')):
    W = fastsim.gen_world(seed)
    for c in sys.argv[2:]:
        r = fastsim.run_episode(W, c, 0); a = A.get((str(seed), c)); b = (str(r['success']), str(r['time']), str(r['travel']))
        print(seed, c, 'GIONG' if a == b else 'KHAC', a, b, flush=True)
