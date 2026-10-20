// Möbius Strip 3D - Infinite Library (Sketch 3D). Paste into a Sketch 3D node's code editor.
// Parametric non-orientable Möbius strip with transverse tubular rungs, edge rails and orbiting satellites.
param("twists", 1, 1, 5);
param("radius", 1.3, 0.5, 2.5);
param("width_r", 0.42, 0.1, 1.0);
param("ribs", 80, 24, 180);
param("spin", 0.6, 0.0, 3.0);
param("hue", 0.62, 0.0, 1.0);

function draw(t) {
  push();
  rotateY(t * spin);
  rotateX(t * spin * 0.65);
  rotateZ(sin(t * 0.35) * 0.25);

  const N = floor(ribs);
  const numTwists = floor(twists);
  const leftEdge = [];
  const rightEdge = [];
  const center = [];

  for (let i = 0; i <= N; i++) {
    const u = (i / N) * TAU;
    const halfTwist = (u * numTwists) * 0.5;
    const cosU = cos(u), sinU = sin(u);
    const cosH = cos(halfTwist), sinH = sin(halfTwist);

    const cx = radius * cosU;
    const cy = 0;
    const cz = radius * sinU;
    center.push([cx, cy, cz]);

    const dx = width_r * cosH * cosU;
    const dy = width_r * sinH;
    const dz = width_r * cosH * sinU;

    leftEdge.push([cx - dx, cy - dy, cz - dz]);
    rightEdge.push([cx + dx, cy + dy, cz + dz]);
  }

  // Draw transverse ribs connecting left and right edge
  for (let i = 0; i < N; i++) {
    const pL = leftEdge[i];
    const pR = rightEdge[i];
    const frac = i / N;
    fill(hsl((hue + frac * 0.45) % 1.0, 0.75, 0.52));
    tube(pL[0], pL[1], pL[2], pR[0], pR[1], pR[2], 0.018, 6);
  }

  // Draw longitudinal edge rails
  for (let i = 0; i < N; i++) {
    const L1 = leftEdge[i], L2 = leftEdge[i + 1];
    const R1 = rightEdge[i], R2 = rightEdge[i + 1];
    const frac = i / N;
    fill(hsl((hue + 0.15 + frac * 0.3) % 1.0, 0.85, 0.62));
    tube(L1[0], L1[1], L1[2], L2[0], L2[1], L2[2], 0.024, 8);
    tube(R1[0], R1[1], R1[2], R2[0], R2[1], R2[2], 0.024, 8);
  }

  // Orbiting pulse satellites traveling the full 2-circuit topology
  const satellites = 6;
  for (let s = 0; s < satellites; s++) {
    const phase = (t * 0.25 + s / satellites) % 1.0;
    const fullStep = phase * 2.0;
    const isFirstCircuit = fullStep < 1.0;
    const subFrac = isFirstCircuit ? fullStep : (fullStep - 1.0);
    const idx = floor(subFrac * N);
    const pos = isFirstCircuit ? leftEdge[idx] : rightEdge[idx];

    push();
    translate(pos[0], pos[1], pos[2]);
    fill(hsl((hue + 0.5 + s / satellites) % 1.0, 0.95, 0.72));
    sphere(0.065, 10);
    pop();
  }

  pop();
}
