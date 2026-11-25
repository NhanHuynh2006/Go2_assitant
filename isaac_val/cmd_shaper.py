"""Bo nan lenh (de xuat tag opt-in `~cs`, CHUA co trong robot_ros): dat SAU bo dieu khien, TRUOC _twist.
Ly do (Isaac 24/11): moi lan nga cua policy rough deu co |vy| ~0.26-0.30 CUNG LUC |wz| 0.75-0.99 trong 2 s cuoi, thuong kem lui.
  1) khi di ngang (|vy| > VY_ON) hoac lui (vx < VX_BACK): |wz| <= WZ_CAP
  2) gioi han toc do doi lenh: |dvy| <= DVY * dt, |dwz| <= DWZ * dt (lenh 10 Hz -> 0.15 / 0.25 moi chu ky)
Khong dung nav_local/robot_ros; hook can co: robot_ros goi shaper(u, now) ngay truoc self._twist(...)."""
import math

VY_ON, VX_BACK, WZ_CAP = 0.15, -0.05, 0.6
DVY, DWZ = 1.5, 2.5          # /s


class CmdShaper:
    def __init__(self, vy_on=VY_ON, vx_back=VX_BACK, wz_cap=WZ_CAP, dvy=DVY, dwz=DWZ):
        self.p = (vy_on, vx_back, wz_cap, dvy, dwz)
        self.last, self.t = (0.0, 0.0, 0.0), None
        self.n_cap = self.n_rate = self.n = 0

    def __call__(self, vx, vy, wz, now):
        vy_on, vx_back, wz_cap, dvy, dwz = self.p
        self.n += 1
        if abs(vy) > vy_on or vx < vx_back:
            if abs(wz) > wz_cap:
                self.n_cap += 1
            wz = max(-wz_cap, min(wz_cap, wz))
        if self.t is not None:
            dt = max(1e-3, min(0.3, now - self.t))
            lvx, lvy, lwz = self.last
            vy2 = lvy + max(-dvy * dt, min(dvy * dt, vy - lvy))
            wz2 = lwz + max(-dwz * dt, min(dwz * dt, wz - lwz))
            if abs(vy2 - vy) > 1e-9 or abs(wz2 - wz) > 1e-9:
                self.n_rate += 1
            vy, wz = vy2, wz2
        if vx == 0.0 and vy == 0.0 and wz == 0.0:          # lenh dung (phanh) di qua nguyen ven
            pass
        self.last, self.t = (vx, vy, wz), now
        return vx, vy, wz


def install(robot, clock):
    """boc robot._twist (dung trong isaac_val de thu; KHONG phai ban trien khai)."""
    sh = CmdShaper()
    orig = robot._twist

    def tw(vx=0.0, vy=0.0, wz=0.0):
        if vx == 0.0 and vy == 0.0 and wz == 0.0:
            sh.last, sh.t = (0.0, 0.0, 0.0), clock.t
            return orig(0.0, 0.0, 0.0)
        return orig(*sh(float(vx), float(vy), float(wz), clock.t))
    robot._twist = tw
    robot._shaper = sh
    return sh
