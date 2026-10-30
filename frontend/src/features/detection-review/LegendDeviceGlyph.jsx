import { useEffect, useState } from 'react'
import { Group, Rect, Image as KonvaImage } from 'react-konva'
import { API_BASE_URL } from '../../api/auth.js'
import { DeviceGlyph } from './DeviceGlyph.jsx'

const images = new Map()
function sourceGlyph(id) {
  if (!images.has(id)) images.set(id, fetch(`${API_BASE_URL}/api/symbol-legends/${id}/glyph.png`, { credentials: 'include', cache: 'no-cache' })
    .then(r => r.ok ? r.blob() : null).then(blob => blob && new Promise(resolve => {
      const image = new window.Image(), url = URL.createObjectURL(blob)
      image.onload = () => { URL.revokeObjectURL(url); resolve(image) }
      image.onerror = () => { URL.revokeObjectURL(url); resolve(null) }; image.src = url
    })).catch(() => null).then(image=>{if(!image)images.delete(id);return image}))
  return images.get(id)
}
export function LegendDeviceGlyph({ legendId, scale, ...props }) {
  const [loaded, setLoaded] = useState(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => { const update = event => { if (event.detail === legendId) { images.delete(legendId); setRevision(value => value + 1) } }; window.addEventListener('ved:legend-artwork-changed', update); return () => window.removeEventListener('ved:legend-artwork-changed', update) }, [legendId])
  useEffect(() => { let active = true; if (legendId) sourceGlyph(legendId).then(image => { if (active) setLoaded({ id: legendId, image }) }); return () => { active = false } }, [legendId, revision])
  const image = loaded && loaded.id === legendId ? loaded.image : null
  if (!image) return <DeviceGlyph {...props} scale={scale}/>
  const factor = 30 / Math.max(image.width, image.height) / scale
  const width=image.width*factor,height=image.height*factor,padding=2/scale
  return <Group listening={false}>
    <Rect x={-width/2-padding} y={-height/2-padding} width={width+2*padding} height={height+2*padding}
      cornerRadius={2/scale} fill="#fffdf8e6" stroke={props.color || '#af5837'} strokeWidth={1.2/scale}/>
    <KonvaImage image={image} x={-width/2} y={-height/2}
      width={width} height={height} listening={false}/>
  </Group>
}
