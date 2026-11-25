import csv,collections,glob,math
from math import comb
def wil(k,n,z=1.96):
    p=k/n;d=1+z*z/n;c=(p+z*z/2/n)/d;h=z*math.sqrt(p*(1-p)/n+z*z/4/n/n)/d;return c-h,c+h
rows=[]
for f in sorted(glob.glob("results/final_office_w[01]/trials.csv")): rows+=list(csv.DictReader(open(f)))
by=collections.defaultdict(list)
for r in rows: by[r['config']].append(r)
F=lambda x: float(x) if x not in ('',None) else None
def stat(r): return F(r['min_clear_m']) is not None and F(r['min_clear_m'])<0
def ppl(r): return F(r['min_person_gap_m']) is not None and F(r['min_person_gap_m'])<0
S=lambda rs: sum(int(r['success']) for r in rs)
ref={(r['task'],r['trial']):int(r['success']) for r in by['prism@ppo+sac']}
print("rows",len(rows))
print("cfg                        n  ok  Wilson%   | stat ppl pplfault blank | robotcaused | clut crowd | McN b/c p")
for c,rs in sorted(by.items(),key=lambda kv:-S(kv[1])):
    n=len(rs);k=S(rs);lo,hi=wil(k,n)
    st=sum(stat(r) for r in rs);pp=sum(ppl(r) for r in rs)
    pf=sum(ppl(r) and r['at_fault']=='1' for r in rs)
    rc=sum(stat(r) or (ppl(r) and r['at_fault']=='1') for r in rs)
    af=sum(r['at_fault']=='1' for r in rs)
    cl=[r for r in rs if r['cat']=='clutter'];cr=[r for r in rs if r['cat']=='crowd']
    b=sum(ref[(r['task'],r['trial'])]>int(r['success']) for r in rs);cc=sum(ref[(r['task'],r['trial'])]<int(r['success']) for r in rs)
    m=b+cc;p=min(1,2*sum(comb(m,i) for i in range(min(b,cc)+1))/2**m) if m else 1
    print(f"{c:26s} {n} {k:3d} {100*k/n:3.0f} [{100*lo:.0f}-{100*hi:.0f}] | {st:2d} {pp:2d} {pf:2d} af={af:2d} | {rc:2d} | {S(cl)}/{len(cl)} {S(cr)}/{len(cr)} | {b}/{cc} p={p:.3f}")
