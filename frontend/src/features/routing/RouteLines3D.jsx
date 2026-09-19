import { routeWorldPositions } from './routeProjection.js'

export function RouteLines3D({ segments }) {
  return <group>{segments.map((segment, index) => <line key={index}>
    <bufferGeometry><bufferAttribute attach="attributes-position" args={[new Float32Array(routeWorldPositions(segment)), 3]} /></bufferGeometry>
    <lineBasicMaterial color={segment.kind === 'riser' ? '#9c36b5' : '#00897b'} depthTest={false} />
  </line>)}</group>
}
