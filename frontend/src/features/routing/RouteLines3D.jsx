import { useMemo } from 'react'
import { routeAppearance, routeWorldPositions } from './routeProjection.js'
import { ROUTE_DISPLAY_RADIUS } from './routeMesh.js'
import { displayWiringRuns, wiringRuns } from './wiringPresentation.js'
import { WiringTube3D } from './WiringTube3D.jsx'

export function RouteLines3D({ segments }) {
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
      .map(run=>({...run,spread:false}))),ROUTE_DISPLAY_RADIUS)
  },[segments])
  return <group name="generated-routing">{runs.map(run => {
    const segment=run.segment
    const appearance = routeAppearance(segment.kind)
    return <group key={run.id} name={appearance.label} userData={{ kind: segment.kind, displayRadiusOnly: true }}>
      <WiringTube3D run={run} radius={ROUTE_DISPLAY_RADIUS} color={appearance.color} xray />
    </group>
  })}</group>
}
