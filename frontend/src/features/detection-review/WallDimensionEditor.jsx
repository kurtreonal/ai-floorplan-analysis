import { useState } from 'react'
import { formatWallMeasure } from './wallMeasurements.js'
import { resizeWall, wallLength } from './wallDrawing.js'

export function WallDimensionEditor({wall,pixelsPerMeter,onUpdate,onError}) {
  const [length,setLength]=useState('')
  const [unit,setUnit]=useState('m')
  const scaled=Number.isFinite(pixelsPerMeter)&&pixelsPerMeter>0
  return <fieldset><legend>Physical wall dimensions</legend>
    <p>Centerline: {formatWallMeasure(wallLength(wall),pixelsPerMeter,unit)}. Start stays anchored; joined corners move together.</p>
    <label>Length unit<select value={scaled?unit:'px'} onChange={e=>setUnit(e.target.value)} disabled={!scaled}>
      {scaled ? [['cm','Centimeters'],['ft','Feet (decimal)'],['m','Meters'],['mm','Millimeters']].map(([id,name])=><option value={id} key={id}>{name}</option>) : <option value="px">Source pixels (unscaled)</option>}
    </select></label>
    <form onSubmit={e=>{e.preventDefault();try {
      const factor={m:1,cm:.01,mm:.001,ft:.3048}[unit]
      onUpdate(resizeWall(wall,Number(length)*(scaled?pixelsPerMeter*factor:1)))
    } catch(error){onError?.(error.message)}}}>
      <label>Exact centerline length<input type="number" min="0.001" step="any" value={length} onChange={e=>setLength(e.target.value)} required /></label>
      <button className="btn btn-outline-primary" type="submit">Apply length</button>
    </form>
    <label>{scaled?'Wall thickness (m)':'Wall thickness (source px)'}<input type="number" min="0.001" max="1000" step="any"
      value={scaled ? wall.thickness_meters??(wall.estimated_thickness_pixels??12)/pixelsPerMeter : wall.estimated_thickness_pixels??12}
      onChange={e=>{const value=Number(e.target.value);if(value>0&&value<=1000)onUpdate({...wall,...(scaled?{thickness_meters:value,estimated_thickness_pixels:value*pixelsPerMeter}:{estimated_thickness_pixels:value})})}} /></label>
    <label>Wall height (m, optional)<input type="number" min="0.001" max="1000" step="any" value={wall.height_meters??''}
      onChange={e=>{const value=e.target.value===''?null:Number(e.target.value);if(value===null||value>0&&value<=1000)onUpdate({...wall,height_meters:value})}} /></label>
    {!scaled&&<p>No confirmed page scale. Length/thickness remain source pixels; entering a height does not calibrate the plan.</p>}
  </fieldset>
}
