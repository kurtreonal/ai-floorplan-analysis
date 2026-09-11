# 3D Electrical Fixtures & Asset Modeling Specification

This reference details standard procedural geometries, mounting heights (AFF), materials, and GLTF asset optimization guidelines for electrical fixtures in Three.js and React Three Fiber.

---

## 1. Standard Mounting Elevations (Above Finished Floor - AFF)

Per National Electrical Code (NEC) and Philippine Electrical Code (PEC) standard design conventions:

| Category | Device / Fixture Type | Standard Elevation (AFF) | 3D Mesh Dimensions (W x H x D meters) | Color / Material |
| :--- | :--- | :--- | :--- | :--- |
| **Receptacle** | Convenience Duplex Outlet | 0.30 m (12 in) | 0.07 x 0.11 x 0.02 | Matte White Plastic (`#f8fafc`), Metallic screws |
| **Receptacle** | Kitchen Countertop Outlet | 1.10 m (43 in) | 0.07 x 0.11 x 0.02 | GFCI Faceplate with status LED (`#10b981`) |
| **Receptacle** | Dedicated Appliance (AC/Range) | 1.80 m (71 in) | 0.10 x 0.10 x 0.04 | Industrial Slate Grey (`#475569`) |
| **Switch** | Single-Pole / 3-Way Toggle | 1.20 m (48 in) | 0.07 x 0.11 x 0.02 | Rocker Switch Faceplate (`#f8fafc`) |
| **Switch** | Dimmer / Smart Keypad | 1.20 m (48 in) | 0.08 x 0.12 x 0.02 | Backlit Glass/Polycarbonate (`#0f172a`) |
| **Lighting** | Recessed LED Downlight (Can) | Ceiling level (2.80 m) | Radius 0.08, Depth 0.02 | White Trim Ring + Emissive Lens (`#fef08a`, 1.5 intensity) |
| **Lighting** | Surface Troffer / Linear Light | Ceiling level (2.80 m) | 0.30 x 1.20 x 0.05 | Brushed Aluminum frame + Diffuser |
| **Distribution** | Main Electrical Panel (MDB/Loadcenter) | 1.50 m (to center) | 0.50 x 0.80 x 0.12 | Cold-rolled Steel Enclosure (`#334155`), Chrome latch |
| **Raceway** | EMT Conduit (Electrical Metallic Tubing) | Ceiling / Wall Runs | Diameter: 0.02 (3/4") or 0.025 (1") | Galvanized Steel (`#94a3b8`, metalness: 0.85, roughness: 0.25) |
| **Junction** | 4-Square Junction Box | Ceiling / In-Wall | 0.10 x 0.10 x 0.05 | Zinc-plated Steel Box (`#64748b`) |

---

## 2. Procedural 3D Mesh Generators (Three.js)

Procedural geometries avoid asset download latency and run instantly in WebGL:

```javascript
import * as THREE from 'three';

/**
 * Creates a procedural wall-mounted duplex receptacle mesh.
 */
export function createReceptacleMesh() {
  const group = new THREE.Group();

  // Faceplate
  const plateGeo = new THREE.BoxGeometry(0.07, 0.11, 0.015);
  const plateMat = new THREE.MeshStandardMaterial({
    color: 0xf1f5f9,
    roughness: 0.3,
    metalness: 0.05,
  });
  const plate = new THREE.Mesh(plateGeo, plateMat);
  plate.castShadow = true;
  group.add(plate);

  // Receptacle sockets (upper and lower plugs)
  const socketGeo = new THREE.CylinderGeometry(0.016, 0.016, 0.005, 16);
  const socketMat = new THREE.MeshStandardMaterial({
    color: 0x1e293b,
    roughness: 0.8,
  });

  const upperSocket = new THREE.Mesh(socketGeo, socketMat);
  upperSocket.rotation.x = Math.PI / 2;
  upperSocket.position.set(0, 0.025, 0.006);
  group.add(upperSocket);

  const lowerSocket = new THREE.Mesh(socketGeo, socketMat);
  lowerSocket.rotation.x = Math.PI / 2;
  lowerSocket.position.set(0, -0.025, 0.006);
  group.add(lowerSocket);

  return group;
}

/**
 * Creates an electrical distribution panel enclosure.
 */
export function createDistributionPanelMesh(width = 0.5, height = 0.8, depth = 0.12) {
  const group = new THREE.Group();

  // Outer cabinet
  const cabinetGeo = new THREE.BoxGeometry(width, height, depth);
  const cabinetMat = new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.4,
    metalness: 0.7,
  });
  const cabinet = new THREE.Mesh(cabinetGeo, cabinetMat);
  cabinet.castShadow = true;
  cabinet.receiveShadow = true;
  group.add(cabinet);

  // Door panel inset
  const doorGeo = new THREE.BoxGeometry(width * 0.92, height * 0.94, 0.005);
  const doorMat = new THREE.MeshStandardMaterial({
    color: 0x475569,
    roughness: 0.35,
    metalness: 0.75,
  });
  const door = new THREE.Mesh(doorGeo, doorMat);
  door.position.z = depth / 2 + 0.002;
  group.add(door);

  // Handle / Latch
  const handleGeo = new THREE.BoxGeometry(0.02, 0.08, 0.015);
  const handleMat = new THREE.MeshStandardMaterial({
    color: 0xcfd8dc,
    metalness: 0.9,
    roughness: 0.1,
  });
  const handle = new THREE.Mesh(handleGeo, handleMat);
  handle.position.set(width * 0.38, 0, depth / 2 + 0.01);
  group.add(handle);

  return group;
}
```

---

## 3. Lighting & Studio Environment

For optimal clarity in engineering visualizations:
- **Tone Mapping**: `THREE.ACESFilmicToneMapping` with exposure 1.1.
- **Directional Sunlight**: Angled at 45° (`position: [10, 20, 10]`) with soft shadow bias (`-0.0001`) and 2048x2048 shadow map.
- **Hemisphere Fill Light**: Sky `#f8fafc` (0.6), Ground `#334155` (0.3) to illuminate walls and recesses without pitch-black shadows.
- **Grid Plane**: Infinite subtle grid plane at `y = 0` with 1-meter major grid lines and 0.2-meter minor sub-divisions.
