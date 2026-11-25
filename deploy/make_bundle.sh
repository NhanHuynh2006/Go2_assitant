#!/bin/bash
# make_bundle.sh (REALPREP) - CHAY TREN LAPTOP. Dong goi DUNG cac file can tren cho, kiem sha dong bang truoc.
#   bash deploy/make_bundle.sh            -> dist/govoice_real_<ngay>.tar.gz + deploy/MANIFEST.sha256
# Chep len cho (khi da o canh cho, ngay thi nghiem; KHONG lam tu xa khi chua co nguoi):
#   scp -i ~/.ssh/go2_key dist/govoice_real_<ngay>.tar.gz unitree@192.168.123.18:~/
#   ssh -i ~/.ssh/go2_key unitree@192.168.123.18 'mkdir -p ~/govoice_real && tar xzf ~/govoice_real_<ngay>.tar.gz -C ~/govoice_real'
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[1] kiem sha256 dong bang (results/frozen_C1/SHA256SUMS_TEST)"
sha256sum -c --quiet results/frozen_C1/SHA256SUMS_TEST
echo "    OK: moi file dong bang khop"
FROZEN=(nav_local.py nav_prism2.py robot_ros.py isaac_val/cmd_shaper.py research/algo_fast/fast.c
        fastsim.py movers.py crowd_models.py oracle_ctrl.py dyn/go2_params.py dyn/go2_params.yaml)
RUNTIME=(robot_real.py reflex_matcher.py dyn/__init__.py dyn/bagio.py)
SYSID=(dyn/sysid_real.py dyn/HUONG_DAN_DO.md)
DEPLOY=(deploy/real_trial.py deploy/replay_perception.py deploy/bench_steps.py deploy/py38check.py
        deploy/caminfo_relay.py deploy/start_stack.sh deploy/estop.sh deploy/verify_on_dog.sh deploy/DEPLOY.md)
DOCS=(results/frozen_C1/SHA256SUMS_TEST research/FROZEN.md audit/REAL_PREREG.md audit/REAL_SCHEDULE.csv audit/real_power.py CHECKLIST_CHO_THAT.md)
ALL=("${FROZEN[@]}" "${RUNTIME[@]}" "${SYSID[@]}" "${DEPLOY[@]}" "${DOCS[@]}")
for f in "${ALL[@]}"; do [ -f "$f" ] || { echo "THIEU $f"; exit 2; }; done
# moi file dong bang trong goi PHAI nam trong SHA256SUMS_TEST
for f in "${FROZEN[@]}"; do grep -q "  $f\$" results/frozen_C1/SHA256SUMS_TEST || { echo "$f khong co trong SHA256SUMS_TEST"; exit 2; }; done
sha256sum "${ALL[@]}" > deploy/MANIFEST.sha256
printf '%s\n' "${FROZEN[@]}" > deploy/FROZEN_IN_BUNDLE.txt
mkdir -p dist
OUT=dist/govoice_real_$(date +%Y%m%d).tar.gz
tar czf "$OUT" "${ALL[@]}" deploy/MANIFEST.sha256 deploy/FROZEN_IN_BUNDLE.txt
echo "[2] $OUT ($(du -h "$OUT" | cut -f1)), ${#ALL[@]} file"
sha256sum "$OUT" | tee "$OUT.sha256"
echo "[3] tren cho: cd ~/govoice_real && bash deploy/verify_on_dog.sh"
