"""In cac dong LOG cua AUDIT ra audit/LOG_AUDIT_rows.csv (KHONG ghi vao research/LOG.csv; dieu phoi vien tu noi)."""
from a10_results import load
NOTE = dict(base="ban chup code 23:01 (audit/snap), chan doan", real="regime real cu", cmd2="tre lenh 0.2 s", seen2="tre thay nguoi 0.2 s",
            dis0="0% mai dien thoai", dis6="60%", fast="toc do nguoi x1.3", slow="x0.7", dense="+3 nguoi", wob0="khong lac than",
            real_body="than 0.70x0.31", soft5="bo qua cham nong <5 cm", mous="nguoi Moussaid 2009", helb="nguoi Helbing A=7 B=.3",
            future="chan doan muc tran, oracle")
rows = []
for c, nt in NOTE.items():
    for q, v in sorted(load(c).items()):
        rows.append(f'2026-11-23,AUDIT,"{q}",audit/{c}(seed {min(v)}-{max(v)} crowd-only),{len(v)},{sum(int(r["success"]) for r in v.values())},"{nt}"')
with open("LOG_AUDIT_rows.csv", "w") as f:
    f.write("\n".join(rows) + "\n")
print(len(rows), "dong;", sum(int(r.split(",")[-3]) for r in rows), "luot")
