#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
async_executor.py — BO THUC THI BAT DONG BO (ky thuat async cua SmolVLA).

Van de: neu robot lam xong 1 lenh moi nghe lenh ke (tuan tu), thi luc dang
di/nhay no "diec" — bo lo lenh moi, va chuoi lenh dai bi cong don tre.

Giai phap (SmolVLA, arxiv 2506.01844): TACH RIENG "sinh/nghe" khoi "thuc thi".
Hanh dong chay trong 1 THREAD RIENG qua hang doi (queue). Vong chinh van
tiep tuc nghe + STT + nghi cau ke trong khi robot dang lam -> giam ~30%
tong thoi gian hoan thanh chuoi lenh, va EMERGENCY co the chen vao bat ky luc nao.

Co che:
  - enqueue(actions): day chuoi hanh dong vao hang doi
  - emergency_stop(): xoa sach hang doi + dung robot NGAY (uu tien tuyet doi)
  - worker thread: lay tung action -> guard.check -> robot.execute
"""

import threading
import queue
import time


class AsyncExecutor:
    def __init__(self, robot, guard, on_event=None):
        """
        robot   : RobotTools (co .execute(action) va .stop())
        guard   : SafetyGuard (kiem duyet truoc khi chay)
        on_event: callback(str) de in log (tuy chon)
        """
        self.robot = robot
        self.guard = guard
        self.on_event = on_event or (lambda s: None)
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self._running = True
        self._busy = False
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.worker.start()

    # ---------- API cong khai ----------
    def enqueue(self, actions):
        """Day 1 chuoi action vao hang doi (khong chan vong chinh)."""
        if actions:
            self.robot.abort.clear()      # lenh moi cua nguoi dung -> bo trang thai huy
        for a in actions or []:
            self.q.put(a)

    def emergency_stop(self):
        """Uu tien tuyet doi: huy lenh DANG CHAY + xoa hang doi + dung robot ngay.

        Thu tu quan trong:
          1) bat co abort TRUOC -> vong move() dang gui van toc tu thoat trong ~0.1s
             (truoc day chi StopMove 1 lan roi bi vong move de len -> robot di het lenh)
          2) StopMove gui tu LUONG RIENG -> khong xep hang sau loi goi dang ket
             (vd Dance1 chan toi khi nhay xong)
        """
        with self.lock:
            self.robot.abort.set()
            # vet sach hang doi (KHONG goi task_done — tranh dem 2 lan voi worker)
            try:
                while True:
                    self.q.get_nowait()
            except queue.Empty:
                pass
            self.guard.trigger_emergency()
            threading.Thread(target=self._force_stop, daemon=True).start()
            self.on_event("\U0001F6D1 EMERGENCY STOP — da xoa hang doi va dung robot")
            if self._busy:
                self.on_event("   ⏳ neu dang NHAY (dong tac dong goi) robot se ket thuc"
                              " dong tac roi moi dung han — firmware khong cho cat giua chung")
            # cho phep lenh moi sau khi da dung
            self.guard.clear_emergency()

    def _force_stop(self):
        try:
            self.robot.stop()
        except Exception:
            pass

    def is_busy(self):
        return self._busy or not self.q.empty()

    def shutdown(self):
        self._running = False

    # ---------- worker thread ----------
    def _loop(self):
        while self._running:
            try:
                act = self.q.get(timeout=0.1)
            except queue.Empty:
                self._busy = False
                continue
            self._busy = True
            try:
                safe, note = self.guard.check(act)
                if safe is None:
                    self.on_event(f"   \u26d4 {note}")
                    self.q.task_done()
                    continue
                # neu can dung truoc khi di -> chen stand-up
                if note == "STAND_FIRST":
                    self.on_event("   \u2197\ufe0f  robot chua dung — tu dung day truoc")
                    self.robot.execute({"tool": "action", "args": {"name": "standup"}})
                    self.guard.mark_standing(True)
                    time.sleep(0.5)
                res = self.robot.execute(safe)
                self.on_event(f"   \u2705 {res}")
            except Exception as e:
                self.on_event(f"   \u26a0\ufe0f loi thuc thi: {e}")
            finally:
                try:
                    self.q.task_done()
                except ValueError:
                    pass


if __name__ == "__main__":
    # Test bang robot gia (dry-run in ra man hinh)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from robot_tools import RobotTools
    from safety_guard import SafetyGuard

    robot = RobotTools(dry_run=True)
    guard = SafetyGuard()
    ex = AsyncExecutor(robot, guard, on_event=print)

    print(">>> day 3 lenh (robot se tu dung day truoc khi di):")
    ex.enqueue([
        {"tool": "move", "args": {"vx": 0.35, "duration": 2.0}},
        {"tool": "action", "args": {"name": "hello"}},
        {"tool": "action", "args": {"name": "handstand"}},   # se bi guard chan
    ])
    time.sleep(1.0)
    print(">>> trong luc dang lam, kich hoat EMERGENCY:")
    ex.emergency_stop()
    time.sleep(0.5)
    print(">>> xong.")
