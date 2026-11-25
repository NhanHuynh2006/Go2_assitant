# REPORT_PAPER — gói bài báo + bản thảo (agent PAPER, 25/11/2026)

> Coordinator lưu lại từ báo cáo bàn giao của agent PAPER (agent bị chặn ghi .md trước đó; người dùng đã cho phép lưu báo cáo).
> Coordinator đã kiểm lại: MANUSCRIPT.md 5394 từ, refs.bib 41 mục, F0 tồn tại, `sha256sum -c SHA256SUMS_TEST` OK (mã đóng băng không đổi).

## Điều kiện chạy
1 nhân, nice 19, không kill, không xoá, không chạy thí nghiệm mới. make_all.py vẫn qua 97/97 điểm so khớp, chạy 2 lần cho kết quả giống hệt. Có 2 dòng PAPER trong research/LOG.csv.

## 1. Kiểm chứng tài liệu (nhật ký ở NOVELTY.md §5)
- **Đọc toàn văn (arXiv HTML):** C2U-MPPI, Biased-MPPI, PGIF-MPPI, DRA-MPPI, CN-CBF.
- **Chỉ đọc tóm tắt:** Malone T-RO 2017, Gonon RA-L 2021, MPPIPS-HWP.
- **Contingency-MPPI:** L4DC 2025, PMLR 283:869–880.

**Các sửa đổi:**
1. PGIF-MPPI chỉ có 1 tác giả (Mundane).
2. Tác giả đầu bài T-RO 2017 là Malone, không phải Chiang.
3. C2U-MPPI dùng Σ_c đầy đủ, tức có hướng, không đẳng hướng.
4. Biased-MPPI đã có ý chèn mẫu từ bộ điều khiển phụ, nên `prim` phải trình bày là ứng dụng của Biased-MPPI, không phải ý mới.
5. CN-CBF: chỉ trích câu "tới 18 % so với baseline mạnh nhất"; không in các số 95/92/82 % đọc từ hình. Robot của CN-CBF đi 0.25–1.0 m/s.

**Chưa kiểm được:** ngưỡng homicidal chauffeur l/R ≤ √(1−γ²)+γ·arcsin γ−1. Nguồn DTIC lỗi DNS, bản PDF UCSB cần `curl -k`; lệnh này bị chặn quyền và agent không lách. Bản thảo không in công thức, chỉ trích Isaacs 1965 và Pachter & Coates (DOI đã kiểm) cho định nghĩa.

## 2. MANUSCRIPT.md v0.1 (EN, ~5400 từ)
- **Các mục:** Abstract, Intro (3 đóng góp), Related, Setup, Method, Protocol, Results T1–T10, Discussion, Limitations, Conclusion.
- **Tham số Method đã đối chiếu với mã đóng băng:**
  - K=600, T=24, 96 mẫu prim
  - τ_g 1.2, ℓ 0.12, w_geo 40
  - λ=0.3·(Q15−min), c_hit 300
  - ngưỡng đích 0.35 m, giới hạn 300 s
- **Chỗ trống ⟦…⟧:**
  - Gazebo TEST §6.10 và Isaac TEST §6.11 (đã ghi sẵn quy tắc đăng ký trước)
  - Chó thật §6.12
  - Tác giả (SV tác giả đầu, Lê Mỹ Hà liên hệ)
  - Email, repo/DOI dữ liệu
  - Mã ⟦SV2027-xx⟧
- **Đơn vị:** chỉ HCMUTE.
- **Ghi chú:** không để bài được chấp nhận trước 01/2027.

## 3. refs.bib và hình
- **refs.bib:** 41 mục; DOI/arXiv đã kiểm qua Crossref và arXiv API; bibtex đọc không lỗi.
  - Holm 1979 không có DOI.
  - CHAMP chưa ghi commit.
- **Hình F0 (kiến trúc):** sinh bởi make_method_figure.py, ra SVG/PDF/PNG, được make_all.py gọi.

## Lưu ý
- Mô hình `helb` chưa đối chiếu với Helbing & Molnár 1995; đã ghi trong phần hạn chế.
- Isaac v3 (C1 87 vs B1 73, p=0.009) ghi rõ là **thăm dò**, không phải phép so đã đăng ký trước.

## File (results/paper_package/)
- MANUSCRIPT.md, refs.bib
- make_method_figure.py
- figures/F0_architecture.{svg,pdf,png}
- NOVELTY.md §5, REPRODUCE.md
- make_all.py
- checks/OUTPUT_SHA256SUMS (37 file)

## Cập nhật 25/11 (coordinator): ngưỡng homicidal chauffeur ĐÃ KIỂM
Người dùng cho phép tải bài. Bản PDF của tác giả (Bopardikar, Bullo, Hespanha, CDC 2007, doi 10.1109/CDC.2007.4434251) tải bình thường qua TLS, không cần `-k`.
- **Kết quả đối chiếu:** Eq. (2) của bài xác nhận đúng hàm √(1−γ²)+γ·arcsin γ−1, với l/R = c/ρ. Theo bài, khi l/R ≤ hàm này thì kẻ trốn có chiến lược thoát.
- **Đã sửa bản thảo:**
  - Thêm 1 đoạn vào Related Work kèm số liệu: l/R vượt ngưỡng 3,0–6,4 lần, với v_e = 0,3; v_p = 0,9–1,3; ω = 0,35; l = 0,43–0,64.
  - Thêm mục bib `bopardikar2007cooperative`.
  - Đánh dấu mục này trong NOVELTY.md §5 là VERIFIED.
- **Cách viết:** câu trong bài viết theo dạng điều kiện đủ để thoát, đúng như cách bài gốc phát biểu.
- **Còn lại:** chưa đọc trực tiếp Isaacs và Pachter–Coates.
