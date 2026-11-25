# KET QUA CHINH THUC — final_office_merged

960 luot; thuat toan de xuat: **prism@ppo+sac**

| cau hinh | n | thanh cong [KTC 95 %] | va cham | va do robot | thoi gian TB (s) | khung | lac huong | SPL |
|---|---|---|---|---|---|---|---|---|
| **prism@ppo+sac** | 40 | 70 % [55–82] | 18 % | 18 % | 56.1 | 1.1 | 23.9 | 0.61 |
| apmppi | 40 | 68 % [52–80] | 18 % | 12 % | 64.7 | 1.1 | 30.8 | 0.53 |
| apmppi_multi | 40 | 72 % [57–84] | 15 % | 8 % | 62.5 | 1.1 | 23.8 | 0.57 |
| bmppi | 40 | 50 % [35–65] | 32 % | 25 % | 62.4 | 0.9 | 22.6 | 0.45 |
| dwa | 40 | 68 % [52–80] | 28 % | 10 % | 61.0 | 0.5 | 15.4 | 0.66 |
| log_mppi | 40 | 68 % [52–80] | 15 % | 12 % | 80.4 | 1.4 | 25.4 | 0.53 |
| mppi | 40 | 65 % [50–78] | 22 % | 18 % | 84.0 | 2.4 | 27.7 | 0.48 |
| pgmppi | 40 | 62 % [47–76] | 28 % | 22 % | 63.3 | 1.0 | 21.6 | 0.56 |
| pp | 40 | 28 % [16–43] | 35 % | 10 % | 44.9 | 20.6 | 36.0 | 0.27 |
| prism | 40 | 70 % [55–82] | 20 % | 18 % | 58.7 | 1.6 | 24.6 | 0.56 |
| prism@ppo | 40 | 62 % [47–76] | 18 % | 15 % | 69.9 | 1.9 | 28.9 | 0.55 |
| prism@ppo+td3+sac | 40 | 68 % [52–80] | 28 % | 20 % | 66.4 | 1.6 | 24.6 | 0.61 |
| prism_noadapt@ppo+sac | 40 | 65 % [50–78] | 22 % | 20 % | 62.8 | 1.6 | 30.1 | 0.56 |
| prism_noadaptratio@ppo+sac | 40 | 78 % [62–88] | 18 % | 10 % | 62.0 | 1.1 | 21.8 | 0.65 |
| prism_noprior | 40 | 65 % [50–78] | 25 % | 22 % | 62.9 | 1.6 | 21.1 | 0.54 |
| prism_nounc@ppo+sac | 40 | 78 % [62–88] | 18 % | 12 % | 63.0 | 1.3 | 21.9 | 0.65 |
| prism_novalue@ppo+sac | 40 | 70 % [55–82] | 25 % | 18 % | 58.6 | 1.2 | 23.2 | 0.62 |
| prism_novis@ppo+sac | 40 | 82 % [68–91] | 15 % | 5 % | 64.9 | 1.2 | 22.5 | 0.67 |
| prism~t0@ppo+sac | 40 | 52 % [37–67] | 20 % | 8 % | 69.8 | 1.3 | 26.3 | 0.44 |
| rl | 40 | 52 % [37–67] | 38 % | 28 % | 53.0 | 1.0 | 26.8 | 0.52 |
| rl@sac | 40 | 30 % [18–45] | 32 % | 25 % | 56.0 | 1.2 | 44.1 | 0.24 |
| rl@td3 | 40 | 12 % [5–26] | 60 % | 52 % | 35.7 | 1.1 | 25.4 | 0.21 |
| rl_ens | 40 | 48 % [33–63] | 42 % | 38 % | 51.0 | 0.6 | 25.0 | 0.45 |
| rl_safe | 40 | 45 % [31–60] | 30 % | 20 % | 55.7 | 0.7 | 25.0 | 0.35 |

## So sanh ghep cap voi prism@ppo+sac (cung bai, cung lan)

| doi chung | ours thang / thua (thanh cong) | McNemar p | thoi gian ours vs doi chung (s) | Wilcoxon p |
|---|---|---|---|---|
| apmppi | 7 / 6 | 1 | 53.0 vs 55.3 | 0.181 |
| apmppi_multi | 3 / 4 | 1 | 55.3 vs 59.1 | 0.09 |
| bmppi | 13 / 5 | 0.0963 | 52.8 vs 55.4 | 0.132 |
| dwa | 4 / 3 | 1 | 55.6 vs 58.5 | 0.0366 |
| log_mppi | 6 / 5 | 1 | 57.3 vs 76.1 | 2.38e-06 |
| mppi | 8 / 6 | 0.791 | 53.5 vs 74.2 | 9.54e-06 |
| pgmppi | 7 / 4 | 0.549 | 54.6 vs 57.2 | 0.0701 |
| pp | 17 / 0 | 1.53e-05 | 41.9 vs 44.9 | 0.278 |
| prism | 4 / 4 | 1 | 53.7 vs 55.4 | 0.175 |
| prism@ppo | 9 / 6 | 0.607 | 50.1 vs 55.2 | 0.243 |
| prism@ppo+td3+sac | 6 / 5 | 1 | 56.1 vs 56.7 | 0.673 |
| prism_noadapt@ppo+sac | 6 / 4 | 0.754 | 56.2 vs 60.1 | 0.0853 |
| prism_noadaptratio@ppo+sac | 2 / 5 | 0.453 | 56.5 vs 56.0 | 0.675 |
| prism_noprior | 6 / 4 | 0.754 | 53.9 vs 61.6 | 0.00542 |
| prism_nounc@ppo+sac | 1 / 4 | 0.375 | 56.0 vs 57.2 | 0.374 |
| prism_novalue@ppo+sac | 3 / 3 | 1 | 54.5 vs 55.8 | 0.382 |
| prism_novis@ppo+sac | 2 / 7 | 0.18 | 55.7 vs 57.5 | 0.469 |
| prism~t0@ppo+sac | 13 / 6 | 0.167 | 50.8 vs 57.0 | 0.00897 |
| rl | 12 / 5 | 0.143 | 51.5 vs 47.0 | 0.0507 |
| rl@sac | 17 / 1 | 0.000145 | 47.6 vs 53.3 | 0.118 |
| rl@td3 | 24 / 1 | 1.55e-06 | 36.2 vs 25.6 | nan |
| rl_ens | 12 / 3 | 0.0352 | 53.8 vs 48.5 | 0.0386 |
| rl_safe | 11 / 1 | 0.00635 | 56.6 vs 53.6 | 0.193 |

## Theo loai bai

| cau hinh | clutter | crowd |
|---|---|---|
| prism@ppo+sac | 23/25 | 5/15 |
| apmppi | 21/25 | 6/15 |
| apmppi_multi | 23/25 | 6/15 |
| bmppi | 15/25 | 5/15 |
| dwa | 23/25 | 4/15 |
| log_mppi | 20/25 | 7/15 |
| mppi | 18/25 | 8/15 |
| pgmppi | 21/25 | 4/15 |
| pp | 11/25 | 0/15 |
| prism | 22/25 | 6/15 |
| prism@ppo | 20/25 | 5/15 |
| prism@ppo+td3+sac | 23/25 | 4/15 |
| prism_noadapt@ppo+sac | 22/25 | 4/15 |
| prism_noadaptratio@ppo+sac | 22/25 | 9/15 |
| prism_noprior | 20/25 | 6/15 |
| prism_nounc@ppo+sac | 25/25 | 6/15 |
| prism_novalue@ppo+sac | 23/25 | 5/15 |
| prism_novis@ppo+sac | 25/25 | 8/15 |
| prism~t0@ppo+sac | 15/25 | 6/15 |
| rl | 17/25 | 4/15 |
| rl@sac | 9/25 | 3/15 |
| rl@td3 | 4/25 | 1/15 |
| rl_ens | 15/25 | 4/15 |
| rl_safe | 14/25 | 4/15 |
