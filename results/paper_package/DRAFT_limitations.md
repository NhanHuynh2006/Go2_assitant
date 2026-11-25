# DRAFT — Limitations (English, for the paper; honest version)

Each item states the limitation, the evidence and its size, and what would remove it. Sources are files in the project;
table/figure numbers refer to `results/paper_package/`.

1. **Simulation only, so far.** Every confirmatory number comes from fastsim, a 2-D virtual-clock simulator that runs the real
   planner code but simulates the body, the LiDAR rays and the pedestrians. The pre-registered Gazebo TEST (680 worlds, C1 vs B1)
   is still running (placeholder T11), the Isaac Lab cross-check is a 100-world exploratory pilot (T9), and **no navigation run
   with C1 has been made on the real Unitree Go2** (placeholder T12). The paper must not claim real-world performance. (Update 25/11: Gazebo TEST done — C1 80.7 % vs B1 65.7 %, p = 1.5e-13, read with item 5; Isaac TEST done — C1 vs DRA\* n.s., p = 0.46; Isaac is independent only in body dynamics.)

2. **The advantage over DRA-MPPI\* is small and condition-dependent.** Pooled on TEST, C1 − DRA\* = +2.66 points [+1.52, +3.80]
   (Holm 1.5e-5), but per cell it is significant only in CHAMP2/base (+5.9, Holm 1.4e-4). In CHAMP/base (+1.7), Go2/base (+1.4),
   CHAMP2/Helbing (+3.5, Holm 0.064) and **Go2/Helbing (+0.8, Holm 0.86)** it is not. With a fast robot and Helbing-type
   pedestrians C1 is statistically indistinguishable from B1 (+1.8, Holm 0.48), PGIF\* (+1.4, Holm 0.86) and DRA\*. The gap to
   PGIF\* is likewise null in both Helbing cells. The benefit therefore concentrates on slow robots (CHAMP: commands clipped at
   0.3 m/s) facing the base crowd model; it should not be described as a general improvement over the state of the art.

3. **Unequal tuning budget, in favour of C1.** Development log (research/LOG.csv, audit/PREREG_TEST.md §7): the p3/C1 family was
   tuned over ~60 configurations (~31 000 episodes) on all five cells and ~500 worlds; MPPI with tracker v3 over 21 configurations;
   PGIF\* and DRA\* over 35 configurations each, but only in the CHAMP/base cell on seeds 0–149. This violates our own protocol rule
   ("baselines tuned with at least as many trials as the proposed method") and biases the comparison towards C1, especially in
   the cells where PGIF\*/DRA\* were never tuned (CHAMP2, Go2, Helbing). The TEST run cannot correct this. Total recorded trials
   for multiplicity: 600 rows in research/LOG.csv plus 49 in audit/LOG_AUDIT_rows.csv.

4. **Static-only worlds: C1 is non-inferior but worse than B1.** In the pre-registered static-only arm (387 worlds × 3 regimes),
   C1 reached 96.9 % vs 97.8 % for B1: −0.95 points [−1.55, −0.34]. Non-inferiority (margin −2) holds, but the deficit is real and
   comes entirely from more "stuck" episodes (3.1 % vs 2.2 %); DWA (99.5 %) and B0 (99.0 %) are better still (T5). The likely cause
   (not tested in a controlled way) is that tracker v3 creates or keeps person tracks on static clutter, so the planner waits.

5. **Gazebo ghost tracks from CHAMP body wobble (smoke test S4 failed).** In the mandatory Gazebo smoke test (DEV worlds only), the
   shared tracker v3 confirmed static objects as "people" for more than 2 s in 10/10 static-task episodes with C1 and 9/10 with B1
   (on average 6 ghost tracks per episode, longest 54 s for C1 and 144 s for B1). 83 % of ghosts lie within 0.3 m of a static
   surface; ghost rate is flat in |wz| (not a timing error; scan–odometry stamp offset p95 20 ms); ghosts appear only when the
   simulated body tilts ≥ 2° (CHAMP |roll| p95 8.1°, versus ~0.5–0.6° wobble measured on the real dog: roll/pitch 0.010/0.011 rad, dyn/go2_params.yaml), so the 16-beam LiDAR cuts objects at
   different heights. Replaying with interpolated poses did not remove them. Because no integration bug existed, the frozen code
   was not changed and Gazebo TEST runs as registered (deviation #1 in PREREG_TEST §9). Gazebo results — whichever way they go —
   must be read with this artefact, which affects both planners but through different planning layers. A tilt-robust static
   filter for the tracker is future work.

6. **Simulated pedestrians turn more than real ones.** Compared with the THÖR dataset (Zenodo 3382145, CC BY 4.0; 5 sessions,
   94 min), fastsim pedestrians make strong turns ~1.7× more often at normal walking speed (0.6–1.2 m/s), > 60° turns within 2 s
   ~2.8× more often, and stop/start ~2× more often (research/REPORT_SEV.md). The rooms differ (laboratory vs five generated map
   families), so this is not a controlled comparison. Since C1's advantage is largest for late-turning pedestrians, the size of the
   benefit with real pedestrians is unknown and may be smaller. Pedestrians also replan with the same A\* planner as the robot,
   which would leak information to any intention-based predictor (C1 uses constant velocity only; a geodesic intention fan was
   tried and did not help).

7. **Which simulated CHAMP dynamics is "right" is unresolved.** `champ2` predicts the logged CHAMP motion better (2-s error
   0.062 vs 0.088 m, both halves of a split log), yet it agrees *less* with closed-loop Gazebo outcomes (Spearman 0.59 vs 0.90 over
   12 planners); the difference, +0.31 with task-bootstrap 95 % CI [−0.13, +0.42], is inconclusive (8 tasks only, and the earlier
   choice of `champ` was itself made because it raised this correlation, a selection effect). Within the MPPI family alone the
   fastsim–Gazebo correlation cannot be established in either direction (AUDIT: 7 planners, CI [−0.56, 0.87]). We report all three
   regimes as robustness conditions and make no claim about which one Gazebo follows.

8. **Re-implemented baselines with deviations.** PGIF\* and DRA\* were re-implemented from the papers' equations (arXiv
   2608.08323 and 2506.21205), not run from the authors' code (PGIF-MPPI code is MIT-licensed but JAX and assumes known pedestrian
   states; DRA-MPPI code has no licence, so it was not read). Deviations: two-disc robot footprint instead of a point/one disc;
   cost weights rescaled to our cost scale and tuned (`w_h`, `sig_scale`, optional hard penalty 5000 for PGIF\*; `w_soft`, `w_hard`,
   `sig_w`, `sig0` for DRA\*); DRA\* collision probability computed exactly with a non-central χ² lookup table instead of 20 000-sample
   Monte Carlo; the multi-modal turning model of DRA-MPPI was not included (single Gaussian with growing σ); the best DRA\*
   disables the hard threshold (ω_hard = 0) and uses σ_w four times the paper value. Both baselines receive our tracker v3,
   RespModel, K and horizon, but none of C1's sampling changes. Reviewers may reasonably ask for runs of the original code.

9. **Inverse-crime risk.** (a) The online response model `~nl` assumes a tanh-saturation + first-order-lag shape — exactly the
   form of the `champ` regime in fastsim. Mitigation: C1 also wins under `champ2` and `go2`, B1 uses the same `~nl`, and removing
   `~nl` from C1 changes success by only −0.4 points (n.s., T6), so the C1 advantage does not hinge on it; but the absolute numbers
   of every `~nl` planner in the `champ` cells benefit from the matching model. (b) Tracker v3 pushes cluster centroids outward by
   0.64 × cluster radius, matching fastsim's circular pedestrians; this geometric prior may be optimistic for real legs/bodies.
   (c) The same people model, ray caster and tracker are shared by fastsim and the Isaac cross-check, so Isaac checks only the body
   dynamics.

10. **Real-dog dynamics partly assumed.** The `go2` regime samples per episode from dyn/go2_params.yaml. Measured on our own dog
    (LiDAR-odometry reference, two logs, one site): odometry scale, stopping distance (~0.28 s × v0, upper bound), body wobble and
    acceleration lower bounds. **Not measured**, because no log contains velocity commands: command gain (0.95, indirect/literature),
    time constants (literature for x/y, assumed for yaw), command delay (0.10 s, assumed), reverse gain and dead-band (assumed),
    lateral motion (no data). Isaac policies show a dead-band at small commands that we did not put into `go2`. The measurement
    protocol dyn/HUONG_DAN_DO.md has not been executed.

11. **Other threats to validity.**
    - *Metric sensitivity.* The primary metric counts any contact; in earlier Gazebo data 56 % of person contacts were shallower than
      5 cm (comparable to body wobble), so absolute success rates depend on the contact criterion. The fastsim "at-fault" flag is
      not interpretable (|wz| > 0.3 rad/s in 63 % of walking samples) and is reported only as a count.
    - *One episode per world and cell*; pedestrian density, the 30 % distracted-pedestrian rate and the crowd models are simulator
      assumptions (AUDIT found density to be the most influential assumption). The `helb` model is a Helbing–Molnár-type circular
      potential written from memory and not yet checked against the original paper; the code comment citing Moussaïd (2009) for
      `movers.py` is wrong and must not be cited.
    - *Seed ranges.* Confirmation rounds R1–R3 used seeds 300–1999, nominally inside the development range; they were used only for
      confirmation after locking a candidate, but they are not "untouched" in the strict sense. Only VAL and TEST are clean.
    - *Occlusion* is not handled explicitly (an occlusion-aware variant was rejected on DEV); the Go2 LiDAR blind zone near the body
      is modelled only as in fastsim.
    - *Isaac falls.* The learned Isaac policy fell 6/100 (C1) and 5/100 (B1) times in the pilot, linked to slow reverse/turning
      commands; this says nothing about the Unitree SportClient controller, but reverse + slow turning must be tested first and
      tethered on the real robot.
    - *Compute* was measured on the development laptop and in Gazebo, not on the Jetson Orin.
    - *Licences.* Isaac Sim/Lab under the NVIDIA Omniverse EULA (accepted by the user); THÖR CC BY 4.0; ETH/UCY copies used for
      comparison only (licence unclear, not redistributed); no third-party code was copied into the planners.
