// Screen-space intent only. Camera/world scale must not change click tolerance.
export const SELECTION_CLICK_PIXELS = 5
export function selectionGesture(threshold = SELECTION_CLICK_PIXELS) {
  const pointers = new Map()
  let moved = false, cancelled = true
  const id = event => event.pointerId ?? 0
  function move(event) {
    const start = pointers.get(id(event))
    if (start && Math.hypot(event.clientX-start.x,event.clientY-start.y) > threshold) moved = true
  }
  return {
    down(event) {
      if (!pointers.size) { moved = false; cancelled = false }
      else moved = true // Multi-touch is a camera gesture, never a device click.
      if (event.button != null && event.button !== 0 && event.pointerType !== 'touch') cancelled = true
      pointers.set(id(event),{x:event.clientX,y:event.clientY})
    },
    move,
    up(event, inside = true) {
      if (!pointers.has(id(event))) return
      move(event); pointers.delete(id(event))
      if (!inside) cancelled = true
    },
    cancel() { pointers.clear(); cancelled = true },
    lost(event) { if (pointers.has(id(event))) { pointers.clear(); cancelled = true } },
    canSelect(event) { return !pointers.size && !moved && !cancelled && (event?.delta ?? 0) <= threshold && (event?.button ?? 0) === 0 },
  }
}
