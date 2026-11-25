"""THAM DO (agent HM95): chay fastsim tu ban chup chi-doc voi --crowd-model hm95 (crowd_hm95.py), KHONG sua fastsim.py/crowd_models.py.
Va trong tien trinh (cha VA worker, vi fastsim chay worker bang subprocess `python fastsim.py --worker`):
  * argparse: them 'hm95' vao choices cua --crowd-model (meta.json ghi crowd_model=hm95);
  * crowd_models.pm_step (trong bo nho): pm == 'hm95' -> crowd_hm95.pm_step_hm95, con lai goi ham goc;
  * subprocess.Popen: thay duong dan fastsim.py bang file nay de worker cung duoc va.
Dung: python research/hm95_fastsim.py <cac doi so fastsim thuong, vd --suite gen --seeds 0-19 --crowd-model hm95 ...>"""
import sys, os, argparse, importlib.util, subprocess
SNAP = "/home/nhanhuynh/Documents/Go2_assitant/results/frozen_C1/snap"
HERE = os.path.abspath(__file__)
HM = os.path.join(os.path.dirname(os.path.dirname(HERE)), "crowd_hm95.py")
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(HERE)]   # nhu chay fastsim.py tu SNAP
for _i, _a in enumerate(sys.argv[:-1]):                 # --out/--worker tuyet doi TRUOC khi chdir (khong ghi vao ban chup)
    if _a in ("--out", "--worker"):
        sys.argv[_i + 1] = os.path.abspath(sys.argv[_i + 1])
sys.path.insert(0, SNAP); os.chdir(SNAP)
_spec = importlib.util.spec_from_file_location("crowd_hm95", HM)
hm = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hm); sys.modules["crowd_hm95"] = hm
if os.environ.get("HM95_CONTACT") == "1":
    hm.CONTACT = True

_add = argparse._ActionsContainer.add_argument


def _add_arg(self, *a, **k):
    if "--crowd-model" in a and k.get("choices"):
        k["choices"] = list(k["choices"]) + ["hm95"]
    return _add(self, *a, **k)


argparse._ActionsContainer.add_argument = _add_arg
import fastsim as F                      # noqa: E402
import crowd_models as CM                # noqa: E402
assert os.path.dirname(os.path.abspath(F.__file__)) == SNAP and os.path.dirname(os.path.abspath(CM.__file__)) == SNAP
_pm = CM.pm_step
CM.pm_step = lambda c, dt, pm: hm.pm_step_hm95(c, dt) if pm == "hm95" else _pm(c, dt, pm)
_FS = os.path.abspath(F.__file__)
_Popen = subprocess.Popen


def _popen(cmd, *a, **k):
    if isinstance(cmd, list):
        cmd = [HERE if c == _FS else c for c in cmd]
    return _Popen(cmd, *a, **k)


subprocess.Popen = _popen
if __name__ == "__main__":
    if "--worker" in sys.argv and os.environ.get("HM95_STATS"):
        import atexit, json
        atexit.register(lambda: open(os.environ["HM95_STATS"], "a").write(json.dumps(hm.STATS) + "\n"))
    F.main()
