# REPRODUCE — regenerate every table and figure of the paper package

All paths are relative to the project root `~/Documents/Go2_assitant`. Built 2026-11-24 by agent PAPER.

## 0. Contents of `results/paper_package/`
| Path | What |
|---|---|
| `make_all.py` | the only generator; reads raw CSVs, writes `tables/`, `figures/`, `checks/` |
| `tables/T1_main_TEST.{csv,tex}` | main TEST results, 7 planners × 5 cells + pooled, Wilson CIs |
| `tables/T2_primary_family.{csv,tex}` | pre-registered family: Δ, bootstrap CI, permutation p, Holm |
| `tables/T3_percell_mcnemar.{csv,tex}` | per-cell exact McNemar, Holm over 15 |
| `tables/T4_failure_breakdown.{csv,tex}` | person / static / stuck / timeout / no path, per cell and pooled |
| `tables/T5_static_only.{csv,tex}` | static-only arm |
| `tables/T6_ablation.{csv,tex}` | round-2 ablation + round-3 simplification (non-inferiority) |
| `tables/T7_compute_time.{csv,tex}` | ms per control step |
| `tables/T8_dynamics.{csv,tex}` | CHAMP vs champ/champ2 vs Isaac vs real Go2 (DYN), with sources and flags |
| `tables/T9_fidelity_isaac.{csv,tex}`, `tables/T9_isaac_v3.csv` | fastsim–Gazebo rank correlation, Isaac cross-check |
| `tables/T10_replication.{csv,tex}` | R1, R2, R3, VAL, TEST |
| `tables/T11_gazebo_TEST.{csv,tex}` | Gazebo TEST (PREREG §2); make_all also runs the hashed `research/coord_gz_test_analyze.py` (sha checked against `results/frozen_C1/SHA256SUMS_GZ_ANALYSIS`) and compares lines. DRA\* row is filled automatically only when `results/GZ_TEST_DRA` holds ≥ 340 worlds (partial runs are never read into tables) |
| `tables/T11b_isaac_TEST.{csv,tex}` | Isaac TEST (PREREG §3, deviations #3–#4); replica of hashed `isaac_val/test_stats.py`, checked line by line against `results/ISAAC_TEST/stats.txt` |
| `tables/T11_gazebo_TEST_PLACEHOLDER.md` (superseded note), `tables/T12_real_dog_PLACEHOLDER.md` | real robot: placeholder, no numbers |
| `figures/F1…F6 .{pdf,png}` | figures (Okabe–Ito colours + marker/hatch coding for grayscale); F6 = Gazebo TEST example from stored episode logs (fixed selection rule); `F6_SKIPPED.txt` now marked superseded |
| `checks/CHECKS.txt` | 119 reproduction checks against the coordinator/agent outputs (0 mismatches at build, 25/11 ~14:20) |
| `checks/INPUT_SHA256SUMS` | SHA-256 of all 537 raw input files read |
| `checks/OUTPUT_SHA256SUMS` | SHA-256 of every generated table/figure |
| `DRAFT_results.md`, `DRAFT_limitations.md`, `NOVELTY.md` | English drafts (NOVELTY §5 = verification log of 25/11) |
| `MANUSCRIPT.md`, `refs.bib` | full manuscript draft v0.1 (pandoc citations; all DOIs/arXiv IDs checked against Crossref/arXiv on 25/11; `bibtex` parses it) |
| `make_method_figure.py` → `figures/F0_architecture.{svg,pdf,png}` | method/architecture figure; called by `make_all.py` |

LaTeX tables need `\usepackage{booktabs,graphicx}` (each table is a `table*` wrapped in `\resizebox{\textwidth}{!}{…}`).

## 1. Verify the frozen code (read-only)
```bash
cd ~/Documents/Go2_assitant
sha256sum -c results/frozen_C1/SHA256SUMS            # 11 files: code used for VAL
sha256sum -c results/frozen_C1/SHA256SUMS_TEST       # 16 files: + fast.so, eval_sim.py, gen_gazebo_test.py, PREREG_TEST.md, run_gz_groups.sh
(cd results/frozen_C1/snap && sha256sum -c --quiet ../SHA256SUMS_SNAP && echo SNAP_OK)   # read-only snapshot used for TEST
sha256sum results/frozen_C1/code.tgz                  # 3c6a458c1d7aad3faa0b6510cffb50f41b93d46a72604e85314f3370a38788b8 at build time
sha256sum -c results/frozen_C1/SHA256SUMS_GZ_ANALYSIS     # Gazebo TEST analysis script
sha256sum -c --quiet results/frozen_C1/SHA256SUMS_ISAAC && sha256sum -c results/frozen_C1/SHA256SUMS_ISAAC_TEST   # Isaac TEST code + wrapper/analysis
```
All checks passed when this package was built (2026-11-24 ~20:50; GZ/Isaac files 2026-11-25 ~14:00).

## 2. Verify the raw inputs
```bash
sha256sum -c --quiet results/paper_package/checks/INPUT_SHA256SUMS && echo INPUTS_OK
```

## 3. Regenerate everything (one core, ~25 s)
```bash
cp results/paper_package/checks/OUTPUT_SHA256SUMS /tmp/expected_outputs      # keep the reference first
# NOTE: until the Gazebo DRA* arm finishes, T11 shows a 'running' row; once results/GZ_TEST_DRA has >= 340 worlds the T11 outputs change by design
OPENBLAS_NUM_THREADS=1 nice -n 19 venv/bin/python results/paper_package/make_all.py
#   -> prints "checks: 97, mismatches: 0"; exit status 1 if any reproduction check fails
diff /tmp/expected_outputs results/paper_package/checks/OUTPUT_SHA256SUMS && echo BYTE_IDENTICAL
```
Determinism: every random procedure has a fixed seed (primary family `default_rng(20261124)` exactly as
`research/coord_val_analyze.py`; ablation and round-3 non-inferiority `default_rng(0)` exactly as `research/algo_confirm.py` /
`algo_noninf.py`; other bootstraps 20261125–20261129). PDF/PNG metadata dates are stripped. Two consecutive runs gave
byte-identical outputs. Byte identity of figures assumes the same library versions:
Python 3.14.4, numpy 2.5.2, scipy 1.18.1, matplotlib 3.10.9, PyYAML 6.0.3 (project `venv`). With other versions the CSV/LaTeX
numbers must still be identical; PNG/PDF bytes may differ.

## 4. Cross-check against the coordinator's own analysis scripts
```bash
venv/bin/python research/coord_val_analyze.py results/TEST_ | diff - research/TEST_fastsim_results.txt && echo TEST_SAME
venv/bin/python research/coord_val_analyze.py results/VAL_  | diff - research/VAL_results.txt       && echo VAL_SAME
```
Both were identical at build time. The static-arm script of the coordinator was not saved; `make_all.py` reproduces every
number of `research/TEST_static_results.txt` (bootstrap: one shared `default_rng(20261124)` stream, 20 000 resamples).

## 5. Where the raw data come from (re-running experiments is NOT part of the paper build)
fastsim is deterministic: rerunning a cell from the frozen snapshot reproduces the CSVs row for row (checked by AUDIT/GAZEBO,
e.g. 735/735 rows). **TEST seeds (≥ 100000) may only be run by the coordinator (PROTOCOL rule 1).**
| Data | Directory | Command (coordinator) |
|---|---|---|
| TEST, 5 cells × 7 planners | `results/TEST_{champ,champ2,go2}_{base,helb}` | `SEEDS=100000-101386 bash research/coord_test_fastsim.sh` (runs from `results/frozen_C1/snap`, checks SHA256SUMS_SNAP before each cell, refuses non-empty output dirs) |
| Static-only arm | `results/TESTSTATIC_{champ,champ2,go2}` | `bash research/coord_test_static.sh` (wraps `research/coord_test_static.py`, which inverts the crowd filter in the parent process; meta.json still says crowd_only=true) |
| VAL | `results/VAL_*` | `bash research/coord_val.sh` (seeds 2000–2399) |
| Confirmation R1/R2/R3 | `results/algo_V*`, `algo_W*`, `algo_Y*` | ALGO scripts `research/algo_stage.sh` (R1, seeds 300–799), `algo_stage3.sh` (R2, 1000–1499), `algo_stage5.sh` (R3, 1500–1999), via `research/algo_run.sh` |
| Ablation / non-inferiority | `research/algo_ablation2.txt`, `algo_noninf3.txt` | `research/algo_confirm.py`, `research/algo_noninf.py` (reproduced inside make_all.py) |
| Timing | `research/algo_timing.txt` | `venv/bin/python research/algo_timing.py 93 <configs>` (with/without `GOVOICE_FAST_SO`) — machine-dependent, parsed not re-measured |
| Gazebo smoke | `results/GZ_smoke/smoke_check.txt` | `research/gz/run_smoke.sh`, `research/gz/smoke_check.py` |
| CHAMP identification | `results/sysid.npz` | `pipeline/sysid.py`; fit `pipeline/sysid_fit2.py` (make_all.py executes only its data/model part, not the grid search) |
| Isaac dynamics tables | `isaac_val/tables_random.md` | `isaac_val/analyze_random.py` (Isaac Lab 5.1 env in `~/isaac`; parsed, not recomputed) |
| Isaac pilot / v3 runs | `isaac_val/res_pilot.csv`, `res_{nl,t3,nlnotilt,nlcs}.csv` | `isaac_val/pilot_stats.py`, `run_*.sh` (needs GPU + `~/isaac`) |
| Real Go2 dynamics | `dyn/go2_params.yaml` | `dyn/analyze_bags.py` on `~/go2_maps/*/*.db3` (read-only logs) |
| Fidelity | `results/coord_fid_{champ,champ2}`, `results/final_office_merged/trials.csv` | fastsim `--suite office` 8 tasks × 4 trials × 12 planners; Gazebo: 960 earlier episodes |

## 6. Updating the placeholders
When `results/GZ_TEST` is final, add a loader to `make_all.py` that implements PREREG_TEST §2 (exact McNemar C1 vs B1 on complete
pairs; DRA\* only if gated) and replace `T11_gazebo_TEST_PLACEHOLDER.md` by generated CSV/LaTeX. Never type numbers by hand.
