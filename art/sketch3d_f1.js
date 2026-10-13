// Formula-1 car for Sketch 3D. Nose points +x, ground at y = 0.
param("hue", 0.0, 0, 1);            // livery colour (0 = red)
param("sat", 0.9, 0, 1);
param("light", 0.42, 0.05, 0.9);
param("tyre_hue", 0.14, 0, 1);      // tyre compound band (soft = red, medium = yellow, hard = white)
param("tyre_sat", 0.95, 0, 1);
param("speed", 8, -20, 20);         // wheel spin
param("steer", 0.0, -0.5, 0.5);     // front wheel steering (rad)
param("ride", 0.0, -0.03, 0.12);    // ride height
param("bounce", 0.004, 0, 0.03);    // suspension wobble
param("front_wing", 0.12, 0, 0.5);  // front wing flap angle
param("rear_wing", 0.18, 0, 0.5);   // rear wing flap angle
param("halo", 1, 0, 1);             // halo on / off

var CACHE = (typeof CACHE === 'undefined') ? {} : CACHE;
var CARBON = [0.035, 0.035, 0.04], SILVER = [0.72, 0.74, 0.78], WHITE = [0.92, 0.92, 0.94], VISOR = [0.03, 0.05, 0.07];

function cosLerp(a, b, k) { var s = (1 - Math.cos(k * Math.PI)) / 2; return a + (b - a) * s; }
function ctrl(X, Y, x) {
  if (x <= X[0]) return Y[0];
  for (var i = 1; i < X.length; i++)
    if (x <= X[i]) return cosLerp(Y[i - 1], Y[i], (x - X[i - 1]) / (X[i] - X[i - 1]));
  return Y[Y.length - 1];
}
function spow(v, e) { return (v < 0 ? -1 : 1) * Math.pow(Math.abs(v), e); }

// monocoque control points, tail -> nose
var BX = [-1.7, -1.5, -0.9, -0.3, 0.2, 0.7, 1.2, 1.9, 2.3];
var BW = [0.03, 0.08, 0.20, 0.27, 0.24, 0.22, 0.16, 0.09, 0.03];
var BT = [0.24, 0.30, 0.50, 0.58, 0.50, 0.42, 0.32, 0.24, 0.20];
var BB = [0.22, 0.20, 0.17, 0.15, 0.14, 0.13, 0.12, 0.10, 0.12];

// station(v 0..1) -> {x, w, yt, yb, n, zo}; returns flat triangle list facing outward
function loft(N, M, station) {
  var rings = [], ctr = [], i, j;
  for (i = 0; i <= N; i++) {
    var s = station(i / N), yc = (s.yt + s.yb) / 2, hh = (s.yt - s.yb) / 2, zo = s.zo || 0, ring = [];
    for (j = 0; j < M; j++) {
      var a = j / M * Math.PI * 2, e = 2 / s.n;
      ring.push([s.x, yc + hh * spow(Math.sin(a), e), zo + s.w * spow(Math.cos(a), e)]);
    }
    rings.push(ring); ctr.push([s.x, yc, zo]);
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
function col(c) { fill(c[0], c[1], c[2]); }

// flat plate in the x-y plane (thickness z), drawn double-sided so it shows from both sides
function plate(pts, z, zthick) {
  var h = zthick / 2, k, n = pts.length;
  for (var side = -1; side <= 1; side += 2) {
    beginShape(TRIANGLE_FAN);
    for (k = 0; k < n; k++) vertex(pts[k][0], pts[k][1], z + side * h);
    endShape();
    beginShape(TRIANGLE_FAN);
    for (k = n - 1; k >= 0; k--) vertex(pts[k][0], pts[k][1], z + side * h);
    endShape();
  }
}

function wheel(spin, r, w, tyreCol) {
  push();
  rotateX(Math.PI / 2);                              // axis y -> z
  col(CARBON);               cylinder(r, w, 32);                 // tyre
  fill(tyreCol);             cylinder(r * 0.88, w + 0.006, 32);  // compound band
  fill(0.05, 0.05, 0.055);   cylinder(r * 0.80, w + 0.012, 32);  // sidewall
  col(SILVER);               cylinder(r * 0.52, w + 0.02, 24);   // rim
  rotateY(spin);
  col(CARBON);
  for (var q = 0; q < 5; q++) { push(); rotateY(q * Math.PI * 2 / 5); translate(r * 0.26, 0, 0); box(r * 0.5, w + 0.03, r * 0.07); pop(); }
  col(SILVER);               cylinder(r * 0.16, w + 0.04, 16);   // hub nut
  pop();
}

function strut(x1, y1, z1, x2, y2, z2) { tube(x1, y1, z1, x2, y2, z2, 0.012, 6); }

function draw(t) {
  var livery = hsl(hue, sat, light), tyre = hsl(tyre_hue, tyre_sat, tyre_sat < 0.1 ? 0.9 : 0.5);
  var spin = -t * speed, bob = ride + Math.sin(t * 9) * bounce;
  var RF = 0.30, WF = 0.27, RR = 0.33, WR = 0.36;          // front/rear tyre radius & width
  var XF = 1.35, XR = -1.55, TRACK = 0.70;                  // axle positions, wheel centre z

  // ---- car body (rides on the suspension) ----
  push();
  translate(0, bob, 0);

  fill(livery);
  emit(cached('mono', function () {
    return loft(70, 22, function (v) {
      var x = -1.7 + 4.0 * v;
      return { x: x, w: ctrl(BX, BW, x), yt: ctrl(BX, BT, x), yb: ctrl(BX, BB, x), n: 2.6 };
    });
  }));
  [1, -1].forEach(function (s) {
    emit(cached('pod' + s, function () {
      return loft(40, 18, function (v) {
        var x = 0.55 - 1.75 * v, round = Math.pow(Math.min(1, v * 7), 0.5);
        return { x: x, zo: s * 0.36, w: 0.17 * round * Math.pow(1 - Math.pow(v, 4), 0.5),
                 yt: 0.40 - 0.16 * v, yb: 0.10, n: 3 };
      });
    }));
  });

  // floor, bargeboards, sidepod inlets, diffuser
  col(CARBON);
  push(); translate(-0.25, 0.07, 0); box(2.9, 0.025, 1.0); pop();
  push(); translate(-1.7, 0.1, 0); box(0.35, 0.03, 0.8); pop();
  [1, -1].forEach(function (s) {
    push(); translate(0.9, 0.2, s * 0.44); box(0.55, 0.17, 0.015); pop();
    push(); translate(0.58, 0.26, s * 0.36); box(0.03, 0.15, 0.2); pop();
  });

  // cockpit opening, helmet, halo
  var cy = ctrl(BX, BT, 0.1);
  col(VISOR); push(); translate(0.1, cy + 0.003, 0); box(0.55, 0.01, 0.2); pop();
  col(WHITE); push(); translate(0.05, cy + 0.06, 0); sphere(0.095, 14); pop();
  col(VISOR); push(); translate(0.13, cy + 0.07, 0); box(0.05, 0.04, 0.13); pop();
  if (halo > 0.5) {
    col(CARBON);
    [1, -1].forEach(function (s) {
      tube(-0.1, cy + 0.02, s * 0.2, 0.2, cy + 0.2, s * 0.2, 0.017, 6);
      tube(0.2, cy + 0.2, s * 0.2, 0.46, cy + 0.15, s * 0.04, 0.017, 6);
    });
    tube(0.46, cy + 0.15, 0, 0.55, cy + 0.01, 0, 0.02, 6);
  }

  // shark fin and mirrors
  fill(livery);
  plate([[-0.55, 0.56], [-1.65, 0.32], [-1.65, 0.62], [-0.9, 0.62]], 0, 0.015);
  [1, -1].forEach(function (s) {
    push(); translate(0.55, cy - 0.02, s * 0.3); box(0.07, 0.04, 0.09); pop();
    col(CARBON); strut(0.52, cy - 0.04, s * 0.22, 0.55, cy - 0.02, s * 0.3); fill(livery);
  });

  // front wing: stacked flaps + end plates + nose pylons
  fill(livery);
  [0, 1, 2].forEach(function (k) {
    push(); translate(2.42 - k * 0.06, 0.05 + k * 0.055, 0); rotateZ(-front_wing * (0.6 + 0.3 * k));
    box(0.26 - k * 0.03, 0.015, 1.7); pop();
  });
  col(CARBON);
  push(); translate(2.45, 0.04, 0); box(0.3, 0.012, 1.74); pop();
  [1, -1].forEach(function (s) {
    fill(livery); push(); translate(2.42, 0.12, s * 0.86); box(0.5, 0.2, 0.014); pop();
    col(CARBON);  push(); translate(2.28, 0.15, s * 0.12); box(0.04, 0.1, 0.02); pop();
  });

  // rear wing: lower beam, main plane, flap, end plates, pillar
  col(CARBON);
  push(); translate(-1.9, 0.26, 0); rotateZ(-0.1); box(0.28, 0.015, 0.8); pop();
  push(); translate(-1.82, 0.4, 0); box(0.05, 0.4, 0.05); pop();
  fill(livery);
  push(); translate(-1.9, 0.62, 0); rotateZ(-rear_wing); box(0.3, 0.018, 1.0); pop();
  push(); translate(-1.97, 0.72, 0); rotateZ(-rear_wing * 1.6); box(0.22, 0.016, 1.0); pop();
  [1, -1].forEach(function (s) { push(); translate(-1.92, 0.52, s * 0.51); box(0.5, 0.5, 0.014); pop(); });
  pop();

  // ---- suspension arms (static, anchored to the car) ----
  col(CARBON);
  [1, -1].forEach(function (s) {
    var zw = s * (TRACK - 0.1);
    // front wishbones + push rod
    strut(XF - 0.28, 0.16, s * 0.2, XF, 0.17, zw); strut(XF + 0.28, 0.16, s * 0.2, XF, 0.17, zw);
    strut(XF - 0.25, 0.32, s * 0.2, XF, 0.3, zw);  strut(XF + 0.25, 0.32, s * 0.2, XF, 0.3, zw);
    // rear
    strut(XR - 0.25, 0.16, s * 0.15, XR, 0.18, zw); strut(XR + 0.25, 0.16, s * 0.15, XR, 0.18, zw);
    strut(XR - 0.22, 0.34, s * 0.15, XR, 0.34, zw); strut(XR + 0.22, 0.34, s * 0.15, XR, 0.34, zw);
  });

  // ---- wheels ----
  [1, -1].forEach(function (s) {
    push(); translate(XF, RF, s * TRACK); rotateY(steer); wheel(spin, RF, WF, tyre); pop();
    push(); translate(XR, RR, s * TRACK); wheel(spin, RR, WR, tyre); pop();
  });
}
