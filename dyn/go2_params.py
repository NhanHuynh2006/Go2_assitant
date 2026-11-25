# -*- coding: utf-8 -*-
"""Doc go2_params.yaml va lay mau mot bo dong hoc Go2 (cho train / fastsim regime "go2").
   s = sample(rng)      # dict: gain(3) back vsat tau(3) delay acc(3) xoff deadband wob(3) odom_scale
   apply_to_sim(sim, s) # gan vao fastsim.Sim dang co (gain, vsat, back, wob, tau, delay)"""
import os
import numpy as np
import yaml
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "go2_params.yaml")


def load():
    with open(PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def sample(rng, D=None):
    D = D or load()
    R, u = D["domain_randomization"], lambda a: float(rng.uniform(*a))
    k = u(R["wob_scale"])
    return dict(gain=np.array([u(R["gain"][a]) for a in "xyw"]), back=u(R["back"]), vsat=u(R["vsat"]),
                tau=np.array([u(R["tau"][a]) for a in "xyw"]), delay=u(R["delay"]), acc=np.array([u(R["acc"][a]) for a in "xyw"]),
                xoff=u(R["xoff"]), deadband=u(R["deadband_x"]), wob=k * np.array(D["body_wobble"]["fastsim_wob"]["v"]),
                odom_scale=u(R["odom_scale_error"]), odom_yaw_scale=u(R["odom_yaw_scale"]), lidar_delay=u(R["lidar_delay"]),
                lidar_stamp_jitter=R["lidar_stamp_jitter"])


def apply_to_sim(sim, s):
    for k in ("gain", "back", "vsat", "wob", "tau", "delay"):
        setattr(sim, k, s[k])
    # acc, xoff, deadband, odom_scale, lidar_delay: fastsim.substep chua co cho gan -> xem REPORT_DYN
