"""THAM DO (coordinator, 26/11): anh huong cua kep vy 0.15 (chó thật, REAL_PREREG sửa đổi #1) trong fastsim regime champ2.
Chay fastsim tu ban chup chi-doc; va Sim.__init__ (cha VA worker) de lim[1] = VY_CAP khi regime champ2. KHONG sua fastsim.py.
Dung: VY_CAP=0.15 python research/vy15_fastsim.py <doi so fastsim>"""
import sys, os, importlib, subprocess
SNAP = "/home/nhanhuynh/Documents/Go2_assitant/results/frozen_C1/snap"
HERE = os.path.abspath(__file__)
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(HERE)]
for _i, _a in enumerate(sys.argv[:-1]):
    if _a in ("--out", "--worker"):
        sys.argv[_i + 1] = os.path.abspath(sys.argv[_i + 1])
sys.path.insert(0, SNAP); os.chdir(SNAP)
import fastsim as F                      # noqa: E402
assert os.path.dirname(os.path.abspath(F.__file__)) == SNAP
CAP = float(os.environ.get("VY_CAP", "0.15"))
_init = F.Sim.__init__


def _init2(self, W, config, trial, regime="champ", oracle=False, tmax=300.0):
    _init(self, W, config, trial, regime=regime, oracle=oracle, tmax=tmax)
    if regime == "champ2":
        self.lim = self.lim.copy(); self.lim[1] = min(self.lim[1], CAP)


F.Sim.__init__ = _init2
_FS = os.path.abspath(F.__file__); _Popen = subprocess.Popen
subprocess.Popen = lambda cmd, *a, **k: _Popen([HERE if c == _FS else c for c in cmd] if isinstance(cmd, list) else cmd, *a, **k)
if __name__ == "__main__":
    F.main()
