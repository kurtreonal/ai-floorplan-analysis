---
name: threejs-asset-studio
description: >-
  Comprehensive guide and runbook for creating, optimizing, and manipulating interactive 3D electrical
  assets in Three.js and React Three Fiber. Use when implementing procedural 3D electrical fixtures,
  GLTF model loading, PBR material systems, 3D raycasting and selection gizmos (TransformControls),
  3D wall snapping, InstancedMesh batching, and lighting/shadow optimization.
---

# 3D Asset Studio & Interactive Graphics (Three.js / React Three Fiber)

This skill provides step-by-step guidance for developing, optimizing, and interacting with 3D electrical assets, fixtures, raceways, and distribution equipment in VED Electrical Services.

---

## 1. Procedural Generation vs. GLTF Asset Loading

### When to use Procedural Geometries:
- High-frequency repetitive items (convenience duplex receptacles, toggle wall switches, 4-square junction boxes, circular LED downlights).
- Instantly rendered without network payload or async loading delay.
- Infinitely scalable parametric dimensions (e.g., custom panel cabinet widths and depths).

### When to use GLTF/GLB Models:
- Complex industrial equipment (large distribution switchboards, dry-type transformers, motor control centers).
- Must be pre-optimized: Draco compressed, merged draw calls, single shared 1024x1024 PBR texture atlas, under 250 KB per model.

---

## 2. Realistic PBR Electrical Materials

Engineering clarity requires clean, distinct PBR materials that respond naturally to environment lighting:

```javascript
import * as THREE from 'three';

export const ELECTRICAL_MATERIALS = {
  // Faceplates and plastic trim
  whitePlastic: new THREE.MeshStandardMaterial({
    color: 0xf8fafc,
    roughness: 0.35,
    metalness: 0.05,
  }),
  // Electrical Metallic Tubing (EMT) Conduit & Fittings
  emtConduit: new THREE.MeshStandardMaterial({
    color: 0x94a3b8,
    roughness: 0.25,
    metalness: 0.85,
  }),
  // Cold-rolled Steel Panel Enclosure
  panelEnclosure: new THREE.MeshStandardMaterial({
    color: 0x334155,
    roughness: 0.4,
    metalness: 0.7,
  }),
  // Emissive LED Fixture Lens (Active Circuit)
  luminaireLensOn: new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xfef08a,
    emissiveIntensity: 1.8,
    roughness: 0.2,
  }),
  // Emissive LED Fixture Lens (Unpowered / Switched Off)
  luminaireLensOff: new THREE.MeshStandardMaterial({
    color: 0xe2e8f0,
    roughness: 0.5,
    metalness: 0.1,
  }),
};
```

---

## 3. Interactive 3D Raycasting & Selection Gizmos

Allow users to select, move, and rotate electrical devices directly in the 3D viewport using `@react-three/drei` `TransformControls`:

```jsx
import React, { useRef } from 'react';
import { TransformControls } from '@react-three/drei';

export function EditableDevice({ symbol, isSelected, onTransformEnd }) {
  const meshRef = useRef();

  return (
    <>
      <mesh
        ref={meshRef}
        position={[symbol.x, symbol.elevation || 0.3, symbol.y]}
        castShadow
      >
        <boxGeometry args={[0.08, 0.12, 0.03]} />
        <meshStandardMaterial color={isSelected ? '#3b82f6' : '#64748b'} />
      </mesh>

      {isSelected && (
        <TransformControls
          object={meshRef}
          mode="translate"
          translationSnap={0.05} // Snap translation to 5cm increments
          onMouseUp={() => {
            if (meshRef.current && onTransformEnd) {
              const pos = meshRef.current.position;
              onTransformEnd(symbol.id, { x: pos.x, y: pos.z, elevation: pos.y });
            }
          }}
        />
      )}
    </>
  );
}
```

---

## 4. 3D Wall Surface Snapping

When a device is moved in 3D, snap it directly to the nearest wall surface and align its rotation normal to the wall face:

```javascript
/**
 * Projects a 3D point onto the nearest wall segment and computes normal rotation.
 */
export function snapTo3DWall(point, walls, wallThickness = 0.15) {
  let closest = null;
  let minDistance = 0.3; // 30cm threshold in 3D world meters

  for (const wall of walls) {
    const dx = wall.end.x - wall.start.x;
    const dz = wall.end.y - wall.start.y;
    const lenSq = dx * dx + dz * dz;
    if (lenSq === 0) continue;

    const t = Math.max(0, Math.min(1, ((point.x - wall.start.x) * dx + (point.z - wall.start.y) * dz) / lenSq));
    const projX = wall.start.x + t * dx;
    const projZ = wall.start.y + t * dz;

    const dist = Math.hypot(point.x - projX, point.z - projZ);
    if (dist < minDistance) {
      minDistance = dist;
      // Normal vector perpendicular to wall
      const wallAngle = Math.atan2(dz, dx);
      const normalAngle = wallAngle + Math.PI / 2;

      // Position device slightly proud of wall surface
      const offset = (wall.thickness_meters || wallThickness) / 2 + 0.01;
      closest = {
        position: {
          x: projX + Math.cos(normalAngle) * offset,
          y: point.y,
          z: projZ + Math.sin(normalAngle) * offset,
        },
        rotation: [0, -wallAngle, 0],
      };
    }
  }

  return closest;
}
```

---

## 5. Performance Batching: InstancedMesh for Repetitive Devices

For large commercial plans with hundreds of identical outlets or light fixtures, batch geometries into a single draw call with `THREE.InstancedMesh`:

```javascript
export function createInstancedDeviceCluster(symbols, geometry, material) {
  const count = symbols.length;
  const instancedMesh = new THREE.InstancedMesh(geometry, material, count);
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const rotation = new THREE.Quaternion();
  const scale = new THREE.Vector3(1, 1, 1);

  symbols.forEach((sym, index) => {
    position.set(sym.x, sym.elevation || 0.3, sym.y);
    rotation.setFromAxisAngle(new THREE.Vector3(0, 1, 0), sym.rotation || 0);
    matrix.compose(position, rotation, scale);
    instancedMesh.setMatrixAt(index, matrix);
  });

  instancedMesh.instanceMatrix.needsUpdate = true;
  instancedMesh.castShadow = true;
  return instancedMesh;
}
```
