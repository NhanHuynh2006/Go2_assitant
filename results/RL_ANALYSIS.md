# So lieu RL (4096 tinh huong / lan danh gia) - de Claude danh gia

- ppo s0 thuc te : tant/rl_nav/runs/ppo_r_s0/best.npz  93.8% [93.1-94.5]     1.3%      4.8%     0.1%    8.0
- ppo s0 hoan hao: tant/rl_nav/runs/ppo_r_s0/best.npz  94.4% [93.7-95.1]     1.1%      4.4%     0.1%    8.1
- ppo s1 thuc te : tant/rl_nav/runs/ppo_r_s1/best.npz  93.7% [92.9-94.4]     1.2%      5.0%     0.1%    8.0
- ppo s1 hoan hao: tant/rl_nav/runs/ppo_r_s1/best.npz  94.3% [93.6-95.0]     1.2%      4.4%     0.1%    8.0
- ppo s2 thuc te : tant/rl_nav/runs/ppo_r_s2/best.npz  93.5% [92.7-94.2]     1.4%      4.9%     0.2%    8.0
- ppo s2 hoan hao: tant/rl_nav/runs/ppo_r_s2/best.npz  93.5% [92.7-94.2]     1.4%      4.9%     0.2%    8.0
- td3 s0 thuc te : tant/rl_nav/runs/td3_r_s0/best.npz  92.3% [91.4-93.1]     3.8%      3.9%     0.1%    8.2
- td3 s0 hoan hao: tant/rl_nav/runs/td3_r_s0/best.npz  92.3% [91.4-93.1]     4.0%      3.5%     0.2%    8.3
- td3 s1 thuc te : tant/rl_nav/runs/td3_r_s1/best.npz  91.6% [90.7-92.4]     3.0%      4.9%     0.6%    8.8
- td3 s1 hoan hao: tant/rl_nav/runs/td3_r_s1/best.npz  92.3% [91.5-93.1]     3.0%      4.1%     0.6%    8.9
- td3 s2 thuc te : tant/rl_nav/runs/td3_r_s2/best.npz  92.3% [91.5-93.1]     3.8%      3.9%     0.0%    8.1
- td3 s2 hoan hao: tant/rl_nav/runs/td3_r_s2/best.npz  92.6% [91.7-93.3]     3.9%      3.6%     0.0%    8.2
- sac s0 thuc te : tant/rl_nav/runs/sac_r_s0/best.npz  92.1% [91.3-92.9]     2.9%      5.0%     0.1%    8.7
- sac s0 hoan hao: tant/rl_nav/runs/sac_r_s0/best.npz  92.8% [92.0-93.6]     2.8%      4.4%     0.0%    8.8
- sac s1 thuc te : tant/rl_nav/runs/sac_r_s1/best.npz  91.7% [90.8-92.5]     2.7%      5.4%     0.3%    8.9
- sac s1 hoan hao: tant/rl_nav/runs/sac_r_s1/best.npz  92.2% [91.4-93.0]     2.7%      5.1%     0.1%    8.9
- sac s2 thuc te : tant/rl_nav/runs/sac_r_s2/best.npz  91.2% [90.3-92.0]     3.3%      5.4%     0.1%    9.0
- sac s2 hoan hao: tant/rl_nav/runs/sac_r_s2/best.npz  91.6% [90.7-92.4]     3.4%      5.0%     0.1%    9.0

## Bu tru giua seed tot nhat moi thuat toan (ghep cap, cam bien thuc te)
```
policy    toi dich  va vat  va nguoi   (cam bien thuc te, 4096 tinh huong ghep cap)
ppo          93.2%    0.9%      5.9%
td3          91.9%    3.5%      4.4%
sac          92.2%    2.5%      5.2%

A hong ma B lam duoc (% tinh huong), McNemar p:
  ppo    hong, td3    duoc:  2.47%   (p = 0.00109)
  ppo    hong, sac    duoc:  1.78%   (p = 0.00269)
  td3    hong, ppo    duoc:  3.76%   (p = 0.00109)
  td3    hong, sac    duoc:  3.30%   (p = 0.534)
  sac    hong, ppo    duoc:  2.81%   (p = 0.00269)
  sac    hong, td3    duoc:  3.03%   (p = 0.534)

ORACLE (moi tinh huong chon dung policy):
  ppo+td3             95.7%   (+2.5 diem so voi ppo)
  ppo+sac             95.0%   (+1.8 diem so voi ppo)
  td3+sac             95.2%   (+2.0 diem so voi ppo)
  ppo+td3+sac         96.4%   (+3.2 diem so voi ppo)

KET LUAN: tot nhat ppo 93.2%; tran tren khi tron tat ca 96.4% (+3.2). -> THU GHEP THAM LAM TRONG PRISM (Gazebo)
```

Log train: rl_nav/runs/<algo>_r_s<seed>/log.csv
