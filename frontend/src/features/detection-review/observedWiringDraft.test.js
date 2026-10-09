import { describe, expect, it } from 'vitest'
import { initialWiringDraft, nextWiringId, parseWiringPoints } from './observedWiringDraft.js'

describe('source-pixel wiring drafts', () => {
  it('preserves saved tombstones, partial traces and explicit heights without mutating history', () => {
    const wire = { id: 'manual-wiring-0002', disposition: 'rejected', points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], completeness: 'partial', elevation_meters: -0.5 }
    const record = { review: { observed_wiring: [wire] } }
    const draft = initialWiringDraft(record)
    expect(draft).toEqual([wire])
    draft[0].points[0].x = 10
    expect(wire.points[0].x).toBe(1)
    expect(nextWiringId(draft)).toBe('manual-wiring-0003')
  })
  it('initializes actual route candidates unresolved, never inventing heights or routes', () => {
    const candidate = { id: 'segment-0001', points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], route_kind: 'observed' }
    const record = { candidate: { payload: { observed_routes: { segments: [candidate] } } } }
    expect(initialWiringDraft(record)).toEqual([{ id: candidate.id, points: candidate.points, disposition: 'unresolved', completeness: 'partial', elevation_meters: null }])
    expect(initialWiringDraft({ candidate: { payload: {} } })).toEqual([])
    expect(initialWiringDraft({ ...record, review: {} })).toEqual(initialWiringDraft(record))
    const removed = { id: candidate.id, points: [{ x: 2, y: 2 }, { x: 5, y: 5 }], disposition: 'rejected', completeness: 'partial', elevation_meters: null }
    expect(initialWiringDraft({ ...record, review: { observed_wiring: [removed] } })).toEqual([removed])
  })
  it('accepts bounded source coordinates, including page edges and non-axis-aligned observed lines', () => {
    expect(parseWiringPoints(' 0,0\n20.5,30\r\n400,300 ', 400, 300)).toEqual([{ x: 0, y: 0 }, { x: 20.5, y: 30 }, { x: 400, y: 300 }])
  })
  it.each(['', '1,2', '1,2\n', '1,2\n1,2', '1,2\n401,20', '1,2\n20,301', '1,2\n-1,2', '1,2\nNaN,3', '1,2\nInfinity,3', '1,2\n,3', '1,2\n0x10,3', '1,2\n1,2,3', Array(2049).fill('1,2').join('\n')])('rejects invalid or incomplete coordinates %s', (text) => {
    expect(() => parseWiringPoints(text, 400, 300)).toThrow()
  })
  it('does not reuse removed identities or exceed the contract identity limit', () => {
    expect(nextWiringId([])).toBe('manual-wiring-0001')
    expect(() => nextWiringId([{ id: 'manual-wiring-9999' }])).toThrow()
  })
})
