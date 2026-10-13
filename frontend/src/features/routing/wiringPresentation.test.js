import { expect, it } from 'vitest'
import { displayWiringRuns, roundedWiringCurve, wiringRuns } from './wiringPresentation.js'

const run = (id, points) => ({ id, ownerId: id, points })
it('separates coincident runs deterministically but pins their original terminals', () => {
  const original = [run('b', [[0, 3, 0], [4, 3, 0]]), run('a', [[4, 3, 0], [0, 3, 0]])]
  const before = structuredClone(original)
  const display = displayWiringRuns(original, .02)
  expect(display[0].laneOffset).not.toBe(display[1].laneOffset)
  display.forEach((wire, index) => {
    expect(wire.points[0]).toEqual(original[index].points[0])
    expect(wire.points.at(-1)).toEqual(original[index].points.at(-1))
  })
  const reversed = displayWiringRuns([...original].reverse(), .02)
  expect(reversed.find(w => w.id === 'a').points).toEqual(display.find(w => w.id === 'a').points)
  expect(original).toEqual(before)
})
it('keeps branch contact and vertical device drops exact and does not spread clean parallel runs', () => {
  const original = [run('a', [[0, 3, 0], [2, 3, 0], [4, 3, 0]]),
    run('b', [[0, 3, 0], [4, 3, 0]]), run('drop', [[2, 3, 0], [2, 1.2, 0]]),
    run('far', [[0, 3, 1], [4, 3, 1]])]
  const display = displayWiringRuns(original, .02)
  expect(display[0].points).toContainEqual([2, 3, 0])
  expect(display[1].points).toContainEqual([2, 3, 0])
  expect(display[2].points).toEqual(original[2].points)
  expect(display[3].points).toEqual(original[3].points)
})
it('does not collapse overlapping edges or fabricate shared branches at unmarked crossings', () => {
  const input = [run('a', [[0, 3, 0], [4, 3, 0]]), run('b', [[2, 3, -1], [2, 3, 1]])]
  expect(displayWiringRuns(input, .02).map(w => w.points)).toEqual(input.map(w => w.points))
})
it('separates near-parallel tube collisions without connecting their distinct terminals',()=>{
  const input=[run('a',[[0,3,0],[4,3,0]]),run('b',[[0,3,.01],[4,3,.01]])]
  const display=displayWiringRuns(input,.02)
  expect(display[0].laneOffset).not.toBe(display[1].laneOffset)
  expect(display[0].points[0]).toEqual([0,3,0])
  expect(display[1].points[0]).toEqual([0,3,.01])
  expect(display[0].anchors).not.toContainEqual([0,3,.01])
})
it('rounds bends locally without overshoot, leaves anchors exact, and keeps endpoints intact', () => {
  const points = [[0, 3, 0], [2, 3, 0], [2, 3, 2]]
  const curve = roundedWiringCurve(points, .02)
  expect(curve.getPoint(0).toArray()).toEqual(points[0])
  expect(curve.getPoint(1).toArray()).toEqual(points.at(-1))
  expect(curve.curves.some(c => c.type === 'QuadraticBezierCurve3')).toBe(true)
  expect(curve.getPoints(200).every(p => p.x >= -1e-10 && p.x <= 2+1e-10 && p.z >= -1e-10 && p.z <= 2+1e-10 && Math.abs(p.y-3)<1e-10)).toBe(true)
  const pinned = roundedWiringCurve(points, .02, [points[1]])
  expect(pinned.curves.every(c => c.type === 'LineCurve3')).toBe(true)
})
it('joins only consecutive same-style segments, preserving source segment indices', () => {
  const segments = [{ start: [0,3,0], end: [2,3,0] }, { start: [2,3,0], end: [2,3,2] },
    { start: [2,3,2], end: [2,1.2,2], previewDrop: true },
    { start: [0,3,0], end: [0,3,1] }]
  const output = wiringRuns(segments, 'wire', s => s.previewDrop ? 'drop' : 'ceiling')
  expect(output).toHaveLength(3)
  expect(output[0].points).toEqual([[0,3,0],[2,3,0],[2,3,2]])
  expect(output[0].segmentIndices).toEqual([0,1])
})
it('bounds dense-page work and rejects invalid/zero-length points without changing input', () => {
  const input = Array.from({length: 1100}, (_, i) => run(String(i), [[0,3,0],[4,3,0]]))
  const output = displayWiringRuns(input, .02)
  expect(output.every(w => w.laneOffset === 0)).toBe(true)
  expect(roundedWiringCurve([[0,0,0],[0,0,0]], .02)).toBeNull()
  expect(() => roundedWiringCurve([[0,0,0],[NaN,0,0]], .02)).toThrow()
})
