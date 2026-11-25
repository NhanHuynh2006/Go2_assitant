"""Kiem DP: mo phong MC voi dung mo hinh (nhay truoc, hanh dong chon truoc) va chinh sach tham lam theo bang -> so V."""
import sys; sys.path.insert(0,"/home/nhanhuynh/Documents/Go2_assitant"); sys.path.insert(0,"/home/nhanhuynh/Documents/Go2_assitant/sev")
import numpy as np, nav_sev as S
from build import kern
K=kern("crowd"); 
# bang V tung buoc: giai lai n=1..10 -> luu
Vs=[None]*11; Vs[0]=None
for n in range(1,11): Vs[n]=S.solve(K,n=n)
A=S.actions(); rng=np.random.default_rng(0)
cum=np.cumsum(K,1)
def q_after(bx,by,psi_i,s,a):
    pass
def mc(p0,psi0,s0,M=4000):
    n=M; x=np.full(n,p0[0]); y=np.full(n,p0[1]); pi=np.full(n,int(round((psi0%(2*np.pi))/(2*np.pi/24)))%24); s=np.full(n,s0); hit=np.zeros(n,bool)
    psi=pi*2*np.pi/24
    for k in range(10):
        rem=10-k
        # chon a tham lam: ky vong theo K cua V_{rem-1}
        best=np.full(n,9.0); ba=np.zeros(n,int)
        for a in range(len(A)):
            vx,vy,wz=A[a]
            # E theo mau nhay: lay ky vong day du qua 96 trang thai (chi cho 400 hat moi lan)
            ex=0.0
            S_=np.arange(96); 
            ps=S_%24; ss=S_//24
            w=K[(s*24+pi)]                                  # (n,96) nhung pi = chi so roi rac
            PX=x[:,None]+0.3*S.SPEEDS[ss]*np.cos(ps*2*np.pi/24)[None]; PY=y[:,None]+0.3*S.SPEEDS[ss]*np.sin(ps*2*np.pi/24)[None]
            h=wz*.15; dx,dy=(vx*np.cos(h)-vy*np.sin(h))*.3,(vx*np.sin(h)+vy*np.cos(h))*.3
            ex_,ey_=PX-dx,PY-dy; c,sn=np.cos(wz*.3),np.sin(wz*.3); bx,by=c*ex_+sn*ey_,-sn*ex_+c*ey_
            cl=S.clearance(bx,by); val=(cl<0).astype(float)
            if rem>1:
                T=S.Table(Vs[rem-1]); v=T(bx,by,(ps*2*np.pi/24-wz*.3)[None]+0*bx,S.SPEEDS[ss][None]+0*bx); val=np.where(cl<0,1.0,v)
            e=(w*val).sum(1); m=e<best; best=np.where(m,e,best); ba=np.where(m,a,ba)
        # thuc hien: nhay truoc
        u=rng.random(n); st=(cum[s*24+pi]>u[:,None]).argmax(1); pi=st%24; s=st//24
        vx,vy,wz=A[ba].T
        for m in range(1,4):
            t=.1*m; h=.5*wz*t; dx,dy=(vx*np.cos(h)-vy*np.sin(h))*t,(vx*np.sin(h)+vy*np.cos(h))*t
            PX=x+t*S.SPEEDS[s]*np.cos(pi*2*np.pi/24)-dx; PY=y+t*S.SPEEDS[s]*np.sin(pi*2*np.pi/24)-dy
            c,sn=np.cos(wz*t),np.sin(wz*t); bx,by=c*PX+sn*PY,-sn*PX+c*PY; hit|=S.clearance(bx,by)<0
        x,y=bx,by; fp=((pi*2*np.pi/24-wz*.3)%(2*np.pi))/(2*np.pi/24); lo=np.floor(fp); pi=((lo+(rng.random(n)<fp-lo)).astype(int))%24
    return hit.mean()
for p,ps,s in (((1.0,0.),np.pi,2),((1.4,0.),np.pi,2),((0.,1.2),-np.pi/2,2),((1.2,.6),np.pi,2),((1.8,0.8),-2.6,2)):
    v=float(S.Table(Vs[10])(np.array(p[0]),np.array(p[1]),np.array(ps),np.array(S.SPEEDS[s])))
    print(p,"V",round(v,3),"MC",round(mc(p,ps,s,400),3))
