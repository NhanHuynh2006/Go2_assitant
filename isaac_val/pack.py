import json, numpy as np, glob
J = json.load(open("sysid_isaac.json")); R = json.load(open("sysid_random.json"))
o = {}
for k, d in J.items():
    o[k + "_steps"] = np.array([(["vx", "vy", "wz"].index(r["ax"]), r["u"], r["n"], r["ss"], r["p10"], r["p90"], r["gain"], r["tau"], r["delay"], r["t63"], r["t90"], *r["cross"], r["stop"]) for r in d["rows"]], float)
    o[k + "_wob"] = np.array([d["wob"][q] for q in d["wob"]])
o["steps_cols"] = "axis,cmd,n,v_ss,p10,p90,gain,tau,delay,t63,t90,cross_vx,cross_vy,cross_wz,stop_dist"
o["wob_cols"] = "x,y,yaw,roll,pitch,z,vx,vy,wz (rows: <=.2,.2-.5,>.5 m/s)"
o["random_json"] = json.dumps(R)
for f in glob.glob("raw_*_random.npz"):
    o[f[4:-4] + "_rec"] = np.load(f)["rec"]
o["rec_cols"] = "x,y,z,roll,pitch,yaw,vx,vy,wz,cmd_vx,cmd_vy,cmd_wz,fall,vz (50 Hz, T x env)"
np.savez_compressed("sysid_isaac.npz", **o); print({k: getattr(v, "shape", "") for k, v in o.items()})
