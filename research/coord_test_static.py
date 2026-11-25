"""Nhanh VAT TINH (PREREG_TEST bo sung #2): chay fastsim tu ban chup chi-doc tren cac seed KHONG co nguoi.
Dao bo loc --crowd-only CHI trong tien trinh cha (worker van dung gen_world that)."""
import sys, os
SNAP = "/home/nhanhuynh/Documents/Go2_assitant/results/frozen_C1/snap"
sys.path.insert(0, SNAP); os.chdir(SNAP)
import fastsim as F
_orig = F.gen_world
F.gen_world = lambda s: {"crowd": not _orig(s)["crowd"]}
regime, out = sys.argv[1], sys.argv[2]
sys.argv = ["fastsim.py", "--suite", "gen", "--seeds", "100000-101386", "--crowd-only", "--regime", regime, "--crowd-model", "base",
            "--out", out, "--jobs", "14", "--configs",
            "p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5", "mppi~t3~nl:ppl=100;ppl_len=0.5", "pgif~t3~nl:w_h=300;sig_scale=0.7;hard=5000",
            "dra~t3~nl:w_soft=300;w_hard=0;sig_w=1.2;sig0=0.05", "mppi:ppl=32", "dwa~t3~nl:ppl=100;ppl_len=0.3", "log_mppi~t3~nl:ppl=100;ppl_len=0.5"]
F.main()
