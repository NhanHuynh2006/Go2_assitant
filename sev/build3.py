import sys; sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant"); sys.path.insert(0, "/home/nhanhuynh/Documents/Go2_assitant/sev")
import numpy as np, nav_sev as S
from build import kern, D
for nm, sc in (("crowd_x05", .5), ("crowd_x2", 2.0)): np.save(D + f"V_{nm}.npy", S.solve(kern("crowd", sc)))
