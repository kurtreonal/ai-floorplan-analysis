import { useEffect, useRef } from 'react'

// Copy properties, not detection identity, review approval or electrical bindings.
export function deviceClipboardSnapshot(symbol) {
  if (!symbol || symbol.disposition === 'rejected') return null
  return {
    center: { ...symbol.center },
    symbol_legend_id: symbol.symbol_legend_id ?? null,
    custom_unit_price: symbol.custom_unit_price ?? null,
    mounting_height_meters: symbol.mounting_height_meters ?? null,
    ...Object.fromEntries(['mounting_reference','mounting_height_source','terminal_offset_meters','gang_count_confirmed'].filter(k=>symbol[k]!=null).map(k=>[k,symbol[k]])),
  }
}

export function pastedDevice(snapshot, draft, plane, id, pointer = null) {
  if (!snapshot || draft.symbols.length >= 2048) return null
  const width = plane.width_pixels, height = plane.height_pixels
  if (![width, height, snapshot.center.x, snapshot.center.y].every(Number.isFinite)
    || width <= 0 || height <= 0) return null
  const step = Math.max(1, Math.min(width, height) * 0.025)
  // Search outward in source coordinates; repeated paste must not stack devices,
  // clamp them onto one border point or accidentally land on a wire terminal.
  const anchor = pointer && [pointer.x,pointer.y].every(Number.isFinite)
    && pointer.x>=0 && pointer.y>=0 && pointer.x<=width && pointer.y<=height ? pointer : snapshot.center
  for (let ring = pointer && anchor===pointer ? 0 : 1; ring <= 32; ring++) {
    for (const [dx, dy] of ring===0 ? [[0,0]] : [[ring, ring], [-ring, ring], [ring, -ring], [-ring, -ring], [ring, 0], [0, ring], [-ring, 0], [0, -ring]]) {
      const center = { x: Math.round(anchor.x + dx * step), y: Math.round(anchor.y + dy * step) }
      if (center.x < 0 || center.y < 0 || center.x > width || center.y > height) continue
      if (draft.symbols.some(s => s.disposition !== 'rejected'
        && Math.hypot(center.x - s.center.x, center.y - s.center.y) < step * 0.75)) continue
      if ((draft.wirings || []).some(w => w.disposition !== 'rejected' && w.points.length > 0
        && [w.points[0], w.points.at(-1)].some(p => Math.hypot(center.x - p.x, center.y - p.y) <= 2))) continue
      return { ...snapshot, id, center, disposition: 'added' }
    }
  }
  return null
}

export function useDeviceClipboard({ sourceKey, draft, selected, plane, disabled, onPaste }) {
  const clipboard = useRef(null)
  useEffect(() => {
    function shortcut(event) {
      if (event.defaultPrevented || event.repeat || event.altKey
        || (event.type === 'keydown' && !(event.ctrlKey || event.metaKey))
        || event.target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return
      const key = event.type === 'copy' ? 'c' : event.type === 'paste' ? 'v' : event.key.toLowerCase()
      if (key === 'c' && window.getSelection()?.toString()) return
      if (key === 'c' && selected?.kind === 'symbol' && draft && !disabled) {
        const snapshot = deviceClipboardSnapshot(draft.symbols.find(s => s.id === selected.id))
        if (!snapshot) return
        clipboard.current = { sourceKey, snapshot }
        event.preventDefault()
      } else if (key === 'v' && clipboard.current?.sourceKey === sourceKey && draft && plane && !disabled) {
        event.preventDefault()
        onPaste(clipboard.current.snapshot)
      }
    }
    window.addEventListener('keydown', shortcut)
    window.addEventListener('copy', shortcut)
    window.addEventListener('paste', shortcut)
    return () => {
      window.removeEventListener('keydown', shortcut)
      window.removeEventListener('copy', shortcut)
      window.removeEventListener('paste', shortcut)
    }
  }, [sourceKey, draft, selected, plane, disabled, onPaste])
}
