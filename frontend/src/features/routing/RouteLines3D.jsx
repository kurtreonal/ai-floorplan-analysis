import { useMemo } from 'react'
import { routeAppearance, routeWorldPositions } from './routeProjection.js'
import { ROUTE_DISPLAY_RADIUS } from './routeMesh.js'
import { displayWiringRuns, wiringRuns } from './wiringPresentation.js'
import { WiringTube3D } from './WiringTube3D.jsx'

export function RouteLines3D({ segments, inspectUnderground = false }) {
  const runs=useMemo(()=>{
    const projected=segments.map(segment=>{
      const positions=routeWorldPositions(segment)
      return {...segment,start:positions.slice(0,3),end:positions.slice(3)}
    })
    // Route IDs group actual polylines; absent identities are not invented.
    const owners=new Map()
    projected.forEach(segment=>{
      const id=segment.routeId ?? segment.route_id ?? 'generated-collection'
      if(!owners.has(id)) owners.set(id,[])
      owners.get(id).push(segment)
    })
    return displayWiringRuns([...owners].flatMap(([id,items])=>wiringRuns(items,id,s=>s.kind)
      .map(run=>({...run,spread:run.segment.kind==='ceiling_service'}))),ROUTE_DISPLAY_RADIUS)
  },[segments])
  return <group name="generated-routing">{runs.map(run => {
    const segment=run.segment
    const appearance = routeAppearance(segment.kind)
    const source=run.sourcePoints || run.points, positions=source.flat()
    const distances=[0]
    source.slice(1).forEach((point,index)=>distances.push(distances.at(-1)+Math.hypot(...point.map((v,i)=>v-source[index][i]))))
    const xray = inspectUnderground && segment.kind.startsWith('underground')
    const inspection = xray ? { depthTest: false, depthWrite: false } : {}
    return <group key={run.id} name={appearance.label} userData={{ kind: segment.kind, displayRadiusOnly: true }}>
      <WiringTube3D run={run} radius={ROUTE_DISPLAY_RADIUS} color={appearance.color} xray={xray} />
      {appearance.dashed && <line name={`${appearance.label} inspection`} renderOrder={xray ? 11 : 1}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[new Float32Array(positions), 3]} />
        {appearance.dashed && <bufferAttribute attach="attributes-lineDistance" args={[new Float32Array(distances), 1]} />}
      </bufferGeometry>
      <lineDashedMaterial color={appearance.color} dashSize={0.06} gapSize={0.04} {...inspection} />
      </line>}
    </group>
  })}</group>
}
