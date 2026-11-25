import csv,glob,json,numpy as np,collections
for d,cs in (("dev3",["mppi","mppi:ppl=32","p2+turn"]),):
    R=[r for f in glob.glob(f"results/{d}/w*.csv") for r in csv.DictReader(open(f))]
    for c in cs:
        C=[json.loads(r["info"]) for r in R if r["config"]==c and r["col"]=="person"]
        b=np.array([abs(x["bearing"]) for x in C]); print(c,len(b),"mui<30:%.2f 30-60:%.2f hong 60-120:%.2f 120-150:%.2f duoi>150:%.2f"%tuple(np.mean((b>=a)&(b<z)) for a,z in ((0,30),(30,60),(60,120),(120,150),(150,181))), "person_in %.2f robot_in %.2f at_fault %.2f distracted %.2f"%(np.mean([x["person_in"] for x in C]),np.mean([x["robot_in"] for x in C]),np.mean([x["at_fault"] for x in C]),np.mean([x.get("distracted",0) for x in C])))
