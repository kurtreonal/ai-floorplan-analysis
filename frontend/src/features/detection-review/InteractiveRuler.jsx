import { Circle, Group, Line, Text } from 'react-konva'
import { Ruler, X } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'

const number = value => new Intl.NumberFormat(undefined, {maximumFractionDigits:2}).format(value)

export function RulerOverlay({points, lengthMeters, pixelsPerMeter, scale, width, height, onChange, disabled}) {
  const [a,b] = points
  const length = Math.hypot(b.x-a.x,b.y-a.y) || 1
  const u = {x:(b.x-a.x)/length,y:(b.y-a.y)/length}
  const n = {x:-u.y,y:u.x}
  const offset = 24/scale
  const at = (t,d=0) => ({x:a.x+(b.x-a.x)*t+n.x*d,y:a.y+(b.y-a.y)*t+n.y*d})
  const corners = [at(0),at(1),at(1,offset),at(0,offset)].flatMap(p=>[p.x,p.y])
  return <Group draggable={!disabled} onClick={event=>{event.cancelBubble=true}} onTap={event=>{event.cancelBubble=true}}
    onDragEnd={event=>{
      if(event.target!==event.currentTarget)return
      const dx=Math.max(-Math.min(a.x,b.x),Math.min(width-Math.max(a.x,b.x),event.target.x()))
      const dy=Math.max(-Math.min(a.y,b.y),Math.min(height-Math.max(a.y,b.y),event.target.y()))
      event.target.position({x:0,y:0})
      onChange(points.map(p=>({x:p.x+dx,y:p.y+dy})))
    }}>
    <Line points={corners} closed fill="rgba(255,122,69,0.18)" stroke="#ff7a45" strokeWidth={1.5/scale}/>
    {Array.from({length:31},(_,i)=>{
      const start=at(i/30), end=at(i/30,(i%5===0 ? 12:6)/scale)
      return <Line key={i} points={[start.x,start.y,end.x,end.y]} stroke="#9b3c1b" strokeWidth={1/scale} listening={false}/>
    })}
    <Text {...at(.5,29/scale)} text={`${number(pixelsPerMeter>0 ? length/pixelsPerMeter:Number(lengthMeters)||0)} m`} fontSize={12/scale}
      fill="#9b3c1b" offsetX={54/scale} listening={false}/>
    {points.map((p,index)=><Circle key={index} {...p} radius={8/scale} fill="#fff" stroke="#ff7a45" strokeWidth={2/scale}
      draggable={!disabled} onDragStart={event=>{event.cancelBubble=true}}
      onDragMove={event=>{
        event.cancelBubble=true
        const next={x:Math.max(0,Math.min(width,event.target.x())),y:Math.max(0,Math.min(height,event.target.y()))}
        event.target.position(next)
        onChange(points.map((value,i)=>i===index ? next:value))
      }} onDragEnd={event=>{event.cancelBubble=true}}/>)}
  </Group>
}

export function RulerControls({points, lengthMeters, onLengthChange, context={}, onApply, onClose, status, canSave}) {
  const pixelLength=Math.hypot(points[1].x-points[0].x,points[1].y-points[0].y)
  const valid=Number(lengthMeters)>0 && Number(lengthMeters)<=100000 && pixelLength>0
  const busy=status?.status==='saving'
  return <form className="studio-ruler-controls" aria-label="Image ruler" onSubmit={event=>{
    event.preventDefault()
    if(valid && !busy && canSave)onApply({start:points[0],end:points[1],length_meters:Number(lengthMeters)})
  }}>
    <header><strong><Ruler size={16} aria-hidden="true"/>Image ruler</strong><Button variant="ghost" size="icon" aria-label="Close ruler" onClick={onClose}><X size={16}/></Button></header>
    <p>Drag the ruler to move it. Drag either end to resize or rotate.</p>
    {context.pixels_per_meter>0 && <strong>Measured span: {number(pixelLength/context.pixels_per_meter)} m</strong>}
    <label>Known real-world length (m)<input autoFocus type="number" min="0.001" max="100000" step="any" required value={lengthMeters}
      disabled={busy} onChange={event=>onLengthChange(event.target.value)}/></label>
    <small>Place both ends on a labelled dimension, enter its actual length, then set the image scale once.</small>
    {context.source_width_mm>0 && <small>Original page: {number(context.source_width_mm/10)} × {number(context.source_height_mm/10)} cm. Source scale 1:{number(context.scale_denominator || 100)}.</small>}
    {context.multiple_scale_views && <small>Select one scaled plan view before calibrating. This sheet contains separate views.</small>}
    <Button type="submit" disabled={!valid || busy || !canSave}>{busy ? 'Applying…':'Set image scale'}</Button>
    {status?.message && <small role={status.status==='error' ? 'alert':'status'}>{status.message}</small>}
  </form>
}
