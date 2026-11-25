import csv,glob,json,sys,collections
import numpy as np
for d in sys.argv[1:]:
    R=[r for f in glob.glob(d+"/w*.csv") for r in csv.DictReader(open(f))]
    for c in sorted({r["config"] for r in R}):
        C=[json.loads(r["info"]) for r in R if r["config"]==c and r["col"]=="person"]
        C=[x for x in C if "lead" in x]
        if not C: continue
        print(f"== {d} {c}: {len(C)} lan cham; nguoi 'mai dien thoai' {np.mean([x.get('distracted',0) for x in C])*100:.0f}%; loi robot {np.mean([x['at_fault'] for x in C])*100:.0f}%; |huong cham| TB {np.mean([abs(x['bearing']) for x in C]):.0f} do; rv luc cham {np.mean([x['robot_v'] for x in C]):.2f}; pin {np.mean([x['person_in'] for x in C]):.2f}")
        for L in ("3.0","2.0","1.5","1.0","0.5"):
            q=[x["lead"][L] for x in C if L in x["lead"]]
            if q: print(f"   -{L}s n={len(q):3d} d={np.mean([a['d'] for a in q]):.2f} tracker thay {np.mean([a['trk'] for a in q])*100:3.0f}%  nguoi dang huong vao (lech<0.6) {np.mean([a['miss']<.6 and a['ahead']>0 for a in q])*100:3.0f}%  dung yen {np.mean([a['sp']<.2 for a in q])*100:3.0f}%  robot v {np.mean([a['rv'] for a in q]):.2f} tuong<0.6 {np.mean([a['wall']<.6 for a in q])*100:3.0f}%")
