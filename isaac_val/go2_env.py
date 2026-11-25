"""Dung chung: tao moi truong Go2 Isaac Lab (phang) + nap actor chinh thuc (khong can rsl_rl).
Phai goi SAU khi AppLauncher da khoi dong."""
import os
import gymnasium as gym
import torch
import torch.nn as nn

CKPT = os.path.expanduser("~/isaac/ckpt/go2_%s.pt")


def make_env(policy="flat", num_envs=1, device="cpu", seed=0, mass=True, noise=False, spacing=3.0):
    from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.flat_env_cfg import UnitreeGo2FlatEnvCfg
    from isaaclab_tasks.manager_based.locomotion.velocity.config.go2.rough_env_cfg import UnitreeGo2RoughEnvCfg
    from isaaclab.envs import ManagerBasedRLEnv
    cfg = UnitreeGo2FlatEnvCfg() if policy == "flat" else UnitreeGo2RoughEnvCfg()
    if policy != "flat":                      # van san phang, giu height_scan (policy rough can)
        cfg.scene.terrain.terrain_type = "plane"
        cfg.scene.terrain.terrain_generator = None
        cfg.curriculum.terrain_levels = None
    cfg.seed = seed
    cfg.scene.num_envs, cfg.scene.env_spacing = num_envs, spacing
    cfg.sim.device = device
    cfg.observations.policy.enable_corruption = noise
    cfg.events.base_external_force_torque = None
    cfg.events.push_robot = None
    if not mass:
        cfg.events.add_base_mass = None
    cfg.episode_length_s = 1e6
    cfg.terminations.time_out = None
    c = cfg.commands.base_velocity            # lenh do minh dat, khong lay mau
    c.heading_command, c.rel_standing_envs, c.debug_vis = False, 0.0, False
    c.ranges.heading = None
    c.resampling_time_range = (1e9, 1e9)
    for n in list(cfg.rewards.__dict__):      # khong can thuong (bot tinh)
        if not n.startswith("_"):
            setattr(cfg.rewards, n, None)
    cfg.viewer.eye = (3., 3., 2.)
    return ManagerBasedRLEnv(cfg=cfg)


def load_actor(policy, device):
    sd = torch.load(CKPT % policy, map_location="cpu", weights_only=True)["model_state_dict"]
    ks = sorted({int(k.split(".")[1]) for k in sd if k.startswith("actor.")})
    layers = []
    for j, k in enumerate(ks):
        W = sd[f"actor.{k}.weight"]
        l = nn.Linear(W.shape[1], W.shape[0])
        l.weight.data, l.bias.data = W, sd[f"actor.{k}.bias"]
        layers.append(l)
        if j < len(ks) - 1:
            layers.append(nn.ELU())
    return nn.Sequential(*layers).to(device).eval()
