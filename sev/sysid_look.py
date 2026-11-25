import numpy as np
z=np.load("results/sysid.npz",allow_pickle=True)
for k in z.files: print(k,z[k].shape,z[k].dtype, z[k].ravel()[:8] if z[k].size else "")
