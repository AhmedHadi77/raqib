// 3D model of the finished Raqib budget robot (units: mm; x = forward, y = up, z = the robot's right side).
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
  const DECK_W = 210, DECK_D = 150, Y1 = 46, Y2 = 89, T = 3;      // bottom deck y 46..49, top deck y 89..92
  const deckShape = new THREE.Shape();
  const rr = 28, x0 = -110, x1 = 100, z0 = -75, z1 = 75;
  deckShape.moveTo(x0 + rr, z0); deckShape.lineTo(x1 - rr, z0); deckShape.quadraticCurveTo(x1, z0, x1, z0 + rr);
  deckShape.lineTo(x1, z1 - rr); deckShape.quadraticCurveTo(x1, z1, x1 - rr, z1); deckShape.lineTo(x0 + rr, z1);
  deckShape.quadraticCurveTo(x0, z1, x0, z1 - rr); deckShape.lineTo(x0, z0 + rr); deckShape.quadraticCurveTo(x0, z0, x0 + rr, z0);
  // mounting holes
  for (let i = 0; i < 7; i++) for (let j = 0; j < 4; j++) {
    const h = new THREE.Path(); h.absarc(-90 + i * 28, -45 + j * 30, 2.2, 0, Math.PI * 2, true); deckShape.holes.push(h);
  }
  for (const y of [Y1, Y2]) {
    const g = new THREE.ExtrudeGeometry(deckShape, { depth: T, bevelEnabled: false, curveSegments: 24 });
    g.rotateX(Math.PI / 2); g.translate(0, y + T, 0);
    const deck = new THREE.Mesh(g, M.acrylic); deck.receiveShadow = true; deck.castShadow = true; R.add(deck);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g, 30), new THREE.LineBasicMaterial({ color: 0x7fb0d6 }));
    R.add(edges);
  }
  ANCHORS['Top deck (acrylic)'] = new THREE.Vector3(-105, Y2 + 3, -60);
  ANCHORS['Bottom deck (acrylic)'] = new THREE.Vector3(-105, Y1 + 3, -60);

  // standoffs
  for (const [x, z] of [[-96, -62], [-96, 62], [86, -62], [86, 62]]) cyl(3.2, Y2 - Y1 - T, M.brass, x, (Y1 + T + Y2) / 2, z, R, 'y', 6);
  ANCHORS['Brass standoffs 40 mm'] = new THREE.Vector3(86, 70, 62);

  // ---------------- 4WD: four wheels + four TT motors under the bottom deck (front pair carries the encoders)
  const wheel = (x, zW) => {
    cyl(33, 26, M.rubber, x, 33, zW, R, 'z', 48);
    for (let k = 0; k < 18; k++) {        // tread ribs
      const a = (k / 18) * Math.PI * 2;
      const rib = box(5, 2, 26.5, M.rubber, x + Math.cos(a) * 33, 33 + Math.sin(a) * 33, zW, R);
      rib.rotation.z = a + Math.PI / 2;
    }
    cyl(15, 27, M.yellow, x, 33, zW, R, 'z', 32);
    cyl(4, 30, M.white, x, 33, zW, R, 'z', 16);
  };
  for (const s of [1, -1]) {
    const zW = s * 91;
    // front motor: shaft at x = 45, gearbox towards the back, can in the middle
    wheel(45, zW);
    box(48, 22, 18, M.yellow, 31, 33, s * 63, R);
    cyl(10, 22, M.steel, -4, 33, s * 63, R, 'x');
    cyl(2.7, 10, M.white, 45, 33, s * 50, R, 'z', 12);
    // rear motor: mirror image, shaft at x = -70
    wheel(-70, zW);
    box(48, 22, 18, M.yellow, -56, 33, s * 63, R);
    cyl(10, 22, M.steel, -21, 33, s * 63, R, 'x');
    // encoder disc + slot sensor on the front motor's inner shaft
    cyl(11, 1, M.black, 45, 33, s * 47, R, 'z', 40);
    for (let k = 0; k < 20; k++) {
      const a = (k / 20) * Math.PI * 2;
      box(1.6, 3, 1.2, M.white, 45 + Math.cos(a) * 8.5, 33 + Math.sin(a) * 8.5, s * 47, R).rotation.z = a;
    }
    const eb = pcb('enc', 32, 14, 0x163f80, R); eb.position.set(30, Y1 - 0.2, s * 47 - 7); eb.rotation.x = Math.PI; eb.position.z += 14;
    box(5, 12, 4, M.black, 45, Y1 - 7, s * 47 - 3.2, R); box(5, 12, 4, M.black, 45, Y1 - 7, s * 47 + 3.2, R);
    // each side's two motors joined (red-red, black-black), then up to the L298N
    wires.push(wire([[7, 40, s * 70], [-12, 45, s * 72], [-32, 40, s * 70]], 0xe23b2e, 0.7));
    wires.push(wire([[7, 37, s * 72], [-12, 43, s * 74], [-32, 37, s * 72]], 0x2a2e31, 0.7));
    wires.push(wire([[-12, 45, s * 72], [-14, 48, s * 55], [-22, 56, s * 34], [-28, 60, s * 18]], 0xe23b2e, 0.7));
    wires.push(wire([[-12, 43, s * 74], [-16, 47, s * 53], [-24, 55, s * 32], [-30, 60, s * 16]], 0x2a2e31, 0.7));
  }
  ANCHORS['4 wheels + 4 TT gear motors (4WD)'] = new THREE.Vector3(45, 55, 104);
  ANCHORS['Wheel encoders (slot sensor + disc)'] = new THREE.Vector3(45, 40, 47);

  // battery holder under the bottom deck (cells face down)
  box(77, 20, 41, M.blackPlastic, -25, Y1 - 10.5, 0, R);
  for (const dz of [-10, 10]) {
    cyl(9, 65, new THREE.MeshStandardMaterial({ color: 0x2f7dd1, roughness: 0.4 }), -25, Y1 - 19, dz, R, 'x');
  }
  box(8, 6, 10, M.red, 16, Y1 - 10, 16, R);
  ANCHORS['Battery 2 × 18650 (under the deck)'] = new THREE.Vector3(-25, 26, 22);

  // ---------------- L298N on the bottom deck
  const LX = -40, LZ = -22, LY = Y1 + T + 3;
  const l = pcb('l298n', 43, 43, 0x7d1f1a, R); l.position.set(LX, LY, LZ);
  for (let i = 0; i < 7; i++) box(2.2, 24, 22, M.black, LX + 12 + i * 3.4, LY + 12, LZ + 11, R);
  box(26, 3, 22, M.black, LX + 21.5, LY + 1.5, LZ + 11, R);
  for (const [x, z, w, d] of [[LX + 2.5, LZ + 8, 5, 10], [LX + 40.5, LZ + 8, 5, 10], [LX + 8, LZ + 37, 18, 6]])
    box(w, 9, d, M.blueTerm, x, LY + 4.5, z, R);
  pinRow(R, LX + 24, LZ + 38, 6, 2.54, 'x', LY);
  ANCHORS['L298N motor driver'] = new THREE.Vector3(LX + 21, LY + 24, LZ + 11);

  // battery leads: holder -> L298N, and up to the XL4015 at the back of the top deck
  wires.push(wire([[16, Y1 - 6, 20], [10, Y1 + 8, 10], [LX + 6, LY + 9, LZ + 37]], C.bat, 0.9));
  wires.push(wire([[16, Y1 - 12, 20], [8, Y1 + 6, 5], [LX + 12, LY + 9, LZ + 37]], C.gnd, 0.9));
  wires.push(wire([[16, Y1 - 6, 22], [-60, Y1 + 20, 30], [-103, 70, -20], [-104, Y2 + 10, -40], [-96, Y2 + 9, -58]], C.bat, 0.9));
  wires.push(wire([[16, Y1 - 12, 22], [-62, Y1 + 18, 26], [-106, 70, -22], [-106, Y2 + 9, -42], [-96, Y2 + 9, -63]], C.gnd, 0.9));

  // ---------------- top deck
  const TY = Y2 + T;
  // Raspberry Pi 4 (85 x 56), header edge towards the middle of the deck
  const PX = -62, PZ = 4, PY = TY + 5;
  for (const [x, z] of [[3.5, 3.5], [61.5, 3.5], [3.5, 52.5], [61.5, 52.5]]) cyl(2.5, 5, M.brass, PX + x, TY + 2.5, PZ + z, R, 'y', 6);
  pcb('pi', 85, 56, 0x145a37, R).position.set(PX, PY, PZ);
  box(21, 13.5, 16, M.steel, PX + 85 - 8, PY + 6.75, PZ + 10.5, R);          // ethernet
  box(17, 15.5, 13, M.steel, PX + 85 - 6.5, PY + 7.75, PZ + 29, R);           // USB 3
  box(17, 15.5, 13, M.steel, PX + 85 - 6.5, PY + 7.75, PZ + 47, R);           // USB 2
  box(15, 1.5, 15, M.alu, PX + 29.5, PY + 0.75, PZ + 29.5, R);
  for (let i = 0; i < 6; i++) box(1.4, 9, 15, M.alu, PX + 23.5 + i * 2.5, PY + 5, PZ + 29.5, R);   // CPU heatsink
  box(9, 3.2, 7.5, M.steel, PX + 11.5, PY + 1.6, PZ + 54, R);                 // USB-C
  cyl(3, 7, M.black, PX + 54, PY + 3, PZ + 54, R, 'z');                       // audio jack
  pinRow(R, PX + 10.5, PZ + 3.6, 20, 2.54, 'x', PY); pinRow(R, PX + 10.5, PZ + 6.1, 20, 2.54, 'x', PY);
  ANCHORS['Raspberry Pi 4 (2 GB)'] = new THREE.Vector3(PX + 30, PY + 9, PZ + 40);
  const pin = (n) => {                     // header pin tip (odd pins on the inner row)
    const i = Math.floor((n - 1) / 2);
    return [PX + 10.5 + i * 2.54, PY + 6.5, PZ + (n % 2 ? 3.6 : 6.1)];
  };

  // XL4015 at the back right (long side along z)
  const xl = pcb('xl4015', 54, 23, 0x163f80, R); xl.position.set(-80, TY + 2, -70); xl.rotation.y = -Math.PI / 2;
  cyl(8, 9, M.black, -90.5, TY + 6.5, -54.5, R);                                    // coil
  box(5, 6, 5, M.blueTerm, -95.4, TY + 5, -41.8, R);                                // trimmer
  box(9, 9, 10, M.blueTerm, -91, TY + 6.5, -66, R); box(9, 9, 10, M.blueTerm, -91, TY + 6.5, -20, R);   // IN / OUT
  cyl(5, 12, new THREE.MeshStandardMaterial({ color: 0x1d3f8f, roughness: 0.4 }), -104, TY + 8, -72, R);   // 1000 uF
  ANCHORS['XL4015 5 V converter'] = new THREE.Vector3(-95, TY + 10, -40);
  // cut USB cable: XL4015 OUT -> Pi USB-C
  wires.push(wire([[-100, TY + 8, -20], [-112, TY + 14, 10], [-100, TY + 16, 72], [-60, TY + 14, 70], [PX + 11.5, PY + 2, PZ + 64],
    [PX + 11.5, PY + 1.6, PZ + 58]], C.usb, 1.8));
  ANCHORS['Cut USB cable → Pi power'] = new THREE.Vector3(-108, TY + 14, 40);

  // hub board (perfboard) on the right side, ADS1115 next to it
  const HX = -58, HZ = -72, HW = 70, HD = 40;
  for (const [x, z] of [[3, 3], [HW - 3, 3], [3, HD - 3], [HW - 3, HD - 3]]) cyl(2.2, 4, M.brass, HX + x, TY + 2, HZ + z, R, 'y', 6);
  pcb('hub', HW, HD, 0x9c7f42, R).position.set(HX, TY + 4, HZ);
  ANCHORS['Hub board (rails + dividers)'] = new THREE.Vector3(HX + 35, TY + 6, HZ + 20);
  const rail = (i, x) => [HX + x, TY + 6, HZ + 3.6 + i * 2.9];          // 0 5V,1 3V3,2 GND,3 SDA,4 SCL
  // Pi -> hub rails
  const toRail = [[2, 0, C.v5], [1, 1, C.v33], [6, 2, C.gnd], [3, 3, C.sda], [5, 4, C.scl]];
  toRail.forEach(([n, i, c], k) => {
    const p = pin(n);
    wires.push(wire([p, [p[0], p[1] + 10 + k, p[2] - 2], [p[0] - 2, TY + 16 + k, HZ + HD + 6], rail(i, 60 - k * 3)], c));
  });

  // ADS1115 + MPU6050 in front of the hub
  pcb('ads', 28, 17, 0x4a2a70, R).position.set(20, TY + 3, -72);
  pinRow(R, 21.5, -55.5 + 0.5, 10, 2.54, 'x', TY + 3);
  ANCHORS['ADS1115 ADC'] = new THREE.Vector3(34, TY + 6, -64);
  pcb('mpu', 21, 16, 0x163f80, R).position.set(22, TY + 3, -42);
  ANCHORS['MPU6050 motion sensor'] = new THREE.Vector3(32, TY + 6, -34);
  // I2C + power wires from the hub to ADS / MPU
  [[0, C.v33, 1], [1, C.gnd, 2], [2, C.scl, 4], [3, C.sda, 3]].forEach(([k, c, ri]) => {
    wires.push(wire([[23 + k * 2.54, TY + 9, -55], [16, TY + 14, -56 + k], rail(ri, 66)], c, 0.6));
    wires.push(wire([[24 + k * 2.54, TY + 6, -27], [14, TY + 14, -36 + k], rail(ri, 64)], c, 0.6));
  });

  // AHT20 + BMP280 (front left) and MQ-135 (back left), PAM8403 + speaker (back middle)
  pcb('aht', 15, 12, 0x4a2a70, R).position.set(40, TY + 3, 50);
  ANCHORS['AHT20 + BMP280 climate'] = new THREE.Vector3(47, TY + 5, 56);
  const mqX = -104, mqZ = 40;
  pcb('mq', 32, 28, 0x163f80, R).position.set(mqX, TY + 3, mqZ);
  const can = cyl(10, 13, M.mesh, mqX + 13, TY + 9.5, mqZ + 12, R, 'y', 32);
  cyl(10.6, 3, M.copper, mqX + 13, TY + 4.5, mqZ + 12, R);
  ANCHORS['MQ-135 gas sensor'] = new THREE.Vector3(mqX + 13, TY + 16, mqZ + 12);
  pcb('pam', 21, 13, 0x145a37, R).position.set(-80, TY + 3, 5);
  ANCHORS['PAM8403 amplifier'] = new THREE.Vector3(-70, TY + 5, 12);
  const spk = cyl(20, 6, M.black, -96, TY + 3, 6, R, 'y', 48);
  cyl(14, 1, new THREE.MeshStandardMaterial({ color: 0x3b4048, roughness: 0.8 }), -96, TY + 6.5, 6, R, 'y', 40);
  cyl(5, 2, M.steel, -96, TY + 7.5, 6, R);
  ANCHORS['Speaker 3 W'] = new THREE.Vector3(-96, TY + 8, 6);
  // audio cable Pi jack -> PAM, wires to hub
  wires.push(wire([[PX + 54, PY + 3, PZ + 58], [PX + 50, PY + 12, PZ + 66], [-80, TY + 14, 30], [-76, TY + 6, 16]], C.audio, 1.1));
  wires.push(wire([[-60, TY + 5, 8], [-56, TY + 12, -10], rail(0, 8)], C.v5, 0.6));
  wires.push(wire([[-60, TY + 5, 10], [-54, TY + 12, -12], rail(2, 6)], C.gnd, 0.6));
  wires.push(wire([[-80, TY + 5, 12], [-90, TY + 8, 10], [-92, TY + 6, 8]], 0xe23b2e, 0.5));
  // AHT, MQ to the hub
  [[0, C.v33, 1], [1, C.gnd, 2], [2, C.scl, 4], [3, C.sda, 3]].forEach(([k, c, ri]) =>
    wires.push(wire([[41 + k * 3.5, TY + 4, 62], [30, TY + 20, 30 + k], [0, TY + 20, -10], rail(ri, 40 + k)], c, 0.6)));
  [[0, C.v5, 0], [1, C.gnd, 2], [3, C.audio, 2]].forEach(([k, c, ri]) =>
    wires.push(wire([[mqX + 4 + k * 6, TY + 3, mqZ + 27], [mqX + 16, TY + 26, mqZ - 10], [-60, TY + 26, -20], rail(ri, 20 + k * 3)], c, 0.6)));

  // ---------------- front: three HC-SR04 on brackets, webcam on a post
  const sonar = (x, z, angle, name, trigPin, echoPin, color) => {
    const g = new THREE.Group(); g.position.set(x, TY, z); g.rotation.y = angle; R.add(g);
    box(6, 2, 40, M.black, -3, 1, 0, g);                  // bracket foot
    box(2, 24, 40, M.black, -6.5, 12, 0, g);              // bracket upright
    const b = pcb('hcsr04', 45, 20, 0x163f80, g);
    b.setRotationFromMatrix(new THREE.Matrix4().makeBasis(new THREE.Vector3(0, 0, -1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, -1, 0)));
    b.position.set(-3, 25, 22.5);
    for (const dz of [-13, 13]) {
      cyl(8, 12, M.steel, 3, 13, dz, g, 'x', 32);
      cyl(6.4, 12.4, new THREE.MeshStandardMaterial({ color: 0x3a3f45, roughness: 0.9 }), 3.3, 13, dz, g, 'x', 32);
    }
    const w = new THREE.Vector3(); g.updateMatrixWorld(); w.set(-6, 3, 0).applyMatrix4(g.matrixWorld);
    ANCHORS[name] = new THREE.Vector3(6, 25, 0).applyMatrix4(g.matrixWorld);
    // 4 wires from the back of the sonar: VCC, Trig, Echo, GND
    const back = (k) => new THREE.Vector3(-6, 3, -4 + k * 2.6).applyMatrix4(g.matrixWorld).toArray();
    const tp = pin(trigPin), ep = pin(echoPin);
    wires.push(wire([back(0), [back(0)[0] - 18, TY + 18, back(0)[2] * 0.6], [0, TY + 16, -20], rail(0, 64)], C.v5, 0.6));
    wires.push(wire([back(3), [back(3)[0] - 18, TY + 16, back(3)[2] * 0.6], [2, TY + 14, -22], rail(2, 64)], C.gnd, 0.6));
    wires.push(wire([back(1), [back(1)[0] - 20, TY + 24, back(1)[2] * 0.5], [tp[0] + 4, tp[1] + 16, tp[2] - 6], tp], color, 0.6));
    wires.push(wire([back(2), [back(2)[0] - 20, TY + 22, back(2)[2] * 0.5], [ep[0] + 4, ep[1] + 14, ep[2] - 7], ep], color, 0.6));
  };
  sonar(92, 0, 0, 'HC-SR04 centre', 18, 22, C.s3);
  sonar(76, -50, Math.PI / 4, 'HC-SR04 left (45°)', 32, 36, C.s5);     // +45° about y turns it towards -z = left
  sonar(76, 50, -Math.PI / 4, 'HC-SR04 right (45°)', 38, 40, C.s6);

  // webcam on a post behind the centre sonar
  cyl(14, 3, M.blackPlastic, 66, TY + 1.5, 0, R);
  cyl(3.5, 46, M.blackPlastic, 66, TY + 24, 0, R, 'y', 16);
  const cam = new THREE.Mesh(new RoundedBoxGeometry(24, 26, 62, 4, 9), M.blackPlastic);
  cam.position.set(68, TY + 58, 0); cam.castShadow = true; R.add(cam);
  cyl(9, 4, M.steel, 80.5, TY + 58, 0, R, 'x', 40);
  cyl(7, 4.4, M.lens, 81, TY + 58, 0, R, 'x', 40);
  const glint = new THREE.Mesh(new THREE.SphereGeometry(1.8, 12, 8), new THREE.MeshBasicMaterial({ color: 0x9fc3ff }));
  glint.position.set(83, TY + 60.5, 2.5); R.add(glint);
  const led = new THREE.Mesh(new THREE.SphereGeometry(1.2, 12, 8), new THREE.MeshBasicMaterial({ color: 0x55e07a }));
  led.position.set(80.3, TY + 58, 20); R.add(led);
  for (let k = 0; k < 4; k++) box(0.8, 0.8, 0.8, M.black, 80.3, TY + 58, -18 - k * 2.2, R);
  ANCHORS['USB webcam + microphone (fixed)'] = new THREE.Vector3(80, TY + 70, 0);
  wires.push(wire([[56, TY + 50, 0], [40, TY + 30, 10], [PX + 85 + 6, PY + 9, PZ + 29]], C.usb, 1.4));

  // ---------------- Pi -> L298N and encoders through a hole in the top deck
  const hole = [-8, TY, -6];
  const sigs = [[9, C.gnd, 0], [11, C.sig, 1], [13, C.sig, 2], [15, C.sig, 3], [16, C.sig, 4], [33, C.pwm, -1], [35, C.pwm, 5]];
  sigs.forEach(([n, c, k], j) => {
    const p = pin(n);
    const tgt = [LX + 24 + Math.max(0, k) * 2.54, LY + 6, LZ + 38];
    if (n === 9) { tgt[0] = LX + 13; tgt[1] = LY + 9; tgt[2] = LZ + 37; }
    wires.push(wire([p, [p[0], p[1] + 8, p[2] - 3], [hole[0] + j, TY + 4, hole[2] - j], [hole[0] + j, TY - 10, hole[2] - j],
      [tgt[0], LY + 18, tgt[2] + 4], tgt], c, 0.6));
  });
  for (const [n, s] of [[29, 1], [31, -1]]) {
    const p = pin(n);
    wires.push(wire([p, [p[0], p[1] + 8, p[2] - 3], [hole[0] + 8, TY + 2, hole[2] + 4], [10, Y1 + 18, s * 30], [30, Y1 - 2, s * 40]],
      C.s4, 0.6));
  }
  ANCHORS['Jumper wires (colour-coded)'] = new THREE.Vector3(-20, TY + 22, -8);

  wires.forEach((w) => R.add(w));
  return R;
}
