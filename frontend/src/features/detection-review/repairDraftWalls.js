const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y })
const dot = (a, b) => a.x * b.x + a.y * b.y
const cross = (a, b) => a.x * b.y - a.y * b.x
const length = (a) => Math.hypot(a.x, a.y)
const stablePoint = (p) => ({ x: Math.round(p.x * 1e6) / 1e6, y: Math.round(p.y * 1e6) / 1e6 })
const active = (wall) => wall.disposition !== 'rejected' && [wall.start?.x, wall.start?.y, wall.end?.x, wall.end?.y].every(Number.isFinite)
  && length(sub(wall.end, wall.start)) > 0.001

// Source-pixel, undoable repair. Never bridge collinear gaps (possible doors),
// discard records, or extrapolate across a room. Rejected duplicates are retained.
export function repairDraftWalls(input, width, height, options = {}) {
  const maxGap = options.maxGap ?? Math.max(4, Math.min(24, Math.max(width, height) * 0.015))
  const lineTolerance = options.lineTolerance ?? 2
  if (![width, height, maxGap, lineTolerance].every(Number.isFinite) || width <= 0 || height <= 0 || maxGap < 0 || lineTolerance < 0) throw new Error('Invalid wall repair bounds.')
  const walls = structuredClone(input)
  let merged = 0, joined = 0
  const inside = (p) => p.x >= 0 && p.y >= 0 && p.x <= width && p.y <= height
  function mergeOverlaps() {
    let changed = false
    for (let i = 0; i < walls.length; i++) {
      const a = walls[i]
      if (!active(a)) continue
      for (let j = i + 1; j < walls.length; j++) {
        const b = walls[j]
        if (!active(b)) continue
        const av = sub(a.end, a.start), bv = sub(b.end, b.start), al = length(av), bl = length(bv)
        if (Math.abs(cross(av, bv)) / (al * bl) > Math.sin(Math.PI / 180)) continue
        if ([b.start, b.end].some((p) => Math.abs(cross(av, sub(p, a.start))) / al > lineTolerance)) continue
        const t0 = dot(sub(b.start, a.start), av) / (al * al), t1 = dot(sub(b.end, a.start), av) / (al * al)
        // Require actual overlap/touch, not merely proximity across a doorway.
        if (Math.min(t0, t1) > 1 + 1e-9 || Math.max(t0, t1) < -1e-9) continue
        const start = { x: a.start.x + av.x * Math.min(0, t0, t1), y: a.start.y + av.y * Math.min(0, t0, t1) }
        const end = { x: a.start.x + av.x * Math.max(1, t0, t1), y: a.start.y + av.y * Math.max(1, t0, t1) }
        if (!inside(start) || !inside(end)) continue
        a.start = stablePoint(start); a.end = stablePoint(end)
        b.disposition = 'rejected'
        merged++; changed = true
      }
    }
    return changed
  }
  // Bound convergence by record count; no unbounded geometric optimization.
  for (let pass = 0; pass < walls.length && mergeOverlaps(); pass++) { /* merge chains */ }
  const baseline = structuredClone(walls)
  for (const a of walls) {
    if (!active(a)) continue
    const original = baseline.find((wall) => wall.id === a.id)
    const av = sub(original.end, original.start), al = length(av)
    for (const endpoint of ['start', 'end']) {
      let best = null
      for (const b of baseline) {
        if (!active(b) || b.id === a.id) continue
        const bv = sub(b.end, b.start), bl = length(bv), denominator = cross(av, bv)
        if (Math.abs(denominator) / (al * bl) < 0.25) continue
        const offset = sub(b.start, original.start)
        const t = cross(offset, bv) / denominator, u = cross(offset, av) / denominator
        // Only meet an existing segment or a small extension of its endpoint.
        if (u < -maxGap / bl || u > 1 + maxGap / bl) continue
        const point = stablePoint({ x: original.start.x + t * av.x, y: original.start.y + t * av.y })
        const distance = length(sub(point, original[endpoint]))
        if (!inside(point) || distance > maxGap) continue
        if (distance <= 1e-6) { best = null; break }
        // Never collapse/reverse a short wall or shorten most of it.
        if ((endpoint === 'start' && t > 0.25) || (endpoint === 'end' && t < 0.75)) continue
        if (!best || distance < best.distance) best = { point, distance }
      }
      if (best) { a[endpoint] = best.point; joined++ }
    }
  }
  for (let pass = 0; pass < walls.length && mergeOverlaps(); pass++) { /* final overlap cleanup */ }
  return { walls, merged, joined, maxGap }
}
