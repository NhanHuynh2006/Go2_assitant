"""Ghep truc (tu sysid.npz): van toc than trung binh 0.8 s cuoi moi doan lenh hang, theo to hop lenh."""
import numpy as np
z=np.load("results/sysid.npz"); L=z["log"]; seg=z["seg"].reshape(-1,2)
bad=np.zeros(len(L),bool)
for a,b in seg: bad[a-5:b+5]=True
u=L[:,5:8]; st=np.flatnonzero(np.any(np.abs(np.diff(u,axis=0))>1e-9,axis=1))+1
R=[]
for a,b in zip(st[:-1],st[1:]):
    if bad[a:b].any() or L[b-1,1]-L[a,1]<1.0: continue
    t=L[a:b,1]; m=t>t[-1]-0.8
    q=L[a:b][m]
    if len(q)<15: continue
    T=q[-1,1]-q[0,1]
    yaw=np.unwrap(q[:,4]); dy=(yaw[-1]-yaw[0])/T
    vx=np.gradient(q[:,2],q[:,1]); vy=np.gradient(q[:,3],q[:,1])
    bx=(np.cos(yaw)*vx+np.sin(yaw)*vy).mean(); by=(-np.sin(yaw)*vx+np.cos(yaw)*vy).mean()
    R.append((*u[a],bx,by,dy))
R=np.array(R); print(len(R))
ux,uy,wz,bx,by,dy=R.T
def s(n,m): 
    print(f"{n:38s} n={m.sum():3d} bx={bx[m].mean():+.3f}±{bx[m].std():.3f} |by|={np.abs(by[m]).mean():.3f} dy={np.abs(dy[m]).mean():.3f} ux={ux[m].mean():+.2f} uy={np.abs(uy[m]).mean():.2f} |v|={np.hypot(bx,by)[m].mean():.3f}") if m.sum() else print(n,0)
s("tien >0.3, uy=wz=0",(ux>.3)&(uy==0)&(wz==0))
s("tien >0.3, |uy|>0.15,|wz|<.3",(ux>.3)&(abs(uy)>.15)&(abs(wz)<.3))
s("tien >0.3, |uy|>0.15,|wz|>.5",(ux>.3)&(abs(uy)>.15)&(abs(wz)>.5))
s("tien >0.3, |wz|>.5",(ux>.3)&(abs(wz)>.5))
s("ngang >.15, ux=0",(ux==0)&(abs(uy)>.15))
s("ngang >.15, |ux|<.1 all",(abs(ux)<.1)&(abs(uy)>.15))
s("ngang>.2 & |wz|>.5",(abs(uy)>.2)&(abs(wz)>.5))
s("lui <-.1",(ux<-.1)&(uy==0)); s("lui <-.1 all",(ux<-.1))
s("wz only",(ux==0)&(uy==0)&(abs(wz)>.5))
sg=np.abs(uy)>.1
print("gain vy theo |wz|:",[(round((by[sg&m]/uy[sg&m]).mean(),2),int((sg&m).sum())) for m in (abs(wz)<.2,(abs(wz)>=.2)&(abs(wz)<.6),abs(wz)>=.6)])
fw=ux>.25
print("vx theo |uy| khi ux>.25:",[(round(bx[fw&m].mean(),3),int((fw&m).sum())) for m in (abs(uy)<.1,(abs(uy)>=.1)&(abs(uy)<.2),abs(uy)>=.2)])
print("vx theo |wz| khi ux>.25:",[(round(bx[fw&m].mean(),3),int((fw&m).sum())) for m in (abs(wz)<.2,(abs(wz)>=.2)&(abs(wz)<.6),abs(wz)>=.6)])
A=np.c_[uy,wz,ux*wz,ux]; 
print("hoi quy by ~ uy wz ux*wz ux",np.linalg.lstsq(A,by,rcond=None)[0].round(3)); print("hoi quy dy ~ uy wz ux*wz ux",np.linalg.lstsq(A,dy,rcond=None)[0].round(3))
