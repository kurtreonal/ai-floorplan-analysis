import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'

// Only samples continuous frames (orbit/animation), excluding idle demand frames.
// Reduces raster cost, never hides engineering content.
export function StudioQuality() {
  const sample=useRef({seconds:0,frames:0,reduced:false})
  const {setDpr,gl}=useThree()
  useFrame((_,delta)=>{
    if(delta>.15 || delta<=0)return
    const stats=sample.current
    stats.frames++;stats.seconds+=delta
    if(stats.frames<90)return
    const fps=stats.frames/stats.seconds
    gl.domElement.setAttribute('data-studio-fps',fps.toFixed(1))
    if(fps<30 && !stats.reduced){stats.reduced=true;setDpr(1)}
    stats.frames=0;stats.seconds=0
  })
  return null
}
