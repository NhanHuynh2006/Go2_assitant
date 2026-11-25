#!/bin/bash
cd "$(dirname "$0")/.."; export OPENBLAS_NUM_THREADS=1
while kill -0 649623 2>/dev/null; do sleep 5; done
for c in real cmd2 dis6 dis0 seen2 fast dense wob0 real_body soft5 slow; do
  venv/bin/python audit/fs_audit.py --cond $c --n 40 --lo 150 --configs mppi "mppi:ppl=32" p2+turn --jobs 3 --out audit/out/$c
done
echo xong > audit/out/DONE
