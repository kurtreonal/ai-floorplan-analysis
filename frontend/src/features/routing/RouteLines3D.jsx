import { routeAppearance, routeWorldPositions } from './routeProjection.js'

export function RouteLines3D({ segments }) {
  return <group name="generated-routing">{segments.map((segment, index) => {
    const appearance = routeAppearance(segment.kind)
    const positions = routeWorldPositions(segment)
    const length = Math.hypot(...positions.slice(0, 3).map((value, axis) => value - positions[axis + 3]))
    return <line key={index} name={appearance.label}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[new Float32Array(positions), 3]} />
        {appearance.dashed && <bufferAttribute attach="attributes-lineDistance" args={[new Float32Array([0, length]), 1]} />}
      </bufferGeometry>
      {appearance.dashed
        ? <lineDashedMaterial color={appearance.color} dashSize={0.06} gapSize={0.04} />
        : <lineBasicMaterial color={appearance.color} />}
    </line>
  })}</group>
}
