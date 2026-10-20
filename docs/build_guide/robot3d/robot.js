// 3D model of the finished Raqib ESP32 robot 3.0 (units: mm; x = forward, y = up, z = the robot's right side).
// Parts are real sizes and sit where the build guide places them. Board tops use textures drawn
// from the same part drawings as the guide (textures.py).
import * as THREE from './node_modules/three/build/three.module.js';
import { RoundedBoxGeometry } from './node_modules/three/examples/jsm/geometries/RoundedBoxGeometry.js';

const loader = new THREE.TextureLoader();
const texCache = {};
export function loadTextures(names) {
  return Promise.all(names.map((n) => new Promise((res) => loader.load(`tex/${n}.png`, (t) => {
    t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; texCache[n] = t; res();
  }))));
}

const M = {
  acrylic: new THREE.MeshPhysicalMaterial({ color: 0xcfe9ff, transparent: true, opacity: 0.42, roughness: 0.08, metalness: 0,
    clearcoat: 1, side: THREE.DoubleSide, depthWrite: false }),
  acrylicEdge: new THREE.MeshStandardMaterial({ color: 0x9cc8e8, roughness: 0.2, transparent: true, opacity: 0.75 }),
  brass: new THREE.MeshStandardMaterial({ color: 0xd4af37, metalness: 0.85, roughness: 0.3 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x1d1f22, roughness: 0.9 }),
  yellow: new THREE.MeshStandardMaterial({ color: 0xf2c230, roughness: 0.55 }),
  steel: new THREE.MeshStandardMaterial({ color: 0xc9ced3, metalness: 0.8, roughness: 0.3 }),
  alu: new THREE.MeshStandardMaterial({ color: 0xb8bec4, metalness: 0.7, roughness: 0.35 }),
  black: new THREE.MeshStandardMaterial({ color: 0x18191b, roughness: 0.6 }),
  blackPlastic: new THREE.MeshStandardMaterial({ color: 0x232528, roughness: 0.45 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xe3b94b, metalness: 0.9, roughness: 0.25 }),
  blueTerm: new THREE.MeshStandardMaterial({ color: 0x2a63b8, roughness: 0.5 }),
  red: new THREE.MeshStandardMaterial({ color: 0xc0392b, roughness: 0.5 }),
  white: new THREE.MeshStandardMaterial({ color: 0xf4f4f4, roughness: 0.6 }),
  mesh: new THREE.MeshStandardMaterial({ color: 0xc9ced3, metalness: 0.6, roughness: 0.5, wireframe: false }),
  copper: new THREE.MeshStandardMaterial({ color: 0xc87533, metalness: 0.7, roughness: 0.35 }),
  lens: new THREE.MeshPhysicalMaterial({ color: 0x0b1626, roughness: 0.05, metalness: 0.2, clearcoat: 1 }),
};
const side = (hex) => new THREE.MeshStandardMaterial({ color: hex, roughness: 0.6 });

export const ANCHORS = {};   // label name -> THREE.Vector3 (world)

function box(w, h, d, mat, x, y, z, parent) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
}
function cyl(r, h, mat, x, y, z, parent, axis = 'y', seg = 32) {
  const g = new THREE.CylinderGeometry(r, r, h, seg);
  if (axis === 'z') g.rotateX(Math.PI / 2);
  if (axis === 'x') g.rotateZ(Math.PI / 2);
  const m = new THREE.Mesh(g, mat); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; parent.add(m); return m;
}

/** A printed circuit board: w (x) x d (z), top face textured; returns a group whose origin is the board's top-left corner
 *  (x = left edge, z = top edge of the texture), top surface at y = 0. */
function pcb(tex, w, d, edgeHex, parent, t = 1.6) {
  const g = new THREE.Group();
  const mats = [side(edgeHex), side(edgeHex), new THREE.MeshStandardMaterial({ map: texCache[tex], roughness: 0.55 }),
    side(edgeHex), side(edgeHex), side(edgeHex)];
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, t, d), mats);
  m.position.set(w / 2, -t / 2, d / 2); m.castShadow = true; m.receiveShadow = true; g.add(m);
  parent.add(g); return g;
}
function pinRow(parent, x0, z, n, pitch, along = 'x', y = 0) {
  for (let i = 0; i < n; i++) {
    const x = along === 'x' ? x0 + i * pitch : x0, zz = along === 'x' ? z : z + i * pitch;
    box(2.4, 2.5, 2.4, M.black, x, y + 1.25, zz, parent);
    box(0.64, 6, 0.64, M.gold, x, y + 3, zz, parent);
  }
}

// ---------------------------------------------------------------------------------------- wires
const wires = [];
export function wire(points, color, r = 0.75) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.35);
  const m = new THREE.Mesh(new THREE.TubeGeometry(curve, Math.max(24, points.length * 18), r, 8, false),
    new THREE.MeshStandardMaterial({ color, roughness: 0.45 }));
  m.castShadow = true; wires.push(m); return m;
}
const C = { v5: 0xe23b2e, v33: 0xf08a00, gnd: 0x2a2e31, sda: 0x2d6be0, scl: 0xd9a800, bat: 0xc0151b, mot: 0x8d5a3b,
  sig: 0x1e9e55, pwm: 0xf2b705, s3: 0xe0458b, s4: 0x0ea5c6, s5: 0x6d7a12, s6: 0xb4530f, audio: 0x7a7f87, usb: 0x3c4046 };

// ---------------------------------------------------------------------------------------- the robot
export function buildRobot(scene) {
  const R = new THREE.Group(); scene.add(R);
  const Y1 = 46, T = 3, TY = Y1 + T;                  // one acrylic deck, y 46..49
  const shape = new THREE.Shape();
  const x0 = -112, x1 = 98, z0 = -68, z1 = 68, rr = 26;
  shape.moveTo(x0 + rr, z0); shape.lineTo(x1 - rr, z0); shape.quadraticCurveTo(x1, z0, x1, z0 + rr);
  shape.lineTo(x1, z1 - rr); shape.quadraticCurveTo(x1, z1, x1 - rr, z1); shape.lineTo(x0 + rr, z1);
  shape.quadraticCurveTo(x0, z1, x0, z1 - rr); shape.lineTo(x0, z0 + rr); shape.quadraticCurveTo(x0, z0, x0 + rr, z0);
  for (let i = 0; i < 7; i++) for (let j = 0; j < 4; j++) {
    const h = new THREE.Path(); h.absarc(-92 + i * 28, -42 + j * 28, 2.2, 0, Math.PI * 2, true); shape.holes.push(h);
  }
  const g = new THREE.ExtrudeGeometry(shape, { depth: T, bevelEnabled: false, curveSegments: 24 });
  g.rotateX(Math.PI / 2); g.translate(0, Y1 + T, 0);
  const deck = new THREE.Mesh(g, M.acrylic); deck.receiveShadow = true; deck.castShadow = true; R.add(deck);
  R.add(new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), new THREE.LineBasicMaterial({ color: 0x7fb0d6 })));
  ANCHORS['Acrylic deck'] = new THREE.Vector3(70, TY, -55);

  // ---------------- 2WD: two TT motors + wheels at the front, a caster at the back
  const wheel = (x, zW) => {
    cyl(33, 26, M.rubber, x, 33, zW, R, 'z', 48);
    for (let k = 0; k < 18; k++) {
      const a = (k / 18) * Math.PI * 2;
      box(5, 2, 26.5, M.rubber, x + Math.cos(a) * 33, 33 + Math.sin(a) * 33, zW, R).rotation.z = a + Math.PI / 2;
    }
    cyl(15, 27, M.yellow, x, 33, zW, R, 'z', 32);
    cyl(4, 30, M.white, x, 33, zW, R, 'z', 16);
  };
  for (const s of [1, -1]) {
    wheel(40, s * 86);
    box(64, 22, 18, M.yellow, 22, 34, s * 56, R);                 // gearbox under the deck
    cyl(10, 24, M.steel, -18, 34, s * 56, R, 'x');                 // motor can
    wires.push(wire([[-30, 38, s * 52], [-38, 44, s * 40], [-30, 52, s * 30], [-8, TY + 12, s * 14], [6, TY + 11, s * 6]], C.mot, 0.8));
  }
  ANCHORS['2 TT motors + wheels (2WD)'] = new THREE.Vector3(40, 60, 99);
  cyl(5, 20, M.steel, -96, 36, 0, R);                              // caster post
  const ball = new THREE.Mesh(new THREE.SphereGeometry(10, 24, 16), M.steel); ball.position.set(-96, 10, 0); ball.castShadow = true; R.add(ball);
  box(26, 6, 26, M.steel, -96, 43, 0, R);
  ANCHORS['Caster wheel'] = new THREE.Vector3(-96, 12, 0);

  // motor battery under the deck
  box(77, 20, 41, M.blackPlastic, -48, Y1 - 10.5, 0, R);
  for (const dz of [-10, 10]) cyl(9, 65, new THREE.MeshStandardMaterial({ color: 0x2f7dd1, roughness: 0.4 }), -48, Y1 - 19, dz, R, 'x');
  box(8, 6, 10, M.red, -8, Y1 - 10, 16, R);
  ANCHORS['Motor battery 2 × 18650 (under)'] = new THREE.Vector3(-48, 26, 22);

  // ---------------- power bank (the ESP32's battery) at the back
  const bank = new THREE.Mesh(new RoundedBoxGeometry(62, 14, 95, 4, 5), M.blackPlastic);
  bank.position.set(-78, TY + 7, 0); bank.castShadow = true; bank.receiveShadow = true; R.add(bank);
  for (let k = 0; k < 4; k++) {
    const led = new THREE.Mesh(new THREE.SphereGeometry(1.3, 12, 8), new THREE.MeshBasicMaterial({ color: k < 3 ? 0x3ddc84 : 0x3a3f45 }));
    led.position.set(-100, TY + 14.3, -30 + k * 6); R.add(led);
  }
  box(3, 4, 9, M.steel, -46.5, TY + 7, 30, R);
  ANCHORS['USB power bank (ESP32 only)'] = new THREE.Vector3(-90, TY + 15, -20);

  // ---------------- half breadboard (the wiring hub), across the robot
  const BX = -42, BZ = -27.5, BH = 9;
  const bb = new THREE.Group(); bb.position.set(BX, TY, BZ); R.add(bb);
  box(83, BH, 55, new THREE.MeshStandardMaterial({ color: 0xf3f1ea, roughness: 0.7 }), 41.5, BH / 2, 27.5, bb);
  const top = pcb('bread', 83, 55, 0xcdc7b5, bb, 0.2); top.position.y = BH + 0.2;
  ANCHORS['Half breadboard (wiring hub)'] = new THREE.Vector3(BX + 8, TY + BH, BZ + 50);
  const BT = TY + BH;
  // DRV8833, MPU6050, AHT20 plugged into it
  pcb('drv', 18, 22, 0x4f1b5c, R).position.set(BX + 6, BT + 5, BZ + 8);
  ANCHORS['DRV8833 motor driver'] = new THREE.Vector3(BX + 15, BT + 6, BZ + 18);
  pcb('mpu', 21, 16, 0x163f80, R).position.set(BX + 34, BT + 5, BZ + 8);
  ANCHORS['MPU6050 motion sensor'] = new THREE.Vector3(BX + 44, BT + 6, BZ + 15);
  pcb('aht', 15, 12, 0x4a2a70, R).position.set(BX + 62, BT + 5, BZ + 34);
  ANCHORS['AHT20 + BMP280 climate'] = new THREE.Vector3(BX + 69, BT + 6, BZ + 40);
  for (const [x, z, n] of [[BX + 6, BZ + 30, 6], [BX + 34, BZ + 24, 8], [BX + 62, BZ + 46, 4]]) {
    for (let i = 0; i < n; i++) box(2.4, 5, 2.4, M.black, x + 1.3 + i * 2.54, BT + 2.5, z, R);
  }

  // ---------------- XIAO ESP32S3 Sense standing on a bracket, camera looking forward over the sonar
  const XX = 66, XB = TY + 30;                         // bracket top
  box(4, 30, 26, new THREE.MeshStandardMaterial({ color: 0xe9eef3, roughness: 0.5 }), XX - 6, TY + 15, 0, R);
  box(14, 2, 26, new THREE.MeshStandardMaterial({ color: 0xe9eef3, roughness: 0.5 }), XX - 2, TY + 1, 0, R);
  const xiao = new THREE.Group(); xiao.position.set(XX, XB, 0); R.add(xiao);
  const xb = pcb('xiao', 17.5, 21, 0x1b1d20, xiao, 1.2);   // board, top face pointing backwards (-x)
  xb.rotation.set(0, 0, Math.PI / 2); xb.position.set(0, 0, -8.75);
  xb.rotation.set(0, Math.PI / 2, Math.PI / 2);
  xb.position.set(-0.6, 0, 8.75);
  box(4, 21, 17.5, new THREE.MeshStandardMaterial({ color: 0x16191c, roughness: 0.5 }), 2.6, 10.5, 0, xiao);   // Sense board
  box(3, 8, 8, M.black, 6, 12, 0, xiao);                                                                        // camera module
  cyl(3, 2.4, M.lens, 8, 12, 0, xiao, 'x', 24);
  box(3.2, 3, 9, M.steel, -0.6, 22, 0, xiao);                                                                  // USB-C on top
  const led = new THREE.Mesh(new THREE.SphereGeometry(0.9, 10, 8), new THREE.MeshBasicMaterial({ color: 0xff9a2e }));
  led.position.set(-1.6, 3, 5); xiao.add(led);
  ANCHORS['XIAO ESP32S3 Sense (camera forward)'] = new THREE.Vector3(XX + 8, XB + 12, 0);
  // USB-C cable from the power bank up to the XIAO
  wires.push(wire([[-46, TY + 7, 30], [-30, TY + 16, 46], [20, TY + 36, 40], [XX - 1, XB + 34, 10], [XX - 0.6, XB + 24, 0]], C.usb, 1.6));

  // ---------------- HC-SR04P at the front edge, below the camera
  const sg = new THREE.Group(); sg.position.set(92, TY, 0); R.add(sg);
  box(6, 2, 40, M.black, -3, 1, 0, sg);
  box(2, 24, 40, M.black, -6.5, 12, 0, sg);
  const sb = pcb('hcsr04', 45, 20, 0x163f80, sg);
  sb.setRotationFromMatrix(new THREE.Matrix4().makeBasis(new THREE.Vector3(0, 0, -1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, -1, 0)));
  sb.position.set(-3, 25, 22.5);
  for (const dz of [-13, 13]) {
    cyl(8, 12, M.steel, 3, 13, dz, sg, 'x', 32);
    cyl(6.4, 12.4, new THREE.MeshStandardMaterial({ color: 0x3a3f45, roughness: 0.9 }), 3.3, 13, dz, sg, 'x', 32);
  }
  ANCHORS['HC-SR04P distance sensor (3.3 V)'] = new THREE.Vector3(98, TY + 14, 18);

  // ---------------- jumpers: XIAO pins down to the breadboard (8 signals + 3V3 + GND)
  const cols = [C.sig, C.sig, 0x8a55e8, 0x8a55e8, C.sda, C.scl, C.s3, C.s4, C.v33, C.gnd];
  cols.forEach((c, i) => {
    const zz = -7.5 + (i % 5) * 3.6, side = i < 5 ? -1 : 1;
    const start = [XX - 2, XB + 2 + (i % 5) * 3, side * 9];
    const end = [BX + 10 + i * 7.2, BT + 1, BZ + (i < 5 ? 3 : 52)];
    wires.push(wire([start, [XX - 14, XB - 6, side * 14], [30, TY + 24, zz * 2], [end[0] + 6, BT + 12, end[2] + (i < 5 ? 6 : -6)], end], c, 0.55));
  });
  // sonar to the breadboard
  [C.v33, C.s3, C.s4, C.gnd].forEach((c, i) => {
    wires.push(wire([[88, TY + 3, -4 + i * 2.6], [70, TY + 8, -12 + i * 2], [42, TY + 14, -16 + i * 3], [BX + 70 + i * 2.6, BT + 1, BZ + 4]], c, 0.55));
  });
  // battery leads up to the DRV8833
  wires.push(wire([[-8, Y1 - 6, 20], [-14, Y1 + 6, 22], [-28, BT + 8, 10], [BX + 7, BT + 6, BZ + 5]], C.bat, 0.8));
  wires.push(wire([[-8, Y1 - 12, 20], [-16, Y1 + 4, 24], [-30, BT + 6, 12], [BX + 9.5, BT + 6, BZ + 5]], C.gnd, 0.8));
  ANCHORS['Jumper wires (colour-coded)'] = new THREE.Vector3(30, TY + 24, 0);

  wires.forEach((w) => R.add(w));
  return R;
}
