// Dimensions use the room's source-coordinate outline, independent of zoom.
export function roomMeasurements(boundary,pixelsPerMeter) {
  if(!Array.isArray(boundary) || boundary.length<3 || boundary.some(p=>!Number.isFinite(p.x) || !Number.isFinite(p.y)))return null
  const points=boundary.length>3 && boundary[0].x===boundary.at(-1).x && boundary[0].y===boundary.at(-1).y?boundary.slice(0,-1):boundary
  const turn=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
  const between=(a,b,p)=>p.x>=Math.min(a.x,b.x)-1e-8 && p.x<=Math.max(a.x,b.x)+1e-8 && p.y>=Math.min(a.y,b.y)-1e-8 && p.y<=Math.max(a.y,b.y)+1e-8
  for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
    if(j===i+1 || i===0 && j===points.length-1)continue
    const a=points[i],b=points[(i+1)%points.length],c=points[j],d=points[(j+1)%points.length]
    const ac=turn(a,b,c),ad=turn(a,b,d),ca=turn(c,d,a),cb=turn(c,d,b)
    if(ac*ad<0 && ca*cb<0 || Math.abs(ac)<1e-8 && between(a,b,c) || Math.abs(ad)<1e-8 && between(a,b,d) || Math.abs(ca)<1e-8 && between(c,d,a) || Math.abs(cb)<1e-8 && between(c,d,b))return null
  }
  let crossSum=0,cx=0,cy=0
  const edges=points.map((a,i)=>{const b=points[(i+1)%points.length],cross=a.x*b.y-b.x*a.y;crossSum+=cross;cx+=(a.x+b.x)*cross;cy+=(a.y+b.y)*cross;return Math.hypot(b.x-a.x,b.y-a.y)})
  const area=Math.abs(crossSum)/2
  if(area<1e-8 || edges.some(length=>length<1e-8))return null
  const scaled=Number.isFinite(pixelsPerMeter) && pixelsPerMeter>0,factor=scaled?pixelsPerMeter:1
  const rectangular=points.length===4 && points.every((a,i)=>{const b=points[(i+1)%4],c=points[(i+2)%4];return Math.abs((b.x-a.x)*(c.x-b.x)+(b.y-a.y)*(c.y-b.y))<=edges[i]*edges[(i+1)%4]*1e-5})
  return {scaled,area:area/factor**2,perimeter:edges.reduce((sum,n)=>sum+n,0)/factor,edges:edges.map(n=>n/factor),
    center:{x:cx/(3*crossSum),y:cy/(3*crossSum)},rectangular,
    width:(rectangular?edges[0]:Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x)))/factor,
    depth:(rectangular?edges[1]:Math.max(...points.map(p=>p.y))-Math.min(...points.map(p=>p.y)))/factor}
}

export function roomMeasurementLabels(measurement,unit='m') {
  if(!measurement)return {area:'Check room outline',dimensions:'',perimeter:''}
  if(!measurement.scaled)return {area:'Set plan measurements to show area',dimensions:'',perimeter:''}
  const factor=unit==='ft'?3.280839895:{m:1,cm:100,mm:1000}[unit] || 1
  const format=n=>new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(n)
  return {area:`${format(measurement.area*(unit==='ft'?factor**2:1))} ${unit==='ft'?'ft²':'m²'}`,
    dimensions:`${format(measurement.width*factor)} × ${format(measurement.depth*factor)} ${unit}`,
    perimeter:`${format(measurement.perimeter*factor)} ${unit}`}
}
