#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
go2_health_monitor.py — THEO DOI SUC KHOE Go2, CHI DOC, KHONG RA LENH.

Muc dich: bat tan tay khoanh khac robot "bun run rot xuong + den do".
Chay cai nay o 1 terminal RIENG trong luc demo. Khi robot sap, no in ra
snapshot 10 giay TRUOC do -> biet chinh xac motor nao qua nhiet / pin tut /
error_code doi truoc khi rot.

CHAY:
    python3 go2_health_monitor.py                 # in ra man hinh
    python3 go2_health_monitor.py --log health.csv # ghi them ra CSV

Doc:
    rt/lowstate       -> pin, nhiet 12 motor, torque, foot_force, IMU
    rt/sportmodestate -> mode, error_code, body_height

Nguong canh bao (theo kinh nghiem Go2):
    motor >= 70C : bat dau nong, motor hong thuong nong nhat
    motor >= 80C : nguy hiem, sap bi cat momen bao ve
    SOC  <= 20%  : robot tu vao che do bao ve, den do
"""

import sys
import time
import argparse
from collections import deque
from importlib import import_module

# ---- va cyclonedds 0.10.2 khong resolve duoc annotation dang chuoi cua
# ---- unitree_sdk2py (bug 'types.uint8 cannot be resolved'). Va lai truoc khi import idl.
import cyclonedds.idl._type_normalize as _tn

_orig_strip = _tn._strip_unextended_type


def _patched_strip(module, _type):
    if type(_type) == str:
        try:
            pymodule = import_module(module)
            ns = dict(vars(pymodule))
            import cyclonedds.idl.types as _t
            import unitree_sdk2py
            ns.setdefault("types", _t)
            ns.setdefault("unitree_sdk2py", unitree_sdk2py)
            return _patched_strip(module, eval(_type, ns))
        except Exception:
            pass
    return _orig_strip(module, _type)


_tn._strip_unextended_type = _patched_strip

import unitree_sdk2py.idl.unitree_go.msg.dds_ as D  # noqa: E402
from unitree_sdk2py.core.channel import (  # noqa: E402
    ChannelSubscriber, ChannelFactoryInitialize)

JOINTS = ["FR_hip", "FR_thigh", "FR_calf",
          "FL_hip", "FL_thigh", "FL_calf",
          "RR_hip", "RR_thigh", "RR_calf",
          "RL_hip", "RL_thigh", "RL_calf"]

TEMP_WARN = 70
TEMP_CRIT = 80
SOC_WARN = 20

# body_height thap hon nguong nay = robot dang nam / da rot xuong
H_DOWN = 0.15


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default="eth0")
    ap.add_argument("--hz", type=float, default=2.0, help="tan so in ra")
    ap.add_argument("--log", default=None, help="ghi CSV ra file")
    args = ap.parse_args()

    ChannelFactoryInitialize(0, args.iface)
    st = {}
    ChannelSubscriber("rt/lowstate", D.LowState_).Init(
        lambda m: st.__setitem__("low", m), 10)
    ChannelSubscriber("rt/sportmodestate", D.SportModeState_).Init(
        lambda m: st.__setitem__("sport", m), 10)

    print("Cho du lieu tu robot ...")
    t0 = time.time()
    while "low" not in st and time.time() - t0 < 10:
        time.sleep(0.2)
    if "low" not in st:
        print("!!! Khong nhan duoc rt/lowstate. Kiem tra iface (--iface eth0) "
              "va day mang noi bo robot.")
        return 1

    csv = None
    if args.log:
        csv = open(args.log, "w", encoding="utf-8")
        csv.write("t,soc,current_mA,power_v,mode,error_code,body_height," +
                  ",".join(f"T_{j}" for j in JOINTS) + "," +
                  ",".join(f"tau_{j}" for j in JOINTS) + "\n")

    # dem lui 10 giay gan nhat de in ra khi phat hien su co
    hist = deque(maxlen=int(10 * args.hz))
    was_up = False
    t_start = time.time()
    period = 1.0 / args.hz

    print(f"{'t':>6} {'SOC':>4} {'A':>6} {'mode':>4} {'err':>5} {'h':>6} "
          f"{'Tmax':>12} {'canh bao'}")
    try:
        while True:
            time.sleep(period)
            m = st.get("low")
            sp = st.get("sport")
            if m is None:
                print("... mat rt/lowstate")
                continue

            t = time.time() - t_start
            temps = [m.motor_state[i].temperature for i in range(12)]
            taus = [m.motor_state[i].tau_est for i in range(12)]
            hottest = max(range(12), key=lambda i: temps[i])
            soc = m.bms_state.soc
            cur = m.bms_state.current / 1000.0
            mode = sp.mode if sp else -1
            err = sp.error_code if sp else -1
            h = sp.body_height if sp else -1.0

            warns = []
            if temps[hottest] >= TEMP_CRIT:
                warns.append(f"NHIET NGUY HIEM {JOINTS[hottest]}={temps[hottest]}C")
            elif temps[hottest] >= TEMP_WARN:
                warns.append(f"nong {JOINTS[hottest]}={temps[hottest]}C")
            if soc <= SOC_WARN:
                warns.append(f"PIN THAP {soc}%")
            lost = [JOINTS[i] for i in range(12) if m.motor_state[i].lost > 0]
            if lost:
                warns.append("MAT GOI TIN: " + ",".join(lost))

            line = (f"{t:6.1f} {soc:4d} {cur:6.2f} {mode:4d} {err:5d} {h:6.3f} "
                    f"{JOINTS[hottest]:>8}={temps[hottest]:<3d} "
                    f"{'; '.join(warns)}")
            print(line)
            hist.append(line)

            if csv:
                csv.write(f"{t:.2f},{soc},{m.bms_state.current},{m.power_v:.2f},"
                          f"{mode},{err},{h:.3f}," +
                          ",".join(str(x) for x in temps) + "," +
                          ",".join(f"{x:.2f}" for x in taus) + "\n")
                csv.flush()

            # ---- phat hien khoanh khac ROT XUONG: dang dung -> tut xuong nam ----
            if h > H_DOWN:
                was_up = True
            elif was_up and 0 <= h <= H_DOWN:
                was_up = False
                print("\n" + "=" * 78)
                print(">>> ROBOT VUA RO'T XUONG (body_height %.3f). 10 giay truoc do:" % h)
                print("=" * 78)
                for old in hist:
                    print("   " + old)
                print("=" * 78)
                print("   nhiet 12 khop luc nay:")
                for i in range(12):
                    flag = "  <== NONG" if temps[i] >= TEMP_WARN else ""
                    print(f"     {JOINTS[i]:<10}{temps[i]:4d}C  tau={taus[i]:7.2f}{flag}")
                print(f"   pin={soc}%  dong={cur:.2f}A  error_code={err}  mode={mode}")
                print("=" * 78 + "\n")
    except KeyboardInterrupt:
        print("\nDung theo doi.")
    finally:
        if csv:
            csv.close()
            print(f"Da ghi log: {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
