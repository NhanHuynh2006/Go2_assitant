"""Nhanh Isaac TEST (PREREG_TEST §3, Lech #3; uy quyen cua dieu phoi vien 25/11 00:15).
Boc MONG quanh isaac_sim.py da bam (khong sua no): isaac_sim.main() chan seed > 999 bang assert, nen ta goi main() voi --seeds 0-0
(qua assert) va thay ham chon the gioi bang danh sach TEST co dinh: 600 the gioi co nguoi dau tien tu 100000 (= results/TEST_go2_base,
trung voi moi o fastsim TEST). Moi logic con lai (chia shard, chay, ghi) la cua isaac_sim.py da bam."""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
import isaac_sim as I
TEST = json.load(open(os.path.join(D, "test_worlds.json")))
assert len(TEST) == 600 and TEST[0] >= 100000
I.worlds = lambda lo, hi, only, nmax: list(TEST)
args = [a for a in sys.argv[1:]]
assert "--seeds" not in args and "--shaper" not in args
sys.argv = [sys.argv[0], "--seeds", "0-0"] + args
I.main()
