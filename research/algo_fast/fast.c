// Ban C cua nav_local.astar (dung het so hoc float32 cua ban Python) va argmin khoang cach toi duong.
// gcc -O3 -march=native -ffp-contract=off -fPIC -shared fast.c -o fast.so -lm
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
typedef struct { float f, g; int r, c; } N;
static int lt(const N *a, const N *b) {
  if (a->f != b->f) return a->f < b->f;
  if (a->g != b->g) return a->g < b->g;
  if (a->r != b->r) return a->r < b->r;
  return a->c < b->c;
}
static N *hp; static int hn, hc;
static void push(N x) {
  if (hn == hc) { hc = hc ? hc * 2 : 4096; hp = realloc(hp, hc * sizeof(N)); }
  int i = hn++;
  while (i) { int p = (i - 1) / 2; if (!lt(&x, &hp[p])) break; hp[i] = hp[p]; i = p; }
  hp[i] = x;
}
static N pop(void) {
  N r = hp[0], x = hp[--hn]; int i = 0;
  for (;;) { int l = 2 * i + 1; if (l >= hn) break; if (l + 1 < hn && lt(&hp[l + 1], &hp[l])) l++;
    if (!lt(&hp[l], &x)) break; hp[i] = hp[l]; i = l; }
  hp[i] = x; return r;
}
static const double SQ2 = 1.4142135623730951;
static double hh(int r, int c, int gr, int gc) {
  int dr = abs(r - gr), dc = abs(c - gc), m = dr < dc ? dr : dc;
  return (double)(dr + dc) + (SQ2 - 2) * (double)m;
}
// tra ve do dai duong (0 = khong co); path: cap (r,c) tu start -> goal
int astar(const float *w, int H, int W, int sr, int sc, int gr, int gc, int *path, int cap) {
  static const int DR[8] = {-1, 1, 0, 0, -1, -1, 1, 1}, DC[8] = {0, 0, -1, 1, -1, 1, -1, 1};
  int n = H * W, found = 0, len = 0;
  double *gb = malloc(n * sizeof(double)); int *pa = malloc(n * sizeof(int));
  for (int i = 0; i < n; i++) { gb[i] = INFINITY; pa[i] = -1; }
  gb[sr * W + sc] = 0; hn = 0;
  push((N){(float)hh(sr, sc, gr, gc), 0.0f, sr, sc});
  while (hn) {
    N q = pop(); int r = q.r, c = q.c;
    if (r == gr && c == gc) { found = 1; break; }
    if ((double)q.g > gb[r * W + c]) continue;
    for (int k = 0; k < 8; k++) {
      int nr = r + DR[k], nc = c + DC[k];
      if (nr < 0 || nr >= H || nc < 0 || nc >= W) continue;
      float x = w[nr * W + nc];
      if (!isfinite(x)) continue;
      if (k >= 4 && !(isfinite(w[r * W + nc]) && isfinite(w[nr * W + c]))) continue;
      float st = (float)((k < 4 ? 1.0 : SQ2) * 0.5);
      float ng = q.g + st * (x + w[r * W + c]);
      if ((double)ng < gb[nr * W + nc]) {
        gb[nr * W + nc] = ng; pa[nr * W + nc] = r * W + c;
        push((N){ng + (float)hh(nr, nc, gr, gc), ng, nr, nc});
      }
    }
  }
  if (found) {
    for (int k = gr * W + gc; k >= 0; k = pa[k]) { if (len >= cap) break; path[2 * len] = k / W; path[2 * len + 1] = k % W; len++; }
    for (int i = 0; i < len / 2; i++) for (int j = 0; j < 2; j++) { int t = path[2 * i + j]; path[2 * i + j] = path[2 * (len - 1 - i) + j]; path[2 * (len - 1 - i) + j] = t; }
  }
  free(gb); free(pa); return len;
}
void path_argmin(const double *P, int64_t n, const double *sx, const double *sy, int m, int64_t *jt) {
  double e[512]; if (m > 512) m = 512;
  for (int64_t i = 0; i < n; i++) {
    double x = P[2 * i], y = P[2 * i + 1];
    for (int j = 0; j < m; j++) { double dx = x - sx[j], dy = y - sy[j]; dx *= dx; dy *= dy; e[j] = dx + dy; }
    double b = e[0]; for (int j = 1; j < m; j++) b = e[j] < b ? e[j] : b;
    int k = 0; while (e[k] != b) k++;
    jt[i] = k;
  }
}
