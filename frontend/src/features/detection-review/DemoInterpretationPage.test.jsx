/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DemoInterpretationApiError, fetchDemoInterpretation, saveDemoLayout, saveDemoReview } from '../../api/demoInterpretation.js'
import { fetchCurrentLayout } from '../../api/layouts.js'
import { fetchReviewImage } from '../../api/reviewImages.js'
import { fetchSymbolLegends } from '../../api/symbolLegends.js'
import { DemoInterpretationPage } from './DemoInterpretationPage.jsx'


vi.mock('../../api/demoInterpretation.js', async () => ({
  ...(await vi.importActual('../../api/demoInterpretation.js')),
  fetchDemoInterpretation: vi.fn(), saveDemoReview: vi.fn(), saveDemoLayout: vi.fn(),
}))
vi.mock('../../api/layouts.js', async () => ({
  ...(await vi.importActual('../../api/layouts.js')), fetchCurrentLayout: vi.fn(),
}))
vi.mock('../estimation/BOMPanel.jsx', () => ({BOMPanel: () => <div>Automatic draft BOM</div>}))
vi.mock('../../api/reviewImages.js', async () => ({
  ...(await vi.importActual('../../api/reviewImages.js')), fetchReviewImage: vi.fn(),
}))
vi.mock('../../api/symbolLegends.js', async () => ({
  ...(await vi.importActual('../../api/symbolLegends.js')), fetchSymbolLegends: vi.fn(),
}))
vi.mock('./DemoInterpretationCanvas.jsx', () => ({
  DemoInterpretationCanvas: ({ draft, onSelect, onUpdateSymbol, onUpdateWall, onAddWire, onMoveWirePoint, onPlaceDevice, placementPresentation, tool }) => <div data-testid="demo-canvas">
    {draft.walls.length}/{draft.rooms.length}/{draft.symbols.length}
    <button type="button" onClick={() => onSelect({ kind: 'symbol', id: 'symbol-0001' })}>Select first symbol</button>
    <button type="button" onClick={() => onUpdateSymbol({ ...draft.symbols[0], center: { x: 85, y: 65 } })}>Drag first symbol</button>
    <button onClick={()=>onUpdateWall({...draft.walls[0],start:{x:10,y:20},end:{x:100,y:20}})}>Move joined wall</button>
    <button onClick={()=>onMoveWirePoint('segment-0002',0,{x:50,y:20},{kind:'junction',wireId:'segment-0001',segmentIndex:0,t:.5,point:{x:50,y:20}})}>Drag endpoint onto path</button>
    {tool === 'wire' && <button onClick={() => onAddWire([{ x: 20, y: 30 }, { x: 80, y: 30 }])}>Finish drawn wire</button>}
    {tool === 'place-device' && placementPresentation && <button onClick={() => onPlaceDevice({x:200,y:150})}>Place preview device</button>}
  </div>,
}))
vi.mock('./DraftRoomPreview.jsx', () => ({ DraftRoomPreview: ({ draft, onSelect, onUpdateSymbol, onMoveWirePoint }) => <div data-testid="draft-3d">{draft.rooms.length} draft rooms
  <button onClick={() => onSelect({ kind: 'symbol', id: 'symbol-0001' })}>Inspect 3D device</button>
  <button onClick={() => onUpdateSymbol({ ...draft.symbols[0], center: { x: 85, y: 65 } })}>Move 3D device</button>
  <button onClick={()=>onMoveWirePoint('segment-0002',0,{x:50,y:20},{kind:'junction',wireId:'segment-0001',segmentIndex:0,t:.5,point:{x:50,y:20}})}>Drag endpoint onto path</button>
  {draft.wirings?.length > 0 && <><button onClick={() => onSelect({ kind: 'wiring', id: draft.wirings[0].id })}>Inspect 3D wire</button>
    <button onClick={() => onMoveWirePoint(draft.wirings[0].id,1,{ x: 70, y: 30 })}>Move 3D wire point</button></>}
</div> }))


const record = {
  candidate_run_id: 'a'.repeat(32), processing_job_id: 4, floor_plan_id: 3,
  floor_plan_page_id: 8, review: null,
  candidate: { payload: {
    source_plane: { width_pixels: 400, height_pixels: 300 },
    walls: { truncated: false, items: [{ id: 'wall-0001', start: { x: 10, y: 10 }, end: { x: 100, y: 10 } }] },
    rooms: { truncated: false, items: [{ id: 'room-0001', label: null, boundary: [{ x: 10, y: 10 }, { x: 100, y: 10 }, { x: 100, y: 100 }] }] },
    symbols: { truncated: false, items: [{ id: 'symbol-0001', center: { x: 50, y: 50 } }] },
  } },
}


class LoadedImage {
  naturalWidth = 400
  naturalHeight = 300
  set src(value) { this._src = value; queueMicrotask(() => this.onload?.()) }
}


beforeEach(() => {
  fetchDemoInterpretation.mockReset().mockResolvedValue(structuredClone(record))
  fetchReviewImage.mockReset().mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
  fetchSymbolLegends.mockReset().mockResolvedValue([{ id: 9, class_id: 4, name: 'Approved light' }])
  fetchCurrentLayout.mockReset()
  saveDemoReview.mockReset().mockImplementation(async (_floorPlanId, body) => ({
    ...structuredClone(record),
    review: {
      id: 1, revision_number: 1, reviewed_by_user_id: 2,
      created_at: '2026-09-09T00:00:00Z', ...body,
      symbols: body.symbols.map((symbol) => ({ ...symbol, class_id: 4, class_name: 'Approved light' })),
    },
  }))
  saveDemoLayout.mockReset()
  vi.stubGlobal('Image', LoadedImage)
  URL.createObjectURL = vi.fn(() => 'blob:demo')
  URL.revokeObjectURL = vi.fn()
})


afterEach(() => {
  cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals()
})


describe('unified demo interpretation review', () => {
  it.each(['2d','3d'])('edits a shared wire junction in %s with undo/redo and unfinished save/reload', async viewMode => {
    const source=structuredClone(record)
    source.candidate.payload.observed_routes={state:'partial',segments:[
      {id:'segment-0001',points:[{x:0,y:20},{x:100,y:20}]},
      {id:'segment-0002',points:[{x:50,y:70},{x:50,y:120}]},
    ]}
    fetchDemoInterpretation.mockResolvedValue(source)
    const props={projectId:1,floorPlanId:3,processingJobId:4}
    const rendered=render(<DemoInterpretationPage {...props} />)
    await screen.findByText('Select first symbol')
    if(viewMode==='3d')fireEvent.click(screen.getByRole('button',{name:'3D · Draft preview'}))
    const reopen=screen.queryByRole('button',{name:'Reopen Item inspector'})
    if(reopen)fireEvent.click(reopen)
    fireEvent.change(screen.getByLabelText('Select item'),{target:{value:'wiring:segment-0002'}})
    fireEvent.click(screen.getByText('Path vertices & junctions'))
    expect(screen.queryByRole('button',{name:'Connect junction'})).toBeNull()
    fireEvent.click(await screen.findByRole('button',{name:'Drag endpoint onto path'}))
    fireEvent.click(screen.getByRole('button',{name:'Undo'}))
    expect(screen.queryByRole('button',{name:'Detach junction at vertex'})).toBeNull()
    fireEvent.click(screen.getByRole('button',{name:'Redo'}))
    fireEvent.change(within(screen.getByRole('group',{name:'Wire point 1'})).getByLabelText('X'),{target:{value:'60'}})
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body=saveDemoReview.mock.calls[0][1], wires=body.observed_wiring
    expect(wires[0].points).toEqual([{x:0,y:20},{x:60,y:20},{x:100,y:20}])
    expect(wires[1].points[0]).toEqual({x:60,y:20})
    expect(wires[0].junction_attachments[0].junction_id).toBe(wires[1].junction_attachments[0].junction_id)
    expect(body.approved_for_layout).toBe(false)
    const saved=await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue({...saved,candidate:source.candidate})
    rendered.unmount();render(<DemoInterpretationPage {...props} />)
    await screen.findByText('Select first symbol')
    const reopenSaved=screen.queryByRole('button',{name:'Reopen Item inspector'})
    if(reopenSaved)fireEvent.click(reopenSaved)
    fireEvent.change(screen.getByLabelText('Select item'),{target:{value:'wiring:segment-0002'}})
    fireEvent.click(screen.getByText('Path vertices & junctions'))
    fireEvent.click(screen.getByRole('button',{name:'Detach junction at vertex'}))
    expect(screen.queryByRole('button',{name:'Detach junction at vertex'})).toBeNull()
  })
  it('device clipboard supports copy, repeated paste, undo/redo and draft save/reload without copying attachments', async () => {
    const source = structuredClone(record)
    source.draft_review = { symbols: [{ id: 'symbol-0001', disposition: 'corrected',
      center: { x: 50, y: 50 }, symbol_legend_id: 9, mounting_height_meters: 1.2, mounting_wall_id: 'wall-0001' }] }
    source.observed_wiring = [{ id: 'segment-0001', disposition: 'accepted', completeness: 'partial', elevation_meters: null,
      points: [{ x: 10, y: 50 }, { x: 50, y: 50 }], device_attachments: [{ symbol_id: 'symbol-0001', point_index: 1 }] }]
    fetchDemoInterpretation.mockResolvedValue(source)
    const props = { projectId: 1, floorPlanId: 3, processingJobId: 4 }
    const view = render(<DemoInterpretationPage {...props} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    fireEvent.copy(window)
    expect(screen.getByRole('button', { name: 'Undo' }).disabled).toBe(true)
    fireEvent.paste(window)
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/2')
    fireEvent.keyDown(window, { key: 'v', metaKey: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/3')
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/2')
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true, shiftKey: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/3')
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const body = saveDemoReview.mock.calls[0][1]
    expect(body.symbols.slice(1)).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'manual-symbol-0001', disposition: 'added', symbol_legend_id: 9, mounting_height_meters: 1.2 }),
      expect.objectContaining({ id: 'manual-symbol-0002', disposition: 'added' }),
    ]))
    expect(body.symbols[1].center).not.toEqual(body.symbols[2].center)
    expect(body.symbols[1]).not.toHaveProperty('mounting_wall_id')
    expect(body.observed_wiring).toEqual(source.observed_wiring)
    expect(body.review_complete).toBe(false)
    expect(body.approved_for_layout).toBe(false)
    const saved = await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage {...props} />)
    await screen.findByText('Select first symbol')
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/3')
    fireEvent.keyDown(window, { key: 'v', ctrlKey: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/3')
    expect(source.draft_review.symbols).toHaveLength(1)
  })

  it('device clipboard leaves native form editing alone and ignores repeat and unselected devices', async () => {
    render(<DemoInterpretationPage projectId={1} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Select first symbol')
    fireEvent.keyDown(window, { key: 'c', ctrlKey: true })
    fireEvent.keyDown(window, { key: 'v', ctrlKey: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/1')
    fireEvent.click(screen.getByText('Select first symbol'))
    fireEvent.keyDown(window, { key: 'c', ctrlKey: true })
    for (const target of [screen.getByLabelText('VED legend class'), screen.getByLabelText('X', { selector: 'input' })]) {
      expect(fireEvent.keyDown(target, { key: 'v', ctrlKey: true })).toBe(true)
    }
    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true'); document.body.append(editable)
    expect(fireEvent.keyDown(editable, { key: 'v', ctrlKey: true })).toBe(true)
    editable.remove()
    fireEvent.keyDown(window, { key: 'v', ctrlKey: true, repeat: true })
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/1')
  })

  it('counts circuit annotations separately from physical device proposals', async () => {
    const source = structuredClone(record)
    source.candidate.payload.symbols.items = [
      { id: 'symbol-0001', center: { x: 50, y: 50 }, observed_label: 'Duplex outlet' },
      { id: 'symbol-0002', center: { x: 80, y: 50 }, observed_label: 'Circuit home-run notation' },
    ]
    fetchDemoInterpretation.mockResolvedValue(source)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    expect(await screen.findByText(/SHARED DRAFT · 1 DEVICE PROPOSALS · 1 ANNOTATIONS/)).toBeTruthy()
    expect(saveDemoReview).not.toHaveBeenCalled()
  })

  it('numeric wall dimensions update joined corners, undo/redo and survive draft save/reload',async()=>{
    const source=structuredClone(record)
    source.routing_context={pixels_per_meter:100}
    source.candidate.payload.walls.items.push({id:'wall-0002',start:{x:100,y:10},end:{x:100,y:200}})
    fetchDemoInterpretation.mockResolvedValue(source)
    const props={projectId:1,floorPlanId:3,processingJobId:4}
    const view=render(<DemoInterpretationPage {...props} />)
    fireEvent.change(await screen.findByLabelText('Select item'),{target:{value:'wall:wall-0001'}})
    fireEvent.change(screen.getByLabelText('Exact centerline length'),{target:{value:'2'}})
    fireEvent.click(screen.getByRole('button',{name:'Apply length'}))
    expect(screen.getByText(/Centerline: 2 m/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Undo'}))
    expect(screen.getByText(/Centerline: 0.9 m/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Redo'}))
    expect(screen.getByText(/Centerline: 2 m/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Wall height (m, optional)'),{target:{value:'2.5'}})
    fireEvent.change(screen.getByLabelText('Wall thickness (m)'),{target:{value:'0.2'}})
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.walls[0]).toMatchObject({start:{x:10,y:10},end:{x:210,y:10},height_meters:2.5,thickness_meters:.2})
    expect(body.walls[1].start).toEqual(body.walls[0].end)
    const saved=await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue({...saved,routing_context:source.routing_context,candidate:source.candidate})
    view.unmount();render(<DemoInterpretationPage {...props} />)
    fireEvent.change(await screen.findByLabelText('Select item'),{target:{value:'wall:wall-0001'}})
    expect(screen.getByText(/Centerline: 2 m/)).toBeTruthy()
    expect(screen.getByLabelText('Wall height (m, optional)').value).toBe('2.5')
    expect(saveDemoLayout).not.toHaveBeenCalled()
    expect(source.candidate.payload.walls.items[0].end.x).toBe(100)
  })
  it('records a provisional switch correction explicitly and keeps it after reload without canonical approval',async()=>{
    const current=structuredClone(record)
    Object.assign(current.candidate.payload.symbols.items[0],{observed_label:'Gang switch',
      gang_count_proposal:{count:1,basis:'user_requested_default',provisional:true}})
    fetchDemoInterpretation.mockResolvedValue(current)
    fetchSymbolLegends.mockResolvedValue([{id:9,class_id:4,name:'One gang device switch',is_active:true}])
    const props={projectId:1,floorPlanId:3,processingJobId:4}
    const view=render(<DemoInterpretationPage {...props} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByText(/The original one-gang count was defaulted, not read/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button',{name:'Record switch class correction'}))
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.symbols[0].gang_count_confirmed).toBe(true)
    expect(body.review_complete).toBe(false);expect(body.approved_for_layout).toBe(false)
    view.unmount()
    fetchDemoInterpretation.mockResolvedValue({...current,review:{...body,revision_number:1}})
    render(<DemoInterpretationPage {...props} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByText(/Your class correction is recorded/)).toBeTruthy()
    expect(screen.queryByRole('button',{name:'Record switch class correction'})).toBeNull()
  })
  it('moves a shared wall junction in one undoable persisted revision and reloads it',async()=>{
    const current=structuredClone(record)
    current.candidate.payload.walls.items.push({id:'wall-0002',start:{x:100,y:10},end:{x:100,y:100}})
    fetchDemoInterpretation.mockResolvedValue(current)
    const props={projectId:1,floorPlanId:3,processingJobId:4}
    const view=render(<DemoInterpretationPage {...props} />)
    await screen.findByText('Move joined wall')
    fireEvent.click(screen.getByText('Move joined wall'))
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.walls[1].start).toEqual({x:100,y:20})
    expect(body.walls[1].end).toEqual({x:100,y:100})
    view.unmount()
    fetchDemoInterpretation.mockResolvedValue({...current,review:{revision_number:1,...body}})
    render(<DemoInterpretationPage {...props} />)
    await screen.findByText('Move joined wall')
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[1][1].walls).toEqual(body.walls)
  })
  it('keeps wiring visibility and drawing options in the left rail and estimation below the workbench', async () => {
    render(<DemoInterpretationPage projectId={1} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Select first symbol')
    const rail = screen.getByRole('complementary', {name:'Plan editing tools'})
    const visibility = within(rail).getByRole('checkbox', {name:'Show wiring'})
    expect(visibility.checked).toBe(true)
    fireEvent.click(visibility)
    expect(visibility.checked).toBe(false)
    fireEvent.click(within(rail).getByRole('button', {name:'Draw wiring'}))
    expect(within(rail).getByLabelText('Wiring placement').value).toBe('concealed_in_ceiling')
    expect(within(screen.getByRole('region', {name:'Edit item'})).queryByLabelText('Wiring placement')).toBeNull()
    const estimation = screen.getByRole('region', {name:'Plan estimation'})
    expect(within(estimation).getByText('Automatic draft BOM')).toBeTruthy()
    expect(estimation.closest('.studio-device-workbench')).toBeNull()
    expect(estimation.previousElementSibling.textContent).toContain('Measured layout & estimates')
    expect(estimation.parentElement.lastElementChild).toBe(estimation)
    fireEvent.click(screen.getByRole('button', {name:'3D · Draft preview'}))
    await screen.findByTestId('draft-3d')
    expect(within(rail).getByRole('checkbox', {name:'Show wiring'}).checked).toBe(false)
    expect(saveDemoReview).not.toHaveBeenCalled()
  })
  it('automatically links matching devices and edits their class and price together without copying positions',async()=>{
    const source=structuredClone(record)
    source.candidate.payload.symbols.items[0].catalog_class_id=4
    source.candidate.payload.symbols.items.push({id:'symbol-0002',catalog_class_id:4,center:{x:150,y:150}},
      {id:'symbol-0003',center:{x:250,y:250}})
    fetchDemoInterpretation.mockResolvedValue(source)
    fetchSymbolLegends.mockResolvedValue([{id:9,class_id:4,name:'Approved light'},{id:19,class_id:5,name:'Other light'}])
    render(<DemoInterpretationPage projectId={1} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByLabelText('VED legend class').value).toBe('9')
    expect(screen.getByText(/edits apply to 2 matching devices/)).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Custom device unit price (PHP, optional)'),{target:{value:'100'}})
    fireEvent.change(screen.getByLabelText('VED legend class'),{target:{value:'19'}})
    expect(screen.getByLabelText('Custom device unit price (PHP, optional)').value).toBe('')
    fireEvent.change(screen.getByLabelText('Custom device unit price (PHP, optional)'),{target:{value:'200'}})
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await waitFor(()=>expect(saveDemoReview).toHaveBeenCalled())
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.symbols.slice(0,2).map(s=>[s.symbol_legend_id,s.custom_unit_price,s.center])).toEqual([[19,200,{x:50,y:50}],[19,200,{x:150,y:150}]])
    expect(body.symbols[2].symbol_legend_id).toBeNull()
    expect(body.symbols[2].custom_unit_price).toBeUndefined()
    expect(body.approved_for_layout).toBe(false)
    expect(source.candidate.payload.symbols.items[0].catalog_class_id).toBe(4)
  })
  it('saves and reloads a selected device custom price without approving it',async()=>{
    render(<DemoInterpretationPage projectId={1} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    fireEvent.change(screen.getByLabelText('Custom device unit price (PHP, optional)'),{target:{value:'123.45'}})
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await waitFor(()=>expect(saveDemoReview).toHaveBeenCalled())
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.symbols[0].custom_unit_price).toBe(123.45)
    expect(body.approved_for_layout).toBe(false)
    await waitFor(()=>expect(screen.getByLabelText('Custom device unit price (PHP, optional)').value).toBe('123.45'))
  })
  it('loads source-bound manual wall replacements without approving or rewriting raw detection', async () => {
    const inherited=[{...record.candidate.payload.walls.items[0],disposition:'rejected'},
      {id:'manual-wall-0001',disposition:'added',start:{x:20.25,y:30.5},end:{x:20.25,y:90.5}}]
    fetchDemoInterpretation.mockResolvedValue({...structuredClone(record),draft_walls:inherited})
    render(<DemoInterpretationPage projectId={1} floorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('1 wall segments · 1 rooms')
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await waitFor(()=>expect(saveDemoReview).toHaveBeenCalled())
    const payload=saveDemoReview.mock.calls[0][1]
    expect(payload.walls).toEqual(inherited)
    expect(payload.review_complete).toBe(false)
    expect(payload.approved_for_layout).toBe(false)
    expect(payload.expected_revision_number).toBeNull()
    expect(record.candidate.payload.walls.items).toHaveLength(1)
  })
  it('places one chosen device on canvas, exits placement and saves without inventing routing', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByRole('button',{name:'Add missing symbol'}))
    expect(screen.queryByText('Place preview device')).toBeNull()
    fireEvent.change(screen.getByLabelText('Device to place'),{target:{value:'9'}})
    fireEvent.click(screen.getByText('Place preview device'))
    expect(screen.queryByText('Place preview device')).toBeNull()
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    expect(screen.getByText('Wiring · 0 paths')).toBeTruthy()
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.symbols[1]).toMatchObject({id:'manual-symbol-0001',symbol_legend_id:9,center:{x:200,y:150}})
    expect(body.generated_wiring).toEqual([])
    expect(body.review_complete).toBe(false)
    expect(body.approved_for_layout).toBe(false)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('edits and saves generated A* paths immediately, separately from observations and approval', async () => {
    const source = structuredClone(record)
    const wire = { id:'manual-route-0001',disposition:'unresolved',points:[{x:20,y:30},{x:80,y:30}],
      completeness:'partial',elevation_meters:null,algorithm:'astar',source_device_id:'symbol-0001',target_id:'symbol-0002',target_kind:'device' }
    source.generated_wiring=[wire]
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Wiring · 1 paths')
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.change(screen.getByLabelText('Select item'),{target:{value:'wiring:manual-route-0001'}})
    expect(screen.getByText(/Automatic A\* draft — not detected in the image/)).toBeTruthy()
    fireEvent.change(screen.getAllByLabelText('X')[0],{target:{value:'25'}})
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body=saveDemoReview.mock.calls[0][1]
    expect(body.observed_wiring).toEqual([])
    expect(body.generated_wiring[0]).toMatchObject({algorithm:'astar',points:[{x:25,y:30},{x:80,y:30}]})
    expect(body.generated_wiring[0]).not.toHaveProperty('origin')
    expect(body.review_complete).toBe(false)
    const saved=await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Wiring · 1 paths')
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('starts continuous drawing from Add wall instead of inserting a default segment', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByRole('button',{ name: 'Add missing wall' }))
    expect(screen.getByText(/Click A → B → C to keep drawing walls/)).toBeTruthy()
    expect(screen.getByTestId('demo-canvas').textContent).toMatch(/^1\/1\/1/)
    expect(saveDemoReview).not.toHaveBeenCalled()
  })
  it('explains why a superseded historical analysis cannot be saved', async () => {
    saveDemoReview.mockRejectedValue(new DemoInterpretationApiError('The demo interpretation operation could not be completed.',409,'STALE_INTERPRETATION_RUN'))
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByRole('button',{ name: 'Save unfinished draft' }))
    expect(await screen.findByText(/This analysis has been superseded/)).toBeTruthy()
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it.each(['2d','3d'])('commits endpoint connections in %s, undoes/redoes, saves and reloads exact attachments without approval', async view => {
    const source = structuredClone(record)
    source.candidate.payload.symbols.items[0].center = {x:50.125,y:50.75}
    source.candidate.payload.observed_routes = {state:'partial',segments:[{id:'segment-0001',points:[{x:10,y:20},{x:30,y:20}]}]}
    fetchDemoInterpretation.mockResolvedValue(source)
    const rendered = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByLabelText('Select item')
    if (view === '3d') fireEvent.click(screen.getByRole('button',{name:'3D · Draft preview'}))
    fireEvent.change(screen.getByLabelText('Select item'),{target:{value:'wiring:segment-0001'}})
    fireEvent.click(screen.getByText('Device connections'))
    fireEvent.change(screen.getByLabelText('Start device'),{target:{value:'symbol-0001'}})
    expect(screen.getByLabelText('Start device').value).toBe('symbol-0001')
    fireEvent.click(screen.getByRole('button',{name:'Undo'}))
    expect(screen.getByLabelText('Start device').value).toBe('')
    fireEvent.click(screen.getByRole('button',{name:'Redo'}))
    expect(screen.getByLabelText('Start device').value).toBe('symbol-0001')
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await screen.findByText('Review revision 1 saved.')
    const body = saveDemoReview.mock.calls[0][1]
    expect(body.observed_wiring[0]).toMatchObject({points:[{x:50.125,y:50.75},{x:30,y:20}],
      device_attachments:[{symbol_id:'symbol-0001',point_index:0}]})
    expect(body.symbols[0].center).toEqual({x:50.125,y:50.75})
    expect(body.approved_for_layout).toBe(false)
    const saved = await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue({...saved,candidate:source.candidate})
    rendered.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.change(await screen.findByLabelText('Select item'),{target:{value:'wiring:segment-0001'}})
    expect(screen.getByLabelText('Start device').value).toBe('symbol-0001')
    fireEvent.click(screen.getByRole('button',{name:'Disconnect start'}))
    expect(screen.getByLabelText('Start device').value).toBe('')
    expect(saveDemoLayout).not.toHaveBeenCalled()
    expect(source.candidate.payload.observed_routes.segments[0].points[0]).toEqual({x:10,y:20})
  })
  it('persists 3D wire point corrections and reloads the same draft without approval', async () => {
    const source = structuredClone(record)
    source.candidate.payload.observed_routes = { state: 'partial', segments: [{ id: 'segment-0001', points: [{ x: 10, y: 20 }, { x: 30, y: 20 }] }] }
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByRole('button',{ name: '3D · Draft preview', exact: true }))
    fireEvent.click(await screen.findByText('Inspect 3D wire'))
    fireEvent.click(screen.getByText('Move 3D wire point'))
    fireEvent.click(screen.getByRole('button',{ name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[0][1]).toMatchObject({ review_complete: false, approved_for_layout: false,
      observed_wiring: [{ id: 'segment-0001', points: [{ x: 10, y: 20 },{ x: 70, y: 30 }], disposition: 'corrected', completeness: 'partial', elevation_meters: null }] })
    const saved = await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Wiring · 1 paths')
    fireEvent.click(screen.getByText('Edit wiring points'))
    expect(screen.getByLabelText('Source-pixel points segment-0001').value).toBe('10,20\n70,30')
    expect(saveDemoLayout).not.toHaveBeenCalled()
    expect(source.candidate.payload.observed_routes.segments[0].points[1]).toEqual({ x: 30, y: 20 })
  })
  it('saves visible wiring edits and tombstones, restores them on reload, and supports undo without canonical approval', async () => {
    const source = structuredClone(record)
    source.candidate.payload.observed_routes = { state: 'partial', segments: [{ id: 'segment-0001', points: [{ x: 10, y: 20 }, { x: 30, y: 20 }] }] }
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Wiring · 1 paths')
    fireEvent.click(screen.getByText('Edit wiring points'))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.change(screen.getByLabelText('Source-pixel points segment-0001'), { target: { value: '10,20\n50,20' } })
    fireEvent.click(screen.getByText('Apply wiring changes'))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[0][1]).toMatchObject({ review_complete: false, approved_for_layout: false, observed_wiring: [{ id: 'segment-0001', points: [{ x: 10, y: 20 }, { x: 50, y: 20 }], disposition: 'corrected', completeness: 'partial', elevation_meters: null }] })
    fireEvent.click(screen.getByText('Remove wiring trace'))
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Redo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(2))
    const saved = await saveDemoReview.mock.results[1].value
    expect(saved.review.observed_wiring[0]).toMatchObject({ disposition: 'rejected', points: [{ x: 10, y: 20 }, { x: 50, y: 20 }] })
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText('Wiring · 0 paths')
    fireEvent.click(screen.getByText('Edit wiring points'))
    expect(screen.getByText(/Restore (item|wiring)/)).toBeTruthy()
    expect(source.candidate.payload.observed_routes.segments[0].points[1].x).toBe(30)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('makes PDF device names selectable but prevents a wiring pattern from becoming a device', async () => {
    fetchSymbolLegends.mockResolvedValue([
      { id: 19, class_id: 70, name: '2 x 40 watts fluorescent lamp [pdf-76f411c60b6d:p1:L02]' },
      { id: 20, class_id: 71, name: 'Raceway conduit concealed in ceiling [pdf-76f411c60b6d:p1:L10]' },
    ])
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByRole('option', { name: /2 x 40 watts fluorescent lamp/ }).disabled).toBe(false)
    expect(screen.getByRole('option', { name: /Wiring reference, not a device/ }).disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('VED legend class'), { target: { value: '19' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[0][1].symbols[0].symbol_legend_id).toBe(19)
  })
  it('automatically maps an exact training entry without accepting it, then preserves the choice on reload', async () => {
    const source = structuredClone(record)
    source.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    source.candidate.payload.symbols.items[0].training_legend = {
      name: 'Reviewed downlight', legend_entry: 'sheet-08:L01', model_class_id: 0, dataset_sha256: 'a'.repeat(64),
    }
    fetchDemoInterpretation.mockResolvedValue(source)
    const legend = { id: 19, class_id: 70, name: 'Reviewed downlight [sheet-08:L01]' }
    fetchSymbolLegends.mockResolvedValue([legend])
    saveDemoReview.mockImplementation(async (_id, body) => ({ ...source, review: {
      id: 1, revision_number: 1, ...body,
      symbols: body.symbols.map((symbol) => ({ ...symbol, class_id: 70, class_name: legend.name })),
    } }))
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByRole('heading', { name: 'Reviewed downlight' })).toBeTruthy()
    expect(screen.getByText(/Drawing entry: sheet-08:L01/)).toBeTruthy()
    expect(screen.getByLabelText('VED legend class').value).toBe('19')
    expect(screen.queryByText('Use trained legend mapping')).toBeNull()
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const saved = await saveDemoReview.mock.results[0].value
    expect(saved.review.symbols[0]).toMatchObject({ symbol_legend_id: 19, disposition: 'unresolved', class_name: legend.name })
    expect(saveDemoReview.mock.calls[0][1].symbols[0].training_legend).toBeUndefined()
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    fireEvent.click(await screen.findByText('Select first symbol'))
    expect(screen.getByLabelText('VED legend class').value).toBe('19')
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    expect(screen.getByText(/Drawing entry: sheet-08:L01/)).toBeTruthy()
    expect(source.candidate.payload.symbols.items[0].training_legend.model_class_id).toBe(0)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('draws wiring into the shared draft, saves/reloads and supports undo without extra scan controls', async () => {
    const source = structuredClone(record)
    source.candidate.payload.walls.items.push(
      { id: 'wall-0002', start: { x: 50, y: 10 }, end: { x: 100, y: 10 } },
      { id: 'wall-0003', start: { x: 50, y: 15 }, end: { x: 50, y: 80 } },
    )
    const original = structuredClone(source)
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    expect(screen.queryByRole('button', { name: 'Connect walls' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Select drawing region' })).toBeNull()
    expect(screen.queryByText('Reprocess a drawing region (optional)')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Draw wiring' }))
    fireEvent.click(screen.getByRole('button', { name: 'Finish drawn wire' }))
    expect(screen.getByText('Wiring · 1 paths')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.getByText('Wiring · 0 paths')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    expect(saveDemoReview.mock.calls[0][1].walls[1].disposition).toBe('accepted')
    fireEvent.click(screen.getByRole('button', { name: 'Finish drawn wire' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(2))
    const body = saveDemoReview.mock.calls[1][1]
    expect(body.walls[1].disposition).toBe('accepted')
    expect(body.walls[2].start).toEqual({ x: 50, y: 15 })
    expect(body.walls).toHaveLength(3)
    expect(body.review_complete).toBe(false)
    expect(body.observed_wiring).toEqual([{ id: 'manual-wiring-0001', points: [{ x: 20, y: 30 }, { x: 80, y: 30 }],
      disposition: 'added', completeness: 'partial', elevation_meters: null,
      installation_method:'concealed_in_ceiling',line_style:'solid',wiring_legend_id:null,wiring_legend_name:null }])
    const saved = await saveDemoReview.mock.results[1].value
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    expect(screen.getByText('Wiring · 1 paths')).toBeTruthy()
    expect(source).toEqual(original)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('saves the left-rail underground choice with manually drawn wiring without approval', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    fireEvent.click(screen.getByRole('button', {name:'Draw wiring'}))
    fireEvent.change(screen.getByLabelText('Wiring placement'),{target:{value:'concealed_under_floor'}})
    fireEvent.click(screen.getByRole('button',{name:'Finish drawn wire'}))
    fireEvent.click(screen.getByRole('button',{name:'Save unfinished draft'}))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalled())
    expect(saveDemoReview.mock.calls[0][1].observed_wiring[0]).toMatchObject({
      installation_method:'concealed_under_floor',line_style:'dashed',elevation_meters:null,
      points:[{x:20,y:30},{x:80,y:30}],disposition:'added',
    })
    expect(saveDemoReview.mock.calls[0][1].approved_for_layout).toBe(false)
  })
  it('keeps names, class corrections, 3D movement, removal and undo in one revisioned draft', async () => {
    const source = structuredClone(record)
    source.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    source.candidate.payload.symbols.items[0].observed_label = 'Troffer light'
    fetchDemoInterpretation.mockResolvedValue(source)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    expect(screen.getByRole('complementary', { name: 'Plan editing tools' })).toBeTruthy()
    expect(screen.getByRole('option', { name: /Troffer light/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '3D · Draft preview' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Inspect 3D device' }))
    expect(screen.getByRole('heading', { name: 'Troffer light' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('VED legend class'), { target: { value: '9' } })
    expect(screen.getByRole('heading', { name: 'Approved light' })).toBeTruthy()
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Move 3D device' }))
    expect(screen.getByLabelText('X').value).toBe('85')
    expect(screen.getByLabelText('Y').value).toBe('65')
    fireEvent.click(screen.getByRole('button', { name: 'Remove device' }))
    expect(screen.getByText(/Restore (item|wiring)/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Redo' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const body = saveDemoReview.mock.calls[0][1]
    expect(body.symbols[0]).toEqual({ id: 'symbol-0001', disposition: 'rejected', center: { x: 85, y: 65 }, symbol_legend_id: 9 })
    expect(body.walls[0].estimated_thickness_pixels).toBe(12) // advisory pixel width, not approved metres
    expect(body.review_complete).toBe(false)
    expect(body.approved_for_layout).toBe(false)
    expect(source.candidate.payload.symbols.items[0].center).toEqual({ x: 50, y: 50 })
    const saved = await saveDemoReview.mock.results[0].value
    fetchDemoInterpretation.mockResolvedValue({ ...saved, candidate: source.candidate })
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    fireEvent.change(screen.getByLabelText('Select item'), { target: { value: 'symbol:symbol-0001' } })
    expect(screen.getByText(/Restore (item|wiring)/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Remove device' }).disabled).toBe(true)
    expect(screen.getByLabelText('X').value).toBe('85')
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it('preserves extension completeness while an automatically connected wire follows device movement', async () => {
    const saved = structuredClone(record)
    saved.review = { revision_number: 3, walls: [{ ...record.candidate.payload.walls.items[0], disposition: 'accepted' }], rooms: [],
      symbols: [{ id: 'symbol-0001', disposition: 'unresolved', center: { x: 50, y: 50 }, symbol_legend_id: null }],
      observed_wiring: [{ id: 'wiring-0001', disposition: 'unresolved', points: [{ x: 10, y: 10 }, { x: 50, y: 50 }], completeness: 'partial' }],
      openings: [], panels: [], scale_evidence: [], checklist: { symbols: 'pending', observed_wiring: 'pending' } }
    fetchDemoInterpretation.mockResolvedValue(saved)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    fireEvent.click(screen.getByRole('button', { name: 'Drag first symbol' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledOnce())
    expect(saveDemoReview.mock.calls[0][1]).toMatchObject({ expected_revision_number: 3,
      observed_wiring: [{...saved.review.observed_wiring[0],disposition:'corrected',
        points:[{x:10,y:10},{x:85,y:65}],device_attachments:[{symbol_id:'symbol-0001',point_index:1}]}], checklist: saved.review.checklist })
  })
  it('reloads corrected 56-entry proposals from the saved review without changing the AI candidate', async () => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    const view = render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/uses the trained legend catalog/i)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    fireEvent.change(screen.getByLabelText('VED legend class'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('X'), { target: { value: '75' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await screen.findByText('Review revision 1 saved.')
    const saved = await saveDemoReview.mock.results[0].value
    saved.candidate = structuredClone(experimental.candidate)
    expect(saved.review.symbols[0]).toEqual(expect.objectContaining({
      disposition: 'corrected', symbol_legend_id: 9, center: { x: 75, y: 50 },
    }))
    expect(experimental.candidate.payload.symbols.items[0].center).toEqual({ x: 50, y: 50 })
    fetchDemoInterpretation.mockResolvedValue(saved)
    view.unmount()
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/uses the trained legend catalog/i)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.getByLabelText('X').value).toBe('75')
    expect(screen.getByLabelText('VED legend class').value).toBe('9')
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it('previews rooms in 3D with no legend or approval and saves only an unfinished draft', async () => {
    fetchSymbolLegends.mockResolvedValue([])
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    fireEvent.click(screen.getByRole('button', { name: '3D · Draft preview' }))
    expect((await screen.findByTestId('draft-3d')).textContent).toContain('1 draft rooms')
    expect(saveDemoLayout).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1]).toEqual(expect.objectContaining({ review_complete: false, approved_for_layout: false, wall_height_meters: null }))
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
  it('loads aligned room wall and symbol proposals with explicit review controls', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    expect(await screen.findByRole('heading', { name: 'Plan editor' })).toBeTruthy()
    expect(screen.getByTestId('demo-canvas').textContent).toContain('1/1/1')
    expect(screen.getByText(/Required normalized dimensions: 400 × 300/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Save shared canonical layout' }).disabled).toBe(true)
  })

  it('maps and corrects a symbol then saves a separate immutable review revision', async () => {
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByRole('heading', { name: 'Plan editor' })
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.change(screen.getByLabelText('VED legend class'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Review evidence notes'), { target: { value: 'Reviewed visible geometry.' } })
    fireEvent.click(screen.getByLabelText(/I reviewed every proposed/))
    fireEvent.click(screen.getByRole('button', { name: 'Save review revision' }))

    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][0]).toBe(3)
    expect(saveDemoReview.mock.calls[0][1]).toEqual(expect.objectContaining({
      review_complete: true, approved_for_layout: false,
      symbols: [expect.objectContaining({ id: 'symbol-0001', symbol_legend_id: 9 })],
    }))
    expect(await screen.findByText('Review revision 1 saved.')).toBeTruthy()
  })

  it('keeps experimental template proposals unresolved until a user reviews and saves them', async () => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: 'experimental_pull_station_template' }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(/Experimental two-template Pull station detector/)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Remove device' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1].symbols[0].disposition).toBe('rejected')
    expect(saveDemoReview.mock.calls[0][1].review_complete).toBe(false)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })

  it.each([
    ['experimental_reviewed_symbol_yolo', /Troffer, smoke detector and Pull station only/i],
    ['experimental_linked_legend_yolo', /Five classes with uneven same-source recall/i],
    ['development_multiclass56_yolo', /uses the trained legend catalog/i],
  ])('keeps %s symbol proposals unresolved before review', async (provider, note) => {
    const experimental = structuredClone(record)
    experimental.candidate.provenance = { model_release_id: provider }
    fetchDemoInterpretation.mockResolvedValue(experimental)
    render(<DemoInterpretationPage projectId={1} projectFloorId={2} floorPlanId={3} processingJobId={4} />)
    await screen.findByText(note)
    fireEvent.click(screen.getByRole('button', { name: 'Select first symbol' }))
    expect(screen.queryByLabelText('Review decision')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Save unfinished draft' }))
    await waitFor(() => expect(saveDemoReview).toHaveBeenCalledTimes(1))
    expect(saveDemoReview.mock.calls[0][1].symbols[0].disposition).toBe('unresolved')
    expect(saveDemoReview.mock.calls[0][1].review_complete).toBe(false)
    expect(saveDemoLayout).not.toHaveBeenCalled()
  })
})
