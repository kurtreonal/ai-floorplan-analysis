import {useState} from 'react'
import {ImageOff} from 'lucide-react'
import {API_BASE_URL} from '../../api/auth.js'

export function AdminLegendPreview({id,aliases=[],revision=0}){
  const [index,setIndex]=useState(0)
  const ids=[id,...aliases.map(record=>record.id).filter(value=>value!==id)],missing=index>=ids.length
  return <span className="admin-legend-preview" title={missing?'No image added. Edit this legend to upload its symbol.':'2D symbol'}>{missing?<ImageOff size={16} aria-hidden="true"/>:<img key={ids[index]} src={`${API_BASE_URL}/api/symbol-legends/${ids[index]}/glyph.png?v=${revision}`} crossOrigin="use-credentials" alt="" loading="lazy" onError={()=>setIndex(value=>value+1)}/>}</span>
}
