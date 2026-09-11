---
name: threejs-3d-visualizer
description: >-
  Comprehensive guide and runbook for Three.js and React Three Fiber (R3F) 3D floor plan
  visualization, architectural mesh generation, and interactive 3D electrical assets. Use when
  rendering 3D walls, room slabs, openings, electrical devices, conduit routing, camera controls
  (Orbit, Pan, Top View, Perspective), lighting, WebGL performance optimization, and 2D-to-3D sync.
---

# Interactive 3D Visualization (Three.js & React Three Fiber)

This skill provides architectural guidance, math routines, and design guidelines for building high-performance 3D electrical layout viewers in VED Electrical Services using `Three.js` and `@react-three/fiber`.

---

## 1. Core Principles & Technology Constraints

1. **Geometric Accuracy Before Aesthetics**: Geometric fidelity (wall height, thickness, true floor scale, device elevation, conduit runs) must precede decorative furniture, heavy shaders, or complex materials.
2. **JavaScript Only (No TypeScript)**: Source files must be `.js` / `.jsx`. No `.ts`, `.tsx`, or TypeScript-only syntax.
3. **Single Canonical Geometry Source**: The 3D viewer strictly consumes the shared canonical geometry model. Never maintain an independent 3D data structure or parse raw AI/YOLO/VLM detections inside Three.js components.
4. **Synchronized 2D/3D State**: When a symbol or wall is moved or edited in 2D, the 3D scene updates reactively from the canonical geometry store.

---

## 2. 2D-to-3D Coordinate & Mesh Projection

In Three.js, the standard world coordinate system uses:
- **X**: Horizontal axis (matches 2D X in meters).
- **Y**: Vertical elevation axis (height off the ground).
- **Z**: Depth axis (matches 2D Y in meters).

### Wall Extrusion Pipeline

A 2D wall segment defined by `start = {x, y}` and `end = {x, y}`, `height`, and `thickness` is represented as an oriented box:

```javascript
import * as THREE from 'three';

export function createWallGeometry(wall) {
  const dx = wall.end.x - wall.start.x;
  const dz = wall.end.y - wall.start.y;
  const length = Math.hypot(dx, dz);
  const angle = Math.atan2(dz, dx);

  const geometry = new THREE.BoxGeometry(length, wall.height_meters || 3.0, wall.thickness_meters || 0.15);

  const midX = (wall.start.x + wall.end.x) / 2;
  const midY = (wall.height_meters || 3.0) / 2;
  const midZ = (wall.start.y + wall.end.y) / 2;

  return {
    geometry,
    position: [midX, midY, midZ],
    rotation: [0, -angle, 0],
  };
}
```

### Floor Slab Generation

For room boundaries defined by closed 2D polygons:

```javascript
export function createRoomFloorGeometry(roomPolygon) {
  const shape = new THREE.Shape();
  if (roomPolygon.length < 3) return null;

  shape.moveTo(roomPolygon[0].x, roomPolygon[0].y);
  for (let i = 1; i < roomPolygon.length; i++) {
    shape.lineTo(roomPolygon[i].x, roomPolygon[i].y);
  }
  shape.closePath();

  // Extrude slightly downwards (-0.05m) to avoid z-fighting with the ground plane
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: 0.05,
    bevelEnabled: false,
  });

  // Rotate shape from XY to XZ plane
  geometry.rotateX(Math.PI / 2);
  return geometry;
}
```

---

## 3. Electrical Device 3D Glyphs & Standard Elevations

Electrical symbols map to 3D device representations placed at specific standard elevations (above finished floor level, AFF):

| Device Type | Standard Elevation | 3D Visual Mesh | Highlight Color |
| :--- | :--- | :--- | :--- |
| Duplex Convenience Receptacle | 0.30 m AFF | Wall-mounted faceplate box | `#3b82f6` (Blue) |
| Countertop / Kitchen Receptacle | 1.10 m AFF | Wall-mounted faceplate box | `#0ea5e9` (Sky) |
| Wall Switch (Single / 3-Way) | 1.20 m AFF | Toggle plate with indicator | `#10b981` (Emerald) |
| Ceiling Light Fixture | Ceiling level (e.g. 2.80 m) | Circular luminaire with emissive lens | `#f59e0b` (Amber) |
| Electrical Distribution Panel | 1.50 m AFF | Vertical metal enclosure cabinet | `#64748b` (Slate) |

---

## 4. Ceiling & Wall Conduit Routing Visualization

Follow the project electrical routing model in 3D:
1. **Ceiling/Service Runs**: Conduits travel horizontally at ceiling level (`y = ceilingHeight - 0.1m`).
2. **Wall Drops & Rises**: Conduits route vertically inside/along the wall down to receptacle level (`y = 0.30m`) or switch level (`y = 1.20m`).
3. **Smooth Path Construction**:

```javascript
export function buildConduitTubeGeometry(routePoints, radius = 0.015) {
  const curvePoints = routePoints.map(p => new THREE.Vector3(p.x, p.elevation || p.y, p.z));
  const path = new THREE.CatmullRomCurve3(curvePoints, false, 'catmullrom', 0.1);
  return new THREE.TubeGeometry(path, Math.max(20, routePoints.length * 6), radius, 8, false);
}
```

---

## 5. Camera Controls & Viewport Presets

Required camera capabilities:
- **Perspective Orbit**: Free orbit around scene center using `@react-three/drei` `OrbitControls`.
- **Top / Plan View**: Camera positioned directly above (`x = centerX, y = 15, z = centerZ`) looking straight down (`lookAt(centerX, 0, centerZ)`) with orthographic projection or high focal length.
- **Walkthrough Mode**: First-person perspective at human eye level (`y = 1.65m`).
- **Smooth Transitions**: Use `camera.position.lerp()` or `@react-three/fiber` `useFrame` for seamless camera animation between view presets.

```jsx
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';

export function SceneCamera({ viewMode, bounds }) {
  const controlsRef = useRef();

  useEffect(() => {
    if (!controlsRef.current) return;
    if (viewMode === 'top') {
      controlsRef.current.reset();
      controlsRef.current.object.position.set(bounds.centerX, 15, bounds.centerZ);
      controlsRef.current.target.set(bounds.centerX, 0, bounds.centerZ);
    } else if (viewMode === 'perspective') {
      controlsRef.current.object.position.set(bounds.centerX + 8, 8, bounds.centerZ + 8);
      controlsRef.current.target.set(bounds.centerX, 0, bounds.centerZ);
    }
  }, [viewMode, bounds]);

  return <OrbitControls ref={controlsRef} makeDefault enableDamping dampingFactor={0.05} maxPolarAngle={Math.PI / 2 - 0.05} />;
}
```

---

## 6. Performance & WebGL Resource Management

- **InstancedMesh for Repetitive Symbols**: When scenes contain dozens of receptacles and lights, use `THREE.InstancedMesh` with a single shared geometry and material, setting individual transformation matrices with `instancedMesh.setMatrixAt(i, matrix)`.
- **Proper Resource Disposal**: Always dispose of geometries and materials on component unmount to prevent WebGL memory leaks:
  ```javascript
  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);
  ```
- **Pixel Ratio Capping**: Clamp device pixel ratio to 2 (`Math.min(window.devicePixelRatio, 2)`) to avoid GPU strain on high-DPI displays.
