import sys,time; sys.path.insert(0,"/home/nhanhuynh/Documents/Go2_assitant")
import numpy as np, nav_sev as S
K=S.person_kernel([.3,.3,.3],np.radians([30,45,60,90]),.05,.3,np.radians([10,40,90]),0.3)
print(K.sum(1).min(),K.sum(1).max())
K0=np.eye(96,dtype=np.float32)
for nm,k in (("CV tat dinh",K0),("nhay",K)):
    t=time.time(); V=S.solve(k); print(nm,time.time()-t,V.shape)
    T=S.Table(V)
    for d in (0.8,1.2,1.6,2.0,2.5):
        # nguoi truoc mui huong vao (ψ=π), hong huong vao, nguoi truoc mui di cat ngang, quay lung
        q=[float(T(np.array(x),np.array(y),np.array(p),np.array(.9))) for x,y,p in ((d,0,np.pi),(0,d,-np.pi/2),(d,0,np.pi/2),(d,0,0.))]
        print("  d",d,"mui->vao %.2f  hong->vao %.2f  cat ngang %.2f  di xa %.2f"%tuple(q))
