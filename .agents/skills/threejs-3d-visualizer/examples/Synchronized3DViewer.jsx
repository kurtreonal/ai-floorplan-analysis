import React, { useRef, useMemo, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, Center, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';

/**
 * Procedural Wall mesh component.
 */
function WallMesh({ wall }) {
  const { geometry, position, rotation } = useMemo(() => {
    const dx = wall.end.x - wall.start.x;
    const dz = wall.end.y - wall.start.y;
    const length = Math.hypot(dx, dz);
    const angle = Math.atan2(dz, dx);
    const height = wall.height_meters || 3.0;
    const thickness = wall.thickness_meters || 0.15;

    const geo = new THREE.BoxGeometry(length, height, thickness);
    const midX = (wall.start.x + wall.end.x) / 2;
    const midY = height / 2;
    const midZ = (wall.start.y + wall.end.y) / 2;

    return {
      geometry: geo,
      position: [midX, midY, midZ],
      rotation: [0, -angle, 0],
    };
  }, [wall]);

  return (
    <mesh
      geometry={geometry}
      position={position}
      rotation={rotation}
      castShadow
      receiveShadow
    >
      <meshStandardMaterial
        color="#cbd5e1"
        roughness={0.6}
        metalness={0.05}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/**
 * Procedural 3D Device glyph.
 */
function DeviceGlyph({ symbol }) {
  const elevation = symbol.elevation || (symbol.class_id === 1 ? 0.3 : 1.2);
  const color = symbol.status === 'needs_review' ? '#f59e0b' : '#3b82f6';

  return (
    <group position={[symbol.x, elevation, symbol.y]}>
      <mesh castShadow>
        <boxGeometry args={[0.08, 0.12, 0.03]} />
        <meshStandardMaterial color={color} roughness={0.3} metalness={0.2} />
      </mesh>
      {/* Glow halo for selection or review state */}
      {symbol.status === 'needs_review' && (
        <pointLight color="#f59e0b" intensity={0.5} distance={0.5} />
      )}
    </group>
  );
}

/**
 * 3D Conduit tube curve along ceiling and wall drops.
 */
function ConduitRoute({ route }) {
  const geometry = useMemo(() => {
    if (!route.points || route.points.length < 2) return null;
    const curvePoints = route.points.map(
      (p) => new THREE.Vector3(p.x, p.elevation || 2.7, p.y)
    );
    const path = new THREE.CatmullRomCurve3(curvePoints, false, 'catmullrom', 0.1);
    return new THREE.TubeGeometry(path, Math.max(16, route.points.length * 4), 0.015, 8, false);
  }, [route]);

  if (!geometry) return null;

  return (
    <mesh geometry={geometry} castShadow>
      <meshStandardMaterial color="#94a3b8" roughness={0.3} metalness={0.8} />
    </mesh>
  );
}

/**
 * Synchronized3DViewer consumes canonical geometry and renders a responsive,
 * interactive 3D scene with lighting, grid, and camera controls.
 */
export function Synchronized3DViewer({ canonicalGeometry, viewMode = 'perspective' }) {
  const controlsRef = useRef();

  return (
    <div style={{ width: '100%', height: '100%', background: '#0b0f19', position: 'relative' }}>
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.1 }}
      >
        <PerspectiveCamera makeDefault position={[12, 14, 16]} fov={45} />
        <OrbitControls
          ref={controlsRef}
          makeDefault
          enableDamping
          dampingFactor={0.05}
          maxPolarAngle={Math.PI / 2 - 0.02}
        />

        {/* Ambient & Directional Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[15, 25, 10]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-near={0.5}
          shadow-camera-far={50}
          shadow-camera-left={-15}
          shadow-camera-right={15}
          shadow-camera-top={15}
          shadow-camera-bottom={-15}
          shadow-bias={-0.0001}
        />

        {/* Subtle Engineering Grid Floor */}
        <Grid
          position={[0, -0.01, 0]}
          args={[30, 30]}
          cellSize={0.5}
          cellThickness={0.6}
          cellColor="#1e293b"
          sectionSize={2}
          sectionThickness={1.2}
          sectionColor="#334155"
          fadeDistance={25}
          fadeStrength={1}
        />

        <Center top>
          <group>
            {/* 3D Walls */}
            {canonicalGeometry?.walls?.map((wall) => (
              <WallMesh key={wall.id} wall={wall} />
            ))}

            {/* 3D Devices */}
            {canonicalGeometry?.symbols?.map((sym) => (
              <DeviceGlyph key={sym.id} symbol={sym} />
            ))}

            {/* 3D Conduits */}
            {canonicalGeometry?.routes?.map((route) => (
              <ConduitRoute key={route.id} route={route} />
            ))}
          </group>
        </Center>
      </Canvas>
    </div>
  );
}
