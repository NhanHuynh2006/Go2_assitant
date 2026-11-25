"""In ra trung vi rtf_med (va rtf_mean) cua K luot Gazebo TEST moi nhat; CHI doc truong rtf, khong doc ket qua.
   python3 gz_rtf.py [K] [sau_epoch]  -> 'med_rtf_med med_rtf_mean n newest_mtime'"""
import glob, json, os, sys, statistics as st
K = int(sys.argv[1]) if len(sys.argv) > 1 else 4
since = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "GZ_TEST")
eps = []
for f in glob.glob(R + "/s*/g*/episodes.jsonl"):
    m = os.path.getmtime(f)
    for i, l in enumerate(open(f)):
        try:
            j = json.loads(l)
        except Exception:
            continue
        for r in j.get("rows", []):
            if r.get("rtf_med") not in (None, ""):
                eps.append((m, i, float(r["rtf_med"]), float(r["rtf_mean"] or r["rtf_med"])))
eps.sort()
if since:
    eps = [e for e in eps if e[0] > since]
lst = eps[-K:]
if not lst:
    print("nan nan 0 0"); sys.exit()
print(f"{st.median([e[2] for e in lst]):.3f} {st.median([e[3] for e in lst]):.3f} {len(lst)} {lst[-1][0]:.0f}")
