#!/usr/bin/env python3
"""Nhan dang dong hoc CHAMP trong Gazebo: gui lenh ngau nhien (giu 1.2-2 s), ghi lenh + odom 50 Hz.
   source ROS; GZ_PARTITION=gvw1 ROS_DOMAIN_ID=22 venv/bin/python pipeline/sysid.py out.npz 240"""
import math, random, subprocess, sys, threading, time
import numpy as np
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.qos import qos_profile_sensor_data as Q
out, dur = sys.argv[1], float(sys.argv[2])
rclpy.init()
n = rclpy.create_node("sysid")
pub = n.create_publisher(Twist, "/cmd_vel", 10)
log, cur = [], [0.0, 0.0, 0.0]


def cb(m):
    q = m.pose.pose.orientation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
    st = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
    log.append((time.monotonic(), st, m.pose.pose.position.x, m.pose.pose.position.y, yaw, *cur))


n.create_subscription(Odometry, "/gazebo/odom", cb, Q)
threading.Thread(target=rclpy.spin, args=(n,), daemon=True).start()


def send(u):
    cur[:] = u
    t = Twist()
    t.linear.x, t.linear.y, t.angular.z = map(float, u)
    pub.publish(t)


def home():
    send((0, 0, 0))
    subprocess.run(["gz", "service", "-s", "/world/voice_office/set_pose", "--reqtype", "gz.msgs.Pose", "--reptype",
                    "gz.msgs.Boolean", "--timeout", "3000", "--req",
                    'name: "go2", position: {x: 0, y: 0, z: 0.32}, orientation: {w: 1}'], capture_output=True)
    time.sleep(2.5)


time.sleep(2)
home()
rnd = random.Random(1)
t0 = time.monotonic()
seg = []
while time.monotonic() - t0 < dur:
    mode = rnd.choice(["vx", "vx", "vy", "wz", "all", "all", "stop"])
    u = [0.0, 0.0, 0.0]
    if mode in ("vx", "all"):
        u[0] = rnd.uniform(-.2, .6)
    if mode in ("vy", "all"):
        u[1] = rnd.uniform(-.3, .3)
    if mode in ("wz", "all"):
        u[2] = rnd.uniform(-1, 1)
    te = time.monotonic() + rnd.uniform(1.2, 2.2)
    while time.monotonic() < te:
        send(u)
        time.sleep(.05)
    if log and math.hypot(log[-1][2], log[-1][3]) > 1.6:
        seg.append(len(log))
        home()
        seg.append(len(log))
send((0, 0, 0))
np.savez(out, log=np.array(log), seg=np.array(seg))
print(len(log), "mau")
import os
os._exit(0)
