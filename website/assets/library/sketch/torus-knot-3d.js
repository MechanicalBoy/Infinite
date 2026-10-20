// Torus Knot 3D - Infinite Library (Sketch 3D). Paste into a Sketch 3D node's code editor.
// Parametric (p, q) torus knot rendered with tubular segments and orbiting satellites.
param("p", 3, 2, 7);
param("q", 4, 1, 9);
param("radius", 1.2, 0.4, 2.5);
param("tube_r", 0.08, 0.02, 0.25);
param("spin", 0.5, 0.0, 3.0);
param("hue", 0.62, 0.0, 1.0);

function draw(t) {
  push();
  rotateY(t * spin);
  rotateX(t * spin * 0.7);
  rotateZ(sin(t * 0.4) * 0.3);

  const P = floor(p), Q = floor(q);
  const segments = 120;
  const pts = [];

  for (let i = 0; i <= segments; i++) {
    const phi = (i / segments) * TAU;
    const r = radius * (0.8 + 0.3 * cos(Q * phi));
    const x = r * cos(P * phi);
    const y = r * sin(P * phi);
    const z = -radius * 0.5 * sin(Q * phi);
    pts.push([x, y, z]);
  }

  // Draw continuous tubular knot
  for (let i = 0; i < segments; i++) {
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const frac = i / segments;
    fill(hsl((hue + frac * 0.4) % 1.0, 0.75, 0.55));
    tube(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], tube_r, 12);
  }

  // Orbiting satellite beads along the knot
  const satellites = 6;
  for (let s = 0; s < satellites; s++) {
    const offset = (t * 0.3 + s / satellites) % 1.0;
    const idx = floor(offset * segments);
    const pos = pts[idx];
    push();
    translate(pos[0], pos[1], pos[2]);
    fill(hsl((hue + 0.5 + s / satellites) % 1.0, 0.9, 0.7));
    sphere(tube_r * 2.2, 10);
    pop();
  }

  pop();
}
