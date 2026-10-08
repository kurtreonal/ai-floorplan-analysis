// Source pixels only: viewport pan/zoom is inverted by the Konva caller.
export function drawingRegionFromPoints(first, second, width, height) {
  if (![first?.x, first?.y, second?.x, second?.y, width, height].every(Number.isFinite)
    || !Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) return null
  const x = Math.max(0, Math.min(width, Math.floor(Math.min(first.x, second.x))))
  const y = Math.max(0, Math.min(height, Math.floor(Math.min(first.y, second.y))))
  const right = Math.max(0, Math.min(width, Math.ceil(Math.max(first.x, second.x))))
  const bottom = Math.max(0, Math.min(height, Math.ceil(Math.max(first.y, second.y))))
  if (right <= x || bottom <= y) return null
  return { x, y, width: right - x, height: bottom - y }
}
