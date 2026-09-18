import * as THREE from "three";

/**
 * A procedural stand-in for `/samples/car.glb`: an extruded side profile on four
 * wheels, roughly 4.5 × 1.9 × 1.4 m (length × width × height), with the part names the
 * analysis pipeline looks for. Built in metres, length along +x, nose toward +x.
 */
export function placeholderCar(): THREE.Group {
  const car = new THREE.Group();
  car.name = "PlaceholderCar";

  const paint = new THREE.MeshStandardMaterial({ name: "Paint", color: 0x7a1f26, roughness: 0.32, metalness: 0.55 });
  const glass = new THREE.MeshStandardMaterial({ name: "Glass", color: 0x10161f, roughness: 0.08, metalness: 0.7 });
  const rubber = new THREE.MeshStandardMaterial({ name: "Rubber", color: 0x111111, roughness: 0.92, metalness: 0 });
  const alloy = new THREE.MeshStandardMaterial({ name: "Alloy", color: 0xb9b6ae, roughness: 0.35, metalness: 0.85 });
  const lamp = new THREE.MeshStandardMaterial({
    name: "Lamp",
    color: 0xfff1d6,
    emissive: 0xffd9a0,
    emissiveIntensity: 1.4,
    roughness: 0.2,
  });

  // Side profile in the x-y plane (x = length, y = height), extruded across z.
  const profile = new THREE.Shape();
  profile.moveTo(-2.2, 0.32);
  profile.lineTo(2.2, 0.32);
  profile.lineTo(2.26, 0.58);
  profile.lineTo(2.1, 0.8);
  profile.lineTo(0.72, 0.9);
  profile.lineTo(0.1, 1.34);
  profile.lineTo(-0.95, 1.38);
  profile.lineTo(-1.62, 1.02);
  profile.lineTo(-2.14, 0.96);
  profile.lineTo(-2.26, 0.62);
  profile.closePath();

  const width = 1.72;
  const bodyGeometry = new THREE.ExtrudeGeometry(profile, {
    depth: width,
    bevelEnabled: true,
    bevelThickness: 0.06,
    bevelSize: 0.06,
    bevelSegments: 4,
    curveSegments: 6,
  });
  bodyGeometry.translate(0, 0, -width / 2);
  const body = new THREE.Mesh(bodyGeometry, paint);
  body.name = "Body";
  car.add(body);

  // Windshield sits just proud of the sloped panel between (0.72, 0.9) and (0.1, 1.34).
  const wsFrom = new THREE.Vector2(0.72, 0.9);
  const wsTo = new THREE.Vector2(0.1, 1.34);
  const wsDir = wsTo.clone().sub(wsFrom);
  const wsLen = wsDir.length();
  const wsNormal = new THREE.Vector2(wsDir.y, -wsDir.x).normalize();
  const wsCentre = wsFrom.clone().add(wsTo).multiplyScalar(0.5).addScaledVector(wsNormal, 0.075);
  const windshield = new THREE.Mesh(new THREE.BoxGeometry(wsLen * 0.9, 0.02, width * 0.86), glass);
  windshield.name = "Windshield";
  windshield.position.set(wsCentre.x, wsCentre.y, 0);
  windshield.rotation.z = Math.atan2(wsDir.y, wsDir.x);
  car.add(windshield);

  // Rear window.
  const rwFrom = new THREE.Vector2(-0.95, 1.38);
  const rwTo = new THREE.Vector2(-1.62, 1.02);
  const rwDir = rwTo.clone().sub(rwFrom);
  const rwNormal = new THREE.Vector2(-rwDir.y, rwDir.x).normalize();
  const rwCentre = rwFrom.clone().add(rwTo).multiplyScalar(0.5).addScaledVector(rwNormal, 0.075);
  const rearWindow = new THREE.Mesh(new THREE.BoxGeometry(rwDir.length() * 0.85, 0.02, width * 0.8), glass);
  rearWindow.name = "RearWindow";
  rearWindow.position.set(rwCentre.x, rwCentre.y, 0);
  rearWindow.rotation.z = Math.atan2(rwDir.y, rwDir.x);
  car.add(rearWindow);

  // Wheels: cylinder axis along z.
  const tyreGeometry = new THREE.CylinderGeometry(0.34, 0.34, 0.24, 28);
  tyreGeometry.rotateX(Math.PI / 2);
  const rimGeometry = new THREE.CylinderGeometry(0.21, 0.21, 0.26, 20);
  rimGeometry.rotateX(Math.PI / 2);
  const wheels: Array<[string, number, number]> = [
    ["Wheel_FL", 1.42, 0.86],
    ["Wheel_FR", 1.42, -0.86],
    ["Wheel_RL", -1.42, 0.86],
    ["Wheel_RR", -1.42, -0.86],
  ];
  for (const [name, x, z] of wheels) {
    const tyre = new THREE.Mesh(tyreGeometry, rubber);
    tyre.name = name;
    tyre.position.set(x, 0.34, z);
    const rim = new THREE.Mesh(rimGeometry, alloy);
    tyre.add(rim);
    car.add(tyre);
  }

  // Headlights on the nose.
  const lampGeometry = new THREE.BoxGeometry(0.06, 0.14, 0.32);
  for (const [name, z] of [
    ["Headlight_L", 0.58],
    ["Headlight_R", -0.58],
  ] as const) {
    const light = new THREE.Mesh(lampGeometry, lamp);
    light.name = name;
    light.position.set(2.24, 0.7, z);
    car.add(light);
  }

  return car;
}
