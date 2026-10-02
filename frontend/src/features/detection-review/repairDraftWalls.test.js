import { describe, expect, it } from 'vitest'
import { repairDraftWalls } from './repairDraftWalls.js'
import { findSnapPoint } from './wallEditorUtils.js'
const wall = (id, sx, sy, ex, ey) => ({ id, disposition: 'accepted', start: { x: sx, y: sy }, end: { x: ex, y: ey } })
const repair = (walls) => repairDraftWalls(walls, 400, 400, { maxGap: 10 })
describe('bounded, reversible wall repair', () => {
  it('unions overlapping/reversed duplicates and retains tombstones and originals', () => {
    const input = [wall('a', 10, 20, 80, 20), wall('b', 110, 21, 50, 21), wall('c', 30, 20, 60, 20)]
    const before = structuredClone(input), result = repair(input)
    expect(result.merged).toBe(2)
    expect(result.walls[0].end).toEqual({ x: 110, y: 20 })
    expect(result.walls.slice(1).map((w) => w.disposition)).toEqual(['rejected', 'rejected'])
    expect(input).toEqual(before)
    expect(repair(result.walls).walls).toEqual(result.walls)
  })
  it('extends T junctions and nearby corners to intersections, not arbitrary nearby points', () => {
    const input = [wall('a', 10, 10, 100, 10), wall('b', 50, 18, 50, 80), wall('c', 108, 15, 108, 70)]
    const result = repair(input)
    expect(result.walls[0].end).toEqual({ x: 108, y: 10 })
    expect(result.walls[1].start).toEqual({ x: 50, y: 10 })
    expect(result.walls[2].start).toEqual({ x: 108, y: 10 })
    expect(repair(result.walls).walls).toEqual(result.walls)
  })
  it('trims bounded overshoot, keeps connected ends fixed, preserves door gaps and distant/parallel walls', () => {
    const result = repair([wall('a', 10, 10, 108, 10), wall('b', 100, 10, 100, 80)])
    expect(result.walls[0].end).toEqual({ x: 100, y: 10 })
    const input = [wall('a', 10, 10, 50, 10), wall('b', 55, 10, 90, 10), wall('c', 10, 30, 90, 30), wall('d', 180, 15, 180, 100)]
    expect(repair(input).walls).toEqual(input)
  })
  it('keeps rejected records rejected, bounds repair to source, and cannot collapse a short wall', () => {
    const input = [wall('a', 10, 10, 12, 10), wall('b', 11, 10, 11, 40), { ...wall('c', 0, 0, 100, 0), disposition: 'rejected' }]
    expect(repair(input).walls).toEqual(input)
    expect(() => repairDraftWalls(input, 0, 100)).toThrow()
  })
  it('snaps future wall endpoints onto segment interiors while retaining corner priority', () => {
    const walls = [wall('a', 10, 10, 100, 10)]
    expect(findSnapPoint({ x: 50, y: 14 }, walls)).toEqual({ x: 50, y: 10, snapped: true })
    expect(findSnapPoint({ x: 12, y: 14 }, walls)).toEqual({ x: 10, y: 10, snapped: true })
    expect(findSnapPoint({ x: 50, y: 14 }, walls, { excludeWallId: 'a' }).snapped).toBe(false)
  })
})
