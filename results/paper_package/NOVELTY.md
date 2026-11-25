# NOVELTY — what is new in C1 versus the closest work (English, for Introduction / Related Work)

**Bottom line (state this plainly in the paper): no single component of C1 is new.** Constant-velocity Kalman tracking,
sample-based MPC (MPPI) with pedestrian costs, risk terms around predicted pedestrians, adaptive MPPI temperature, biased /
primitive sampling and online model adaptation all exist. The contribution is (i) the **combination**, engineered for a robot
that is about three times slower than the pedestrians it must avoid and that has a long body and measured, saturating
dynamics, and (ii) a **rigorous, pre-registered evaluation protocol** with tuned baselines that share the same perception.

Sources: `research/LIT.md` (LIT, 22/11) and `research/REPORT_OSS.md` (OSS, 22/11). Reading levels as recorded there:
**[TV]** method + experiments read in full text; **[MP]** full text fetched, only abstract/intro/relevant parts read;
**[TT]** abstract or catalogue page only; **[MÃ]** source code inspected. Items marked ⚠ were checked on 25/11; see §5 for the verification log (one item still unverified).

## 1. What C1 is (frozen: `p3+geo-haz+gcv~t3~nl:ppl=32;ppl_len=0.5`)
- **Tracker v3 (`~t3`)**: constant-velocity Kalman filter, static-background subtraction, per-point motion evidence, outward
  compensation of the cluster centroid (0.64 × radius), stopped people kept as people for up to 6 s, tracks held through occlusion
  and the blind zone, "waiting for a tracked person" not counted as stuck. *Shared with all tuned baselines.*
- **RespModel (`~nl`)**: per-axis v = s·tanh(g·u/s) + first-order lag, grid posterior over (g, s) learned online from (command,
  measured velocity). *Shared with all tuned baselines.*
- **p3 planner** (MPPI-based):
  - `prim`: 96 extra samples = maximum-velocity evasive primitives (16 directions × 3 turn modes; full or first 1.2 s);
  - `grad`: temperature λ = 0.3·(15th percentile − min of costs) and a graded collision penalty 300·(1 − t_hit/T) + penetration,
    fixing the degenerate weighting that occurs when most samples collide;
  - `geo` with `gcv`: risk R = max over time of e^(−t/1.2)·f(d), d = clearance between a 2-disc body and each constant-velocity
    pedestrian prediction (time-discounted worst case instead of a sum over steps).
- Ablation (T6): only tracker v3 (−5.8) and `prim` (−4.2) are individually shown to matter; geo/grad/discount/RespModel are not
  individually significant, and geo and grad appear partly interchangeable. The paper must say this.

## 2. Closest work and how C1 differs

| Work | Read | What it does | Overlap with C1 | Difference (claimable, narrow) |
|---|---|---|---|---|
| **PGIF-MPPI**, Mundane (single author), arXiv [2608.08323](https://arxiv.org/abs/2608.08323) (2026, preprint); code MIT [MÃ] | [TV] | Anisotropic Gaussian field around CV-predicted people at every rollout step, closed form, inside MPPI | Closest in role: a forward cone/field around predicted people inside MPPI | PGIF sums over steps without discount, robot 2 m/s (faster than people), point robot, open space, known pedestrian states, baseline = MPPI with static people. C1: discounted max-over-time risk, temperature fix, evasive primitives, real tracker, 2-disc body, robot 3× slower. **Re-implemented and beaten on TEST (+4.98 [3.76, 6.24]) but tie in both Helbing cells.** |
| **DRA-MPPI**, Trevisan, Mustafa et al., arXiv [2506.21205](https://arxiv.org/abs/2506.21205) (IROS 2025); code unlicensed (not read) | [TV] | Joint collision probability with non-Gaussian (mixture) pedestrian predictions incl. random turning (Markov straight→diagonal), Monte Carlo, inside MPPI | Already handles "a pedestrian may turn" inside MPPI | Open-loop (no reaction of the robot after seeing the turn); robot 2 m/s, 6 m corridor, single disc. C1 does not model turning explicitly; its gain over DRA\* is small (+2.66 [1.52, 3.80]) and significant in 1/5 cells. **Do not claim superiority beyond this.** |
| **CN-CBF**, Derajić, Bernhard, Hönig, arXiv [2603.06921](https://arxiv.org/abs/2603.06921) (+ thesis 2610.16522); code MIT [MÃ] | [TV] | HJ reach-avoid game: pedestrian unicycle with adversarial turn rate |ω| ≤ 0.35 rad/s, learned value, softmin over people, QP safety filter; Gazebo + HuNavSim, non-yielding people, real robot | Answers "can the robot still escape if the person turns?" | Ground robot v_r ∈ [0.25, 1.0] m/s, comparable to pedestrians (verified 25/11). OSS's own homicidal-chauffeur derivation suggests that at our speed ratio (γ ≈ 0.32) the infinite-horizon worst-case escape set is essentially empty, motivating finite-horizon, risk-based costs instead of guarantees. No static obstacles, no body orientation, ideal command tracking in CN-CBF. **⚠ STILL UNVERIFIED (25/11, §5)**: the threshold formula was derived by OSS from memory of Isaacs; source PDFs (Isaacs; Pachter & Coates, DGAA 2019) not opened; the numerical min-max check was not finished. Do not print the formula until verified. C1 gives **no** safety guarantee — say so. |
| **C2U-MPPI**, Mohamed, Ali, Liu, RA-L 2025, [2501.08520](https://arxiv.org/abs/2501.08520) | [MP] | Deterministic surrogate of chance constraints with unscented propagation; cooperative / non-cooperative pedestrian modes | Uncertainty-aware pedestrian cost in MPPI | CV + Gaussian, isotropic, robot ≥ 1 m/s, 10 runs per setting. Not re-implemented (we did not compare). Resolved 25/11 (§5): anisotropic Σ_c, UT propagation. |
| **Contingency-MPPI**, Jung, Estornell, Everett, L4DC 2025, [2412.09777](https://arxiv.org/abs/2412.09777); code unlicensed | [TV, method] / [MÃ] | Every nominal state must keep a path to a given safe set within Tc steps (nested MPPI) | Idea "each predicted state must keep an escape" | Fixed static safe set, dynamic agents only in related work, expensive nested optimisation (GPU). C1's evasive primitives are a cheap, non-guaranteed relative of this idea. |
| SCRAMPPI [2603.26995](https://arxiv.org/abs/2603.26995), DualGuard-MPPI [2502.01924](https://arxiv.org/abs/2502.01924) | [TV] / [MP] | HJ value functions used inside MPPI | Value lookup per rollout state | Static/revealed environments, no pedestrians (SCRAMPPI §VII states dynamic obstacles are open). |
| Biased-MPPI, Trevisan & Alonso-Mora, RA-L 2024 | [TV] (25/11) | Mixes samples from auxiliary controllers into MPPI | Same family as `prim` | `prim` is an application of this idea (resolved 25/11, §5). |
| log-MPPI [2203.16599](https://arxiv.org/abs/2203.16599) | [TT] | Log-normal sampling for better exploration | Sampling change | Used as a tuned baseline (log-MPPI); C1 beats it by +7.4 points descriptively. |
| Nav2 MPPI [2307.15236](https://arxiv.org/abs/2307.15236) | [MÃ] | Production MPPI; people only as instantaneous costmap cells; dynamic-obstacle issue #1597 open since 2020 | Base algorithm family | Motivation: standard MPPI reacts late to moving people. |
| Late-turning failures reported by others: HEIGHT [2411.12150 §V-C4], DRL-VO [2301.06512 §IV-C4], ABS [2401.17583 §IX-E], Go2 + video policy [2609.37476] | [TV]/[MP] | Report collisions when people turn/change goals suddenly; robot speed limit prevents recovery | Same phenomenon | Supports the problem statement; cite as motivation, not as baselines. |
| Stochastic reachable sets + APF, **Malone**, Chiang, Lesser, Oishi, Tapia, T-RO 2017 (first author corrected) | [TT, abstract] | Precomputed stochastic reachable sets for moving obstacles | Closest to a probabilistic escape value | Resolved at abstract level 25/11 (§5); full text still closed. |
| VO for capsule-shaped robots, EPFL RA-L 2021 | [TT] | Velocity obstacles with elongated bodies | Body shape | Resolved at abstract level 25/11 (§5). |
| Anisotropic quadruped velocity ellipse, Zhang et al. [2403.10101](https://arxiv.org/abs/2403.10101) | [MP] | Direction-dependent max velocity of legged robots | — | Do **not** claim anisotropic dog dynamics as new. |
| MPPIPS-HWP, Long, Bardaro, Matteucci, ROBIO 2025 | [TT, page 403] | MPPI + learned prediction + audio warning | MPPI + people | Resolved at abstract level 25/11 (§5). |

## 3. Claims we may and may not make
**May (narrow, true on our evidence):**
1. In the surveyed literature we found no MPPI planner that combines, for a robot ~3× slower than pedestrians, (a) a time-discounted
   max-over-horizon geometric risk on a two-disc body, (b) a temperature correction for the many-colliding-samples regime, (c) evasive
   maximum-velocity primitives, and (d) a tracker/response model evaluated jointly — *"we found no"*, not *"first"*.
2. Under a pre-registered protocol (frozen hashes, disjoint DEV/confirmation/VAL/TEST seeds, Holm), with all baselines sharing the same
   perception and response model, C1 beats tuned MPPI, PGIF-MPPI\* and DRA-MPPI\* on 1000 unseen worlds × 5 conditions, and the gaps
   replicate on four further seed sets.
3. The evaluation itself is a contribution: three dynamics regimes (two CHAMP identifications + measured/literature Go2), two crowd
   models, a static-only arm, an Isaac Lab body cross-check, and explicit reporting of null cells, tuning imbalance and failures
   (S4 ghost tracks, static-arm deficit).

**May not:**
- "first to consider turning pedestrians in a safety margin" (CN-CBF, DRA-MPPI), "first closed-form pedestrian cost in MPPI" (PGIF),
  "anisotropic dog dynamics is new", "walls blocking the escape side is new" (CDC 2022 pursuit-evasion), any safety guarantee,
  "outperforms the state of the art" without the condition qualifier, any real-robot claim.
- Any statement that the gain over DRA-MPPI holds with fast robots or Helbing-type pedestrians.

## 4. Open items before submission
1. (Done 25/11, including the homicidal-chauffeur threshold, see §5); re-search with "evasion margin", "escape time", "stochastic reachability pedestrian"
   (LIT searched the web only, no IEEE Xplore access).
2. Decide whether to run the original PGIF-MPPI (MIT) code as an additional check; DRA-MPPI code has no licence (ask the authors).
3. Cite only papers whose links open; mark 2026 arXiv items as preprints.

## 5. Verification log (PAPER, 25/11/2026) — every former ⚠ VERIFY item
Method: arXiv API + Crossref/OpenAlex metadata for every reference in `refs.bib` (all DOIs resolve to the stated titles);
full text read through arXiv HTML where available. "Read" column: what was actually read this time. Nothing was copied.

| Item | Read | What the paper actually does (verified) | Difference to C1 / correction to earlier notes |
|---|---|---|---|
| **C2U-MPPI** (Mohamed, Ali, Liu; RA-L 10(7):7492–7499, 2025, doi 10.1109/LRA.2025.3576071; arXiv 2501.08520) | full text (arXiv HTML v2, methods + experiments) | Chance constraint Pr(collision) ≤ δ approximated as (A_r/η_c)·exp(−½ dᵀΣ_c⁻¹d), Σ_c = Σ_x + Σ_o (full matrix, not isotropic), turned into a deterministic Mahalanobis threshold per step; robot mean/covariance propagated by the **unscented transform** (U-MPPI); pedestrians predicted by a linear Kalman filter with constant velocity; cooperative (social-force) and non-cooperative modes, main analysis non-cooperative; Jackal, max 1.0–2.0 m/s in simulation, 1 m/s real; 10 trials per configuration (e.g. 0 vs 5 collisions vs log-MPPI in a 10-pedestrian scenario); 6 real trials with 5 people. | Earlier note "isotropic" was **wrong** (Σ_c is a full matrix; the experiments use Σ₀ᵒ = I₂). Remains: robot faster than or equal to people, open-loop CV prediction, no evasive primitives, no temperature fix, few trials. We did not re-implement it. |
| **Biased-MPPI** (Trevisan, Alonso-Mora; RA-L 9(6):5871–5878, 2024, doi 10.1109/LRA.2024.3397083; arXiv 2401.09241) | full text (arXiv HTML v2) | One sample per ancillary controller (J samples) plus K−J Gaussian samples around the previous plan; importance weights reduce to exp(−S/λ) so the sampling distribution drops out, at the price of a bias towards the sampling distribution; adaptive λ (×0.9/×1.2 to keep the effective sample count in bounds); ancillary controllers: LQR/LQI/energy swing-up (pendulum), go-slow/go-fast/braking/go-to-goal (vessels), braking only on a Jackal at ~2 m/s with a thrown box. | **C1's `prim` is an instance of this idea** (fixed evasive primitives injected as extra samples) and its adaptive temperature is related. Claim to make: C1 uses *pedestrian-evasion* primitives (16 directions × 3 turn modes, full horizon or first 1.2 s) for a slow legged robot; it is **not** a new sampling scheme. Cite Biased-MPPI explicitly. |
| **Malone, Chiang, Lesser, Oishi, Tapia**, T-RO 33(5):1124–1138, 2017, doi 10.1109/TRO.2017.2705034 | abstract only (OpenAlex); full text closed, UNM PDF server unreachable | A small number of stochastic reachable (SR) sets for *hybrid* moving obstacles (dynamics can switch without warning) are computed a priori and turned into artificial potential fields for online planning; up to 900 obstacles; beats Gaussian APF by up to 60 % (holonomic) / 20 % (unicycle). | First author is **Malone** (LIT listed Chiang first). Closest in spirit to a "probabilistic evasion field", but APF, not MPPI; body shape / slow-robot regime / walls not stated in the abstract. Cite at abstract level only. |
| **Gonon, Paez-Granados, Billard**, RA-L 6(3):4728–4735, 2021, doi 10.1109/LRA.2021.3068660 | abstract only (OpenAlex); PDF blocked (HTTP 405/418/429) | Reactive collision avoidance for non-holonomic robots of convex (capsule) shape among moving obstacles; corrects the steering of a planner/driver; crowd simulator replaying real crowds; standing wheelchair Qolo with on-board LiDAR/RGB-D tracking, up to 5 pedestrians. | Reactive (one-step) velocity correction, not a sampling MPC; supports "body shape is not new". Details about VO-per-closest-subpart come from a search summary only — do not state them. |
| **MPPIPS-HWP** (Long, Bardaro, Matteucci; IEEE ROBIO 2025, pp. 1030–1037, doi 10.1109/ROBIO66223.2025.11376335) | abstract/metadata only (no open full text) | MPPI on per-step cost maps built from STGN-S learned trajectory predictions, plus a hybrid warning policy (warning from predicted-path risk and nearest-pedestrian distance). | Learned multi-step prediction + warnings; C1 uses CV prediction and no warning. Cite as "MPPI with learned pedestrian prediction". |
| **PGIF-MPPI** (re-check) | full text (arXiv HTML v2) | Single author (C. Mundane); to appear in Springer Proceedings in Advanced Robotics (HFR 2026). σ∥ = 1.2 + 0.5 s ahead, 0.5 behind, σ⊥ = 0.6 m; summed over pedestrians and horizon, no discount; pedestrian states from the simulator (ground truth); unicycle 2.0 m/s; baseline vanilla MPPI with static pedestrians; Hard level 41 % success, 0 % collision, 59 % timeout. No hard penalty, no guarantee. | Matches the earlier notes; author list corrected. |
| **DRA-MPPI** (re-check) | full text (arXiv HTML v2) | K = 400 rollouts; joint collision probability by Monte Carlo with 20 000 points; cost ω_soft·P + ω_hard·1[P > 0.05]; CV + Gaussian (Σ_w = 0.3² I) or a Markov mode switch (p = 0.025/step) giving 4 modes; Jackal, reference 2 m/s, 6 m corridor, 4/8/12 social-force pedestrians that react; 98–100 % success vs 43–86 % for vanilla MPPI. Published IROS 2025 pp. 313–320, doi 10.1109/IROS60139.2025.11246822. | Matches our re-implementation description (we compute P analytically, single Gaussian, two discs). |
| **CN-CBF** (re-check) | full text (arXiv HTML v2) | Relative state (x, y, θ_rel, v_o); pedestrian unicycle with ω_o ∈ [−0.35, 0.35] rad/s; robot v_r ∈ [0.25, 1.0] m/s; softmin (β = 4) over pedestrians; CBF-QP at 250 Hz on an MPC nominal controller; Gazebo + HuNavSim, agents do not avoid the robot, 5/10/15 people × 100 scenarios; "up to 18 %" over the strongest baseline; real delivery robot. Static obstacles not stated. | The specific numbers ~95/92/82 % in our earlier notes come from figures we could not read in text — **do not print them**; use "up to 18 % higher success than the strongest baseline". |
| **Contingency-MPPI** venue | PMLR page (search) | L4DC 2025, PMLR 283:869–880. | Venue confirmed. |
| **Homicidal-chauffeur threshold** l/R ≤ √(1−γ²) + γ·arcsin γ − 1 | **VERIFIED 25/11 (coordinator, user-authorised download)** | Full text of Bopardikar, Bullo & Hespanha, CDC 2007, doi 10.1109/CDC.2007.4434251, Eq. (2): with capture radius c = 1 and pursuer min. turning radius ρ, an evasion policy exists if γ ≥ γ_min(ρ), where 1/ρ = √(1−γ_min²) + γ_min·arcsin γ_min − 1 (restating Isaacs [1965] via Başar & Olsder). Same function as ours with l/R = c/ρ. The author PDF downloaded normally over TLS (no bypass needed this time). Isaacs/Pachter–Coates themselves still not read. | Now in the manuscript (Related Work), cited to Bopardikar et al. Eq. (2), phrased as a sufficient condition for evasion; numbers: l/R exceeds the bound 3.0–6.4× (v_e 0.3, v_p 0.9–1.3, ω 0.35, l 0.43–0.64). |
| Anisotropic quadruped velocity (Zhang et al., IROS 2024, doi 10.1109/IROS58592.2024.10803105) | metadata | — | unchanged |

Net corrections: (1) PGIF-MPPI has one author; (2) the T-RO 2017 SR-set paper's first author is Malone; (3) C2U-MPPI's chance constraint is anisotropic (full Σ_c), not isotropic; (4) Biased-MPPI already injects controller-generated samples, so `prim` must be presented as an application of that idea; (5) CN-CBF success percentages must not be quoted from our notes; (6) the homicidal-chauffeur threshold stays unverified.
