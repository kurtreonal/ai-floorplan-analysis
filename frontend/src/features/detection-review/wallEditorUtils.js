/**
 * Utility functions for 2D wall editing, snapping, constraints, and dimension labels.
 */

export function formatWallDimension(lengthPixels, pixelsPerMeter = null) {
  if (!Number.isFinite(lengthPixels) || lengthPixels <= 0) {
    return '0px (unscaled)'
  }
  if (Number.isFinite(pixelsPerMeter) && pixelsPerMeter > 0) {
    const meters = lengthPixels / pixelsPerMeter
    const feetTotal = meters * 3.28084
    let feet = Math.floor(feetTotal)
    let inches = Math.round((feetTotal - feet) * 12)
    if (inches === 12) {
      feet += 1
      inches = 0
    }
    return `${feet}'${inches}"`
  }
  return `${Math.round(lengthPixels)}px (unscaled)`
}

export function constrainPoint(start, current, enabled = false) {
  if (!enabled || !start || !current) return current
  const dx = Math.abs(current.x - start.x)
  const dy = Math.abs(current.y - start.y)
  if (dx >= dy) {
    return { x: current.x, y: start.y }
  }
  return { x: start.x, y: current.y }
}

export function findSnapPoint(point, walls = [], options = {}) {
  const threshold = options.threshold ?? 14
  const excludeWallId = options.excludeWallId ?? null
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    return { x: 0, y: 0, snapped: false }
  }

  let best = null
  let bestDist = threshold

  for (const wall of walls) {
    if (wall.disposition === 'rejected' || wall.id === excludeWallId) continue
    for (const target of [wall.start, wall.end]) {
      if (!target || !Number.isFinite(target.x) || !Number.isFinite(target.y)) continue
      const dist = Math.hypot(point.x - target.x, point.y - target.y)
      if (dist <= bestDist) {
        bestDist = dist
        best = { x: target.x, y: target.y }
      }
    }
  }

  if (best) {
    return { x: best.x, y: best.y, snapped: true }
  }
  return { x: point.x, y: point.y, snapped: false }
}

export function wallMidpoint(start, end) {
  return {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  }
}

export function wallTextRotation(start, end) {
  let angle = Math.atan2(end.y - start.y, end.x - start.x) * (180 / Math.PI)
  if (angle > 90) angle -= 180
  else if (angle < -90) angle += 180
  return angle
}
