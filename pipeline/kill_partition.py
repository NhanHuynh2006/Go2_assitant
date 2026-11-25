#!/usr/bin/env python3
"""Tat MOI tien trinh cua 1 sim song song (nhan biet qua bien moi truong GZ_PARTITION=<ten>),
khong dung toi sim khac. python3 kill_partition.py gvw1"""
import os
import signal
import sys

part = sys.argv[1].encode()
me = os.getpid()
n = 0
for pid in os.listdir("/proc"):
    if not pid.isdigit() or int(pid) == me:
        continue
    try:
        env = open(f"/proc/{pid}/environ", "rb").read().split(b"\0")
    except Exception:                                          # noqa: BLE001
        continue
    if b"GZ_PARTITION=" + part in env:
        try:
            os.kill(int(pid), signal.SIGKILL)
            n += 1
        except Exception:                                      # noqa: BLE001
            pass
print(f"da tat {n} tien trinh cua {sys.argv[1]}")
