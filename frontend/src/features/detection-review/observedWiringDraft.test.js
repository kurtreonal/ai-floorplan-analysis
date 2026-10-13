import { describe, expect, it } from 'vitest'
import { initialWiringDraft, nextWiringId, parseWiringPoints, wiringSavePayload } from './observedWiringDraft.js'

describe('source-pixel wiring drafts', () => {
  it('shows generated routes immediately and saves them separately without confirmation', () => {
    const generated = { id: 'manual-route-0001', points: [{x:1,y:2},{x:3,y:2}], disposition: 'unresolved', completeness: 'partial',
      elevation_meters: null, algorithm: 'astar', source_device_id: 'symbol-0001', target_id: 'symbol-0002', target_kind: 'device' }
    const record = { generated_wiring: [generated], candidate: { payload: {} } }
    const wires = initialWiringDraft(record)
    expect(wires).toEqual([{...generated,origin:'generated'}])
    expect(wiringSavePayload(wires)).toEqual({observed_wiring:[],generated_wiring:[generated]})
    expect(initialWiringDraft({...record,review:{generated_wiring:[{...generated,disposition:'rejected'}]}})[0].disposition).toBe('rejected')
    expect(generated).not.toHaveProperty('origin')
  })
  it('preserves saved tombstones, partial traces and explicit heights without mutating history', () => {
    const wire = { id: 'manual-wiring-0002', disposition: 'rejected', points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], completeness: 'partial', elevation_meters: -0.5 }
    const record = { review: { observed_wiring: [wire] } }
    const draft = initialWiringDraft(record)
    expect(draft).toEqual([wire])
    draft[0].points[0].x = 10
    expect(wire.points[0].x).toBe(1)
    expect(nextWiringId(draft)).toBe('manual-wiring-0003')
  })
  it('includes appended service paths without replacing saved edits or removals', () => {
    const saved={id:'manual-route-0007',disposition:'rejected',points:[{x:10,y:10},{x:20,y:10}]}
    const added={id:'manual-route-0008',disposition:'unresolved',points:[{x:30,y:30},{x:30,y:10}]}
    const record={review:{generated_wiring:[saved]},generated_wiring:[{...saved,disposition:'unresolved'},added]}
    const before=structuredClone(record)
    expect(initialWiringDraft(record)).toEqual([{...saved,origin:'generated'},{...added,origin:'generated'}])
    expect(record).toEqual(before)
  })
  it('initializes actual route candidates unresolved, never inventing heights or routes', () => {
    const candidate = { id: 'segment-0001', points: [{ x: 1, y: 2 }, { x: 3, y: 4 }], route_kind: 'observed' }
    const record = { candidate: { payload: { observed_routes: { segments: [candidate] } } } }
    expect(initialWiringDraft(record)).toEqual([{ id: candidate.id, points: candidate.points, disposition: 'unresolved', completeness: 'partial', elevation_meters: null, line_style: 'unknown' }])
    expect(initialWiringDraft({ candidate: { payload: {} } })).toEqual([])
    expect(initialWiringDraft({ ...record, review: {} })).toEqual(initialWiringDraft(record))
    const removed = { id: candidate.id, points: [{ x: 2, y: 2 }, { x: 5, y: 5 }], disposition: 'rejected', completeness: 'partial', elevation_meters: null }
    expect(initialWiringDraft({ ...record, review: { observed_wiring: [removed] } })).toEqual([removed])
  })
  it('accepts bounded source coordinates, including page edges and non-axis-aligned observed lines', () => {
    expect(parseWiringPoints(' 0,0\n20.5,30\r\n400,300 ', 400, 300)).toEqual([{ x: 0, y: 0 }, { x: 20.5, y: 30 }, { x: 400, y: 300 }])
  })
  it('uses server-derived catalog meanings and suppresses only redundant unedited automatic paths', () => {
    const wire={id:'segment-0001',points:[{x:1,y:1},{x:2,y:1}],installation_method:'concealed_under_floor',wiring_legend_id:1790}
    const path={id:'manual-route-0001',disposition:'unresolved',points:[{x:1,y:1},{x:2,y:1}]}
    const suppressed={...path,disposition:'rejected',suppression_reason:'redundant_observed_connection'}
    const record={observed_wiring:[wire],review:{generated_wiring:[path]},generated_wiring:[suppressed]}
    expect(initialWiringDraft(record)).toEqual([wire,{...suppressed,origin:'generated'}])
    expect(wiringSavePayload(initialWiringDraft(record)).observed_wiring).toEqual([wire])
    expect(initialWiringDraft({...record,review:{generated_wiring:[{...path,disposition:'corrected'}]}})[1].disposition).toBe('corrected')
    const typed={...path,installation_method:'concealed_under_floor',line_style:'dashed',wiring_legend_id:1790,wiring_legend_name:'Approved floor conduit'}
    const edited={...path,disposition:'corrected',points:[{x:9,y:9},{x:10,y:9}]}
    const enriched=initialWiringDraft({review:{generated_wiring:[edited]},generated_wiring:[typed]})[0]
    expect(enriched.points).toEqual(edited.points)
    expect(enriched.installation_method).toBe('concealed_under_floor')
    expect(enriched.disposition).toBe('corrected')
  })
  it.each(['', '1,2', '1,2\n', '1,2\n1,2', '1,2\n401,20', '1,2\n20,301', '1,2\n-1,2', '1,2\nNaN,3', '1,2\nInfinity,3', '1,2\n,3', '1,2\n0x10,3', '1,2\n1,2,3', Array(2049).fill('1,2').join('\n')])('rejects invalid or incomplete coordinates %s', (text) => {
    expect(() => parseWiringPoints(text, 400, 300)).toThrow()
  })
  it('does not reuse removed identities or exceed the contract identity limit', () => {
    expect(nextWiringId([])).toBe('manual-wiring-0001')
    expect(() => nextWiringId([{ id: 'manual-wiring-9999' }])).toThrow()
  })
})
