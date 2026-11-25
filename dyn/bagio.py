#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bagio.py - doc rosbag2 sqlite (*.db3) CHI DOC, giai CDR bang tay, khong can ROS.
Ho tro: nav_msgs/Odometry, sensor_msgs/Imu, sensor_msgs/PointCloud2, geometry_msgs/Twist,
        std_msgs/String.  Kieu khac: tra ve bytes tho.
  python bagio.py FILE.db3            # liet ke topic / kieu / so ban tin / thoi luong
"""
import os
import sqlite3
import struct
import sys

import numpy as np


class Cdr:
    """Con tro doc CDR little-endian (RMW ghi 4 byte dau: 00 01 00 00); can le theo goc byte 4."""

    def __init__(self, b):
        self.b, self.i = b, 4
        if b[1] != 1:
            raise ValueError("chi ho tro CDR little-endian")

    def al(self, n):
        self.i += (-(self.i - 4)) % n

    def get(self, fmt, n):
        self.al(n)
        v = struct.unpack_from("<" + fmt, self.b, self.i)
        self.i += struct.calcsize("<" + fmt)
        return v

    def u32(self):
        return self.get("I", 4)[0]

    def f64(self, k):
        return self.get("%dd" % k, 8)

    def s(self):
        n = self.u32()
        v = self.b[self.i:self.i + n]
        self.i += n
        return v[:-1].decode("utf8", "replace") if n else ""

    def header(self):
        sec, ns = self.get("iI", 4)
        return sec + ns * 1e-9, self.s()


def odom(b):
    """-> (stamp, frame, child, pos3, quat xyzw, v3, w3)  (v, w theo header chu khong sua he truc)"""
    c = Cdr(b)
    st, fr = c.header()
    ch = c.s()
    p = c.f64(7)
    c.f64(36)
    t = c.f64(6)
    return st, fr, ch, p[:3], p[3:], t[:3], t[3:]


def imu(b):
    c = Cdr(b)
    st, fr = c.header()
    q = c.f64(4)
    c.f64(9)
    w = c.f64(3)
    c.f64(9)
    return st, fr, q, w, c.f64(3)


def twist(b):
    return Cdr(b).f64(6)


DT = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


def cloud(b):
    """-> (stamp, frame, mang co cau truc)"""
    c = Cdr(b)
    st, fr = c.header()
    h, w = c.get("II", 4)
    n = c.u32()
    names, off, fm = [], [], []
    for _ in range(n):
        nm = c.s()
        o = c.u32()
        dt = c.get("B", 1)[0]
        cnt = c.u32()
        names.append(nm)
        off.append(o)
        fm.append(("<" + DT[dt]) if cnt == 1 else ("<" + DT[dt], (cnt,)))
    c.get("B", 1)
    ps, rs = c.get("II", 4)
    n = c.u32()
    a = np.frombuffer(b, np.dtype(dict(names=names, offsets=off, formats=fm, itemsize=ps)),
                      count=min(h * w, n // ps), offset=c.i)
    return st, fr, a


PARSE = {"nav_msgs/msg/Odometry": odom, "sensor_msgs/msg/Imu": imu, "geometry_msgs/msg/Twist": twist,
         "sensor_msgs/msg/PointCloud2": cloud, "std_msgs/msg/String": lambda b: Cdr(b).s()}


def connect(path):
    # immutable: khong tao -shm/-wal, khong dung toi ban ghi goc
    return sqlite3.connect("file:%s?mode=ro&immutable=1" % os.path.abspath(os.path.expanduser(path)), uri=True)


def read(path, topic):
    """Sinh (t_bag giay, ban tin da giai) theo thu tu thoi gian."""
    c = connect(path)
    tid, ty = c.execute("select id,type from topics where name=?", (topic,)).fetchone()
    f = PARSE.get(ty, bytes)
    for t, d in c.execute("select timestamp,data from messages where topic_id=? order by timestamp", (tid,)):
        yield t * 1e-9, f(d)


def listing(path):
    c = connect(path)
    return c.execute("select t.name,t.type,count(m.id),min(m.timestamp)/1e9,(max(m.timestamp)-min(m.timestamp))/1e9 "
                     "from topics t left join messages m on m.topic_id=t.id group by t.id").fetchall()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        try:
            for nm, ty, n, t0, d in listing(p):
                print("  %-22s %-30s %6d  %.1f s  %.1f Hz" % (nm, ty, n, d or 0, n / d if d else 0))
        except sqlite3.DatabaseError as e:
            print("  HONG:", e)
