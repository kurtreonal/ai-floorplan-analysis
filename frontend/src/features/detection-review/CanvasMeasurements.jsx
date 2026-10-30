import { Arrow, Group, Line, Text } from 'react-konva'
import { formatWallMeasure } from './wallMeasurements.js'

// Dimensions are derived from source geometry; never from the display grid.
export function CanvasMeasurements({ walls, scale, pixelsPerMeter, unit }) {
  const points = walls.filter(w => w.disposition !== 'rejected').flatMap(w => [w.start,w.end])
  if (!points.length) return null
  const left = Math.min(...points.map(p => p.x)), right = Math.max(...points.map(p => p.x))
  const top = Math.min(...points.map(p => p.y)), bottom = Math.max(...points.map(p => p.y))
  const offset = 28/scale, color = '#365267'
  const label = (x,y,value,rotation=0) => <Text x={x} y={y} text={formatWallMeasure(value,pixelsPerMeter,unit)} rotation={rotation}
    fontSize={11/scale} fill={color} stroke="white" strokeWidth={4/scale} fillAfterStrokeEnabled />
  return <Group listening={false} name="plan-dimensions">
    <Line points={[left,top,left,top-offset-6/scale]} stroke={color} strokeWidth={.7/scale} />
    <Line points={[right,top,right,top-offset-6/scale]} stroke={color} strokeWidth={.7/scale} />
    <Arrow points={[left,top-offset,right,top-offset]} stroke={color} fill={color} strokeWidth={1/scale} pointerLength={4/scale} pointerWidth={4/scale} pointerAtBeginning />
    {label((left+right)/2-35/scale,top-offset-14/scale,right-left)}
    <Line points={[right,top,right+offset+6/scale,top]} stroke={color} strokeWidth={.7/scale} />
    <Line points={[right,bottom,right+offset+6/scale,bottom]} stroke={color} strokeWidth={.7/scale} />
    <Arrow points={[right+offset,top,right+offset,bottom]} stroke={color} fill={color} strokeWidth={1/scale} pointerLength={4/scale} pointerWidth={4/scale} pointerAtBeginning />
    {label(right+offset+5/scale,(top+bottom)/2+35/scale,bottom-top,-90)}
  </Group>
}
