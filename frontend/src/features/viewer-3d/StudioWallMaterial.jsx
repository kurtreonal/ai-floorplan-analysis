import { DoubleSide } from 'three'

export function StudioWallMaterial({ mode = 'full', selected = false }) {
  return <meshStandardMaterial color={selected ? '#e87748' : '#f2eee5'} roughness={.83} metalness={0}
    side={DoubleSide}
    transparent={mode==='xray'} opacity={mode==='xray' ? .16 : 1} depthWrite={mode!=='xray'} />
}
