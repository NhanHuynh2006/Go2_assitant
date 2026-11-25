#!/bin/bash
# research/algo_run.sh <out> <seeds> cfg... : fastsim DEV, 8 tien trinh, ban C cua A*
cd "$(dirname "$0")/.."
export OPENBLAS_NUM_THREADS=1 GOVOICE_FAST_SO=$PWD/research/algo_fast/fast.so
o=$1; s=$2; shift 2
exec venv/bin/python research/algo_oracle.py --suite gen --seeds $s --crowd-only --configs "$@" --out results/$o --jobs ${J:-8} $EXTRA
