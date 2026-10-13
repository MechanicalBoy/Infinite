// Sports coupe for Sketch 3D. Nose points +x, ground at y = -0.5.
// Body and cabin are lofted superellipse cross-sections (smooth rounded panels),
// then wheels, lights, mirrors and spoiler are layered on top.

// Knobs (each param() becomes a modulatable control on the node)
param("length", 1.25, 0.9, 1.7);      // half length of the body
param("width", 0.52, 0.4, 0.7);       // half width of the body
param("body_h", 1.0, 0.6, 1.6);       // body height
param("roof", 1.0, 0.5, 1.6);         // cabin / roof height
param("wheel_r", 0.27, 0.18, 0.40);   // wheel radius
param("ride", 0.0, -0.08, 0.25);      // ride height
param("speed", 6, -14, 14);           // wheel spin
param("steer", 0.0, -0.6, 0.6);       // front wheel steering (rad)
param("bounce", 0.008, 0, 0.06);      // suspension wobble
param("hue", 0.61, 0, 1);             // paint colour
param("sat", 0.78, 0, 1);
param("light", 0.38, 0.05, 0.9);
param("spoiler", 1, 0, 1);            // 1 = rear wing on

var L = 1.25, W = 0.52, GROUND = -0.5, BH = 1, ROOF = 1, LIFT = 0;
var PAINT = [0.08, 0.22, 0.65], GLASS = [0.04, 0.07, 0.10], TRIM = [0.02, 0.02, 0.025];
var CACHE = (typeof CACHE === 'undefined') ? {} : CACHE;

function cosLerp(a, b, k) { var s = (1 - Math.cos(k * Math.PI)) / 2; return a + (b - a) * s; }
function profile(U, Y, u) {
  if (u <= U[0]) return Y[0];
  for (var i = 1; i < U.length; i++)
    if (u <= U[i]) return cosLerp(Y[i - 1], Y[i], (u - U[i - 1]) / (U[i] - U[i - 1]));
  return Y[Y.length - 1];
}
function spow(v, e) { return (v < 0 ? -1 : 1) * Math.pow(Math.abs(v), e); }

// side profile of the lower body
var TU = [-1, -0.85, -0.5, 0, 0.45, 0.8, 1], TY = [-0.02, 0.10, 0.10, 0.07, 0.01, -0.08, -0.20];
function topY(x) { return profile(TU, TY, x / L) + LIFT; }
function botY(x) { return -0.33 + 0.10 * Math.pow(Math.abs(x / L), 6); }
function bodyW(x) {
  var u = x / L;
  return W * Math.pow(Math.max(0, 1 - Math.pow(Math.abs(u), 5)), 0.45) * (1 - 0.06 * Math.max(0, -u));
}

// station(i/N) -> {x, w, yt, yb, n};  returns flat [x,y,z,...] triangle list facing outward
function loft(N, M, station) {
  var rings = [], ctr = [], i, j;
  for (i = 0; i <= N; i++) {
    var s = station(i / N), yc = (s.yt + s.yb) / 2, hh = (s.yt - s.yb) / 2, ring = [];
    for (j = 0; j < M; j++) {
      var a = j / M * Math.PI * 2, e = 2 / s.n;
      ring.push([s.x, yc + hh * spow(Math.sin(a), e), s.w * spow(Math.cos(a), e)]);
    }
    rings.push(ring); ctr.push([s.x, yc, 0]);
  }
  var out = [];
  function tri(a, b, c, o) {
    var ux = b[0]-a[0], uy = b[1]-a[1], uz = b[2]-a[2], vx = c[0]-a[0], vy = c[1]-a[1], vz = c[2]-a[2];
    var nx = uy*vz - uz*vy, ny = uz*vx - ux*vz, nz = ux*vy - uy*vx;
    var cx = (a[0]+b[0]+c[0])/3 - o[0], cy = (a[1]+b[1]+c[1])/3 - o[1], cz = (a[2]+b[2]+c[2])/3 - o[2];
    if (nx*cx + ny*cy + nz*cz < 0) { var t = b; b = c; c = t; }
    out.push(a[0],a[1],a[2], b[0],b[1],b[2], c[0],c[1],c[2]);
  }
  for (i = 0; i < N; i++)
    for (j = 0; j < M; j++) {
      var j2 = (j + 1) % M, p = rings[i][j], q = rings[i+1][j], r = rings[i+1][j2], s2 = rings[i][j2];
      tri(p, q, r, ctr[i]); tri(p, r, s2, ctr[i]);
    }
  return out;
}
function emit(tris) {
  beginShape(TRIANGLES);
  for (var k = 0; k < tris.length; k += 3) vertex(tris[k], tris[k+1], tris[k+2]);
  endShape();
}
function cached(name, build) { if (!CACHE[name]) CACHE[name] = build(); return CACHE[name]; }
function paint(c) { fill(c[0], c[1], c[2]); }

// cabin: x from CA to CB, rounded canopy
var CA = -0.78, CB = 0.55;
function cabinStation(roofLift, widen, bottomTop) {
  return function (v) {
    var k = Math.abs(2 * v - 1);
    var w = 0.40 * Math.pow(Math.max(0, 1 - Math.pow(k, 4)), 0.4) * widen;
    var top = 0.02 + LIFT + 0.40 * ROOF * Math.pow(Math.max(0, 1 - Math.pow(k, 2.6)), 0.5);
    return { x: CA + (CB - CA) * v, w: w, yt: top + roofLift, yb: bottomTop ? top + roofLift - 0.045 : 0.0, n: 6 };
  };
}

function wheel(spin, r) {
  push();
  rotateX(Math.PI / 2);                       // axis y -> z
  var k = r / 0.27;
  paint(TRIM);      cylinder(r, 0.20, 28); // tyre
  paint([0.72, 0.74, 0.78]); cylinder(0.19 * k, 0.19, 28);  // rim barrel
  paint([0.10, 0.10, 0.12]); cylinder(0.165 * k, 0.21, 28); // rim face (dark)
  rotateY(spin);
  paint([0.82, 0.84, 0.88]);
  for (var q = 0; q < 5; q++) {
    push(); rotateY(q * Math.PI * 2 / 5); translate(0.09 * k, 0, 0); box(0.17 * k, 0.225, 0.045); pop();
  }
  cylinder(0.05 * k, 0.235, 14);                  // hub
  pop();
}

function draw(t) {
  // read knobs; geometry is rebuilt only when a shape knob changes
  L = length; W = width; BH = body_h; ROOF = roof;
  LIFT = (BH - 1) * 0.3;
  var key = [L, W, BH, ROOF].join(',');
  if (CACHE.key !== key) CACHE = { key: key };
  var spin = -t * speed;
  var rideY = ride + (wheel_r - 0.27) + Math.sin(t * 8) * bounce;
  var pc = hsl(hue, sat, light);

  push();
  translate(0, rideY, 0);

  // lower body
  fill(pc);
  emit(cached('body', function () {
    return loft(44, 22, function (v) {
      var x = -L + 2 * L * v;
      return { x: x, w: bodyW(x), yt: topY(x), yb: botY(x), n: 3.5 };
    });
  }));

  // glass canopy, then a thin body-colour roof skin on top of it
  paint(GLASS);
  emit(cached('glass', function () { return loft(36, 22, cabinStation(0, 1, false)); }));
  fill(pc);
  emit(cached('roof', function () { return loft(36, 22, cabinStation(0.004, 1.02, true)); }));

  // front and rear lights
  paint([1.0, 0.96, 0.78]);
  [1, -1].forEach(function (s) {
    push(); translate(0.88 * L, topY(0.88 * L) - 0.07, s * bodyW(0.88 * L) * 0.62);
    scale(1.5, 0.5, 1.1); sphere(0.07, 10); pop();
  });
  paint([1.0, 0.08, 0.05]);
  [1, -1].forEach(function (s) {
    push(); translate(-0.93 * L, topY(-0.93 * L) - 0.05, s * bodyW(-0.93 * L) * 0.6);
    box(0.04, 0.05, 0.2); pop();
  });

  // grille, splitter, diffuser, side skirts
  paint(TRIM);
  push(); translate(0.96 * L, -0.24, 0); box(0.05, 0.07, 0.34); pop();
  push(); translate(0.92 * L, -0.345, 0); box(0.22, 0.03, 0.55); pop();
  push(); translate(-0.92 * L, -0.345, 0); box(0.2, 0.03, 0.5); pop();
  [1, -1].forEach(function (s) { push(); translate(0, -0.34, s * 0.50); box(0.9, 0.04, 0.03); pop(); });

  // mirrors
  fill(pc);
  [1, -1].forEach(function (s) { push(); translate(0.40, 0.09 + LIFT, s * (W - 0.05)); box(0.09, 0.05, 0.08); pop(); });

  // spoiler
  if (spoiler > 0.5) {
    var st = topY(-0.87 * L);
    [1, -1].forEach(function (s) { push(); translate(-0.86 * L, st + 0.04, s * W * 0.35); box(0.05, 0.12, 0.03); pop(); });
    push(); translate(-0.88 * L, st + 0.11, 0); box(0.2, 0.025, W * 1.35); pop();
  }
  pop();

  // wheel arches and wheels (follow the body bounce, not the ground)
  var wy = GROUND + wheel_r + Math.sin(t * 8) * bounce * 0.3;
  [0.62 * L, -0.62 * L].forEach(function (x) {
    [1, -1].forEach(function (s) {
      push(); translate(x, wy, s * (W - 0.03)); rotateX(Math.PI / 2);
      paint([0.01, 0.01, 0.012]); cylinder(wheel_r + 0.04, 0.06, 28); pop();
      push(); translate(x, wy, s * (W - 0.06));
      if (x > 0) rotateY(steer);
      wheel(spin, wheel_r); pop();
    });
  });
}
