// Rössler Attractor - Infinite Library (Sketch). Paste into a Sketch node's code editor.
// Continuous-time chaotic attractor: dx = -y - z, dy = x + a y, dz = b + z (x - c).
param("a", 0.2, 0.1, 0.4);
param("c", 5.7, 2.0, 10.0);
param("trail", 2200, 400, 5000);
param("speed", 1.0, 0.2, 3.0);
param("zoom", 1.0, 0.4, 2.5);

function draw(t) {
  background(0.04, 0.04, 0.08);
  const b = 0.2, dt = 0.018 * speed;
  let x = 0.5, y = 0.5, z = 0.5;
  const steps = floor(t * 140) + 600;
  const pts = [];
  for (let i = 0; i < steps; i++) {
    const dx = -y - z;
    const dy = x + a * y;
    const dz = b + z * (x - c);
    x += dx * dt;
    y += dy * dt;
    z += dz * dt;
    pts.push([x, y, z]);
  }
  const from = max(0, pts.length - trail);
  const k = min(width, height) / 34 * zoom;
  const rot = t * 0.15;
  const cosR = cos(rot), sinR = sin(rot);
  noFill();
  strokeWeight(2.0);
  for (let i = from + 1; i < pts.length; i++) {
    const p0 = pts[i - 1], p1 = pts[i];
    const f = (i - from) / (pts.length - from);
    const rx0 = p0[0] * cosR - p0[1] * sinR;
    const ry0 = (p0[0] * sinR + p0[1] * cosR) * 0.7 - p0[2] * 0.7;
    const rx1 = p1[0] * cosR - p1[1] * sinR;
    const ry1 = (p1[0] * sinR + p1[1] * cosR) * 0.7 - p1[2] * 0.7;
    const zNorm = min(max(p1[2] / 15.0, 0.0), 1.0);
    stroke(hsl(0.58 - 0.55 * zNorm * f, 0.85, 0.4 + 0.35 * f));
    line(width / 2 + rx0 * k, height * 0.55 + ry0 * k, width / 2 + rx1 * k, height * 0.55 + ry1 * k);
  }
}
