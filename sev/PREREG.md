# SEV buoc 1 — quy dinh truoc khi nhin so (22/11/2026, 23:50)
Du lieu: fastsim ban chup sev/snap, mppi:ppl=32, seed 0-299 (crowd). Hazard do tu Crowd KHONG robot o seed 800-999 va tu nguoi that.
Don vi: (luot, thoi diem). Diem = max theo nguoi (V: 1-prod(1-V_j)), trang thai NGUOI THAT (tran tren cua moi ham), tuong that.
Chinh (P): duong = -2.0 s / -1.5 s truoc khi cham nguoi. Am = moc ngau nhien cach nhau >= 1 s co nguoi gan nhat < 4 m,
  khong cham trong 3 s toi va con >= 3 s truoc khi het luot; moi luot toi da 4 am (rng co dinh), can bang lai khi bootstrap.
Kho (H): am = thoi diem -2.0/-1.5 s truoc cuc tieu cuc bo cua khoang ho than-nguoi (0 < d_min < 0.6 m, khong cham trong 3 s ke).
Ung vien: dist (ho than), ttc (van toc tuong doi), dce (ho nho nhat du doan 3 s), pgif, turn (khoang ho that cho phia lach), turn_const (2.1 s).
"Tot nhat khac" = AUC cao nhat trong chung tren cung tap (thien cho doi thu).
Dau va tham so: cua SEV khong do lai tren seed 0-299; cac ham doi thu dung tham so mac dinh cua chung.
CI: bootstrap theo LUOT (2000). QUA = dAUC >= 0.03 va CI95 cua dAUC > 0 o ca -2.0 va -1.5 s tren P, va dAUC > 0 tren H.
Khong qua -> dung, khong noi MPPI.
