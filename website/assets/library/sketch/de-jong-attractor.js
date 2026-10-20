// De Jong Attractor - Infinite Library (Sketch). Paste into a Sketch node's code editor.
// Peter de Jong chaotic attractor: x' = sin(a y) - cos(b x), y' = sin(c x) - cos(d y).
param("a", 1.4, -3.0, 3.0);
param("b", -2.3, -3.0, 3.0);
param("c", 2.4, -3.0, 3.0);
param("d", -2.1, -3.0, 3.0);
param("points", 14000, 2000, 35000);
param("drift", 0.12, 0.0, 0.8);
param("size", 1.6, 0.5, 4.0);
param("zoom", 1.0, 0.5, 2.5);

function draw(t) {
  background(0.04, 0.04, 0.08);
  const at = a + 0.18 * sin(t * drift);
  const bt = b + 0.15 * cos(t * drift * 0.85);
  const ct = c + 0.16 * sin(t * drift * 0.7);
  const dt = d + 0.12 * cos(t * drift * 0.6);

  let x = 0.1, y = 0.1;
  const k = min(width, height) * 0.22 * zoom;
  noStroke();

  for (let i = 0; i < points; i++) {
    const nx = sin(at * y) - cos(bt * x);
    const ny = sin(ct * x) - cos(dt * y);
    x = nx;
    y = ny;
    if (i > 30) {
      const frac = i / points;
      const hue = (0.60 + 0.38 * frac + 0.05 * sin(t * 0.2)) % 1.0;
      fill(hsl(hue, 0.82, 0.56, 0.36));
      circle(width / 2 + x * k, height / 2 + y * k, size);
    }
  }
}
