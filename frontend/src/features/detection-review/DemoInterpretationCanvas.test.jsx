/* @vitest-environment jsdom */

import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-konva', () => {
  const container = (name) => function MockContainer({ children, ...props }) {
    return <div data-konva={name} data-name={props.name} ref={(node) => { if (node) node.konvaProps = props }} onClick={props.onClick}>{children}</div>
  }
  const shape = (name) => function MockShape({ text, ...props }) {
    return <span data-konva={name} {...props} ref={node => { if (node) node.konvaProps = props }}>{text}</span>
  }
  return {
    Stage: container('Stage'),
    Layer: container('Layer'),
    Group: container('Group'),
    Image: shape('Image'),
    Line: shape('Line'),
    Rect: shape('Rect'),
    Circle: shape('Circle'),
    Text: shape('Text'),
  }
})

import { DemoInterpretationCanvas } from './DemoInterpretationCanvas.jsx'

describe('DemoInterpretationCanvas', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  const mockDraft = {
    walls: [
      {
        id: 'wall-0001',
        disposition: 'accepted',
        start: { x: 50, y: 50 },
        end: { x: 250, y: 50 },
        estimated_thickness_pixels: 14,
      },
      {
        id: 'wall-0002',
        disposition: 'rejected',
        start: { x: 50, y: 50 },
        end: { x: 50, y: 200 },
      },
    ],
    rooms: [
      {
        id: 'room-0001',
        disposition: 'accepted',
        name: 'Office',
        boundary: [
          { x: 50, y: 50 },
          { x: 250, y: 50 },
          { x: 250, y: 200 },
          { x: 50, y: 200 },
        ],
      },
    ],
    symbols: [
      {
        id: 'sym-0001',
        disposition: 'accepted',
        center: { x: 100, y: 100 },
      },
    ],
  }

  it('previews and places in inverse-transformed source coordinates, ignores toolbar and cancels from chooser', () => {
    const place = vi.fn(), change = vi.fn()
    const {container,rerender} = render(<><select aria-label="chooser"><option>Device</option></select>
      <DemoInterpretationCanvas width={400} height={300} draft={mockDraft} tool="place-device"
        placementPresentation={{family:'switch',label:'Switch'}} onPlaceDevice={place} onToolChange={change} /></>)
    let pointer = {x:180,y:160}
    const stageModel = {getPointerPosition:()=>pointer,
      getAbsoluteTransform:()=>({copy:()=>({invert:()=>({point:p=>({x:(p.x-100)/2,y:(p.y-40)/2})})})})}
    const event = {target:{getStage:()=>stageModel}}
    const stage = container.querySelector('[data-konva="Stage"]')
    act(()=>stage.konvaProps.onMouseMove(event))
    const preview = container.querySelector('[data-name="device-placement-preview"]')
    expect(preview.konvaProps.x).toBe(40)
    expect(preview.konvaProps.y).toBe(60)
    fireEvent.click(screen.getByRole('button',{name:'Zoom In'}))
    expect(place).not.toHaveBeenCalled()
    pointer = {x:50,y:20}
    act(()=>stage.konvaProps.onClick(event))
    expect(place).not.toHaveBeenCalled()
    pointer = {x:180,y:160}
    act(()=>stage.konvaProps.onClick(event))
    expect(place).toHaveBeenCalledWith({x:40,y:60})
    fireEvent.keyDown(screen.getByLabelText('chooser'),{key:'Escape'})
    expect(change).toHaveBeenCalledWith('select')
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={mockDraft} tool="move" layers={{symbols:true}} />)
    expect(container.querySelector('[data-name="device-sym-0001"]').konvaProps.draggable).toBe(false)
  })

  it('commits exact magnetized symbol and wire anchors from slightly offset clicks', () => {
    const onAddWire = vi.fn()
    const source = {...mockDraft,wirings:[{id:'w',points:[{x:200,y:100},{x:200,y:200}]}]}
    const { container } = render(<DemoInterpretationCanvas width={400} height={300} draft={source} tool="wire" onAddWire={onAddWire} />)
    const stage = container.querySelector('[data-konva="Stage"]')
    let point = {x:104,y:99}
    const realStage = {getPointerPosition:() => point,getAbsoluteTransform:() => ({copy:() => ({invert:() => ({point:p => p})})})}
    act(() => stage.konvaProps.onClick({target:{getStage:() => realStage}}))
    point = {x:204,y:101}
    act(() => stage.konvaProps.onClick({target:{getStage:() => realStage}}))
    expect(onAddWire).toHaveBeenCalledWith([{x:100,y:100},{x:200,y:100}])
    expect(source.symbols[0].center).toEqual({x:100,y:100})
  })
  it('magnetizes an existing endpoint in zoomed source space, previews and commits without moving the device', () => {
    const onMove = vi.fn()
    const source = {...mockDraft,wirings:[{id:'w',points:[{x:40,y:100},{x:200,y:100}]}]}
    const {container} = render(<DemoInterpretationCanvas width={400} height={300} draft={source}
      selected={{kind:'wiring',id:'w'}} tool="select" layers={{wirings:true,symbols:true}} onMoveWirePoint={onMove} />)
    const handle = container.querySelector('[name="wiring-point-0"]').konvaProps
    let pos = {x:97,y:101}
    const target = {x:()=>pos.x,y:()=>pos.y,position:p=>{pos=p}}
    act(()=>{handle.onDragStart({target});handle.onDragMove({target})})
    expect(pos).toEqual({x:100,y:100})
    expect(container.querySelector('[name="wire-device-magnet"]')).toBeTruthy()
    act(()=>handle.onDragEnd({target}))
    expect(onMove).toHaveBeenCalledWith('w',0,{x:100,y:100},expect.objectContaining({symbolId:'sym-0001'}))
    expect(container.querySelector('[name="wire-device-magnet"]')).toBeNull()
    expect(source.symbols[0].center).toEqual({x:100,y:100})
    expect(source.wirings[0].points[0]).toEqual({x:40,y:100})
  })
  it('cancels an endpoint magnet on Escape without committing', () => {
    const onMove = vi.fn()
    const source = {...mockDraft,wirings:[{id:'w',points:[{x:40,y:100},{x:200,y:100}]}]}
    const {container} = render(<DemoInterpretationCanvas width={400} height={300} draft={source}
      selected={{kind:'wiring',id:'w'}} tool="select" layers={{wirings:true}} onMoveWirePoint={onMove} />)
    const handle = container.querySelector('[name="wiring-point-0"]').konvaProps
    let pos = {x:99,y:100}
    const target = {x:()=>pos.x,y:()=>pos.y,position:p=>{pos=p},stopDrag:vi.fn()}
    act(()=>{handle.onDragStart({target});handle.onDragMove({target})})
    fireEvent.keyDown(window,{key:'Escape'})
    act(()=>handle.onDragEnd({target}))
    expect(pos).toEqual({x:40,y:100})
    expect(onMove).not.toHaveBeenCalled()
    expect(container.querySelector('[name="wire-device-magnet"]')).toBeNull()
  })
  it('keeps a top wall-drawing hit surface over devices and existing walls without double dispatch', () => {
    const onAddWall=vi.fn()
    const {container,rerender}=render(<DemoInterpretationCanvas width={400} height={300}
      draft={mockDraft} tool="draw" onAddWall={onAddWall} />)
    const hit=container.querySelector('[name="wall-draw-hit"]')
    expect(hit.getAttribute('width')).toBe('400')
    expect(hit.getAttribute('height')).toBe('300')
    expect(hit.getAttribute('fill')).toBe('rgba(0,0,0,0.001)')
    expect(hit.onclick).toBeNull() // one dispatch through Stage, not Rect + Stage
    const stage=container.querySelector('[data-konva="Stage"]')
    let point={x:50,y:50}
    const realStage={getPointerPosition:()=>point,getAbsoluteTransform:()=>({copy:()=>({invert:()=>({point:p=>p})})})}
    for (const next of [{x:50,y:50},{x:250,y:50},{x:250,y:150}]) {
      point=next
      act(()=>stage.konvaProps.onClick({target:{getStage:()=>realStage}}))
    }
    // Joining an existing corner ends the chain, matching the reference.
    expect(onAddWall).toHaveBeenCalledTimes(1)
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={mockDraft} tool="move" />)
    expect(container.querySelector('[name="wall-draw-hit"]')).toBeNull()
  })
  it('renders observed wiring in an independent source-pixel layer, hides removals, and obeys visibility', () => {
    const wires = [
      { id: 'manual-wiring-0001', disposition: 'unresolved', points: [{ x: 10, y: 20 }, { x: 50, y: 30 }] },
      { id: 'manual-wiring-0002', disposition: 'rejected', points: [{ x: 20, y: 20 }, { x: 30, y: 30 }] },
    ]
    const { container, rerender } = render(<DemoInterpretationCanvas width={400} height={300}
      draft={{ ...mockDraft, wirings: wires }} layers={{ wirings: true }} />)
    const line = container.querySelector('[name="observed-wiring-manual-wiring-0001"]')
    expect(line.getAttribute('points')).toBe('10,20,50,30')
    expect(line.getAttribute('stroke')).toBe('#8a5a00')
    expect(container.querySelector('[name="observed-wiring-manual-wiring-0002"]')).toBeNull()
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={{ ...mockDraft, wirings: wires }} layers={{ wirings: false }} />)
    expect(container.querySelector('[name="observed-wiring-manual-wiring-0001"]')).toBeNull()
  })

  it('shares wiring colors across sources and previews the chosen ceiling or underground design', () => {
    const wires = ['manual-wiring-0001', 'generated'].map((id, i) => ({ id,
      origin: i ? 'generated' : undefined, installation_method: 'concealed_in_ceiling', line_style: 'solid',
      points: [{ x: 10, y: 20 }, { x: 50, y: 30 }] }))
    const { container, rerender } = render(<DemoInterpretationCanvas width={400} height={300}
      draft={{ ...mockDraft, wirings: wires }} layers={{ wirings: true }} tool="wire" />)
    for (const wire of wires) expect(container.querySelector(`[name="observed-wiring-${wire.id}"]`).getAttribute('stroke')).toBe('#f05a28')
    const stage = container.querySelector('[data-konva="Stage"]')
    const realStage = { getPointerPosition: () => ({ x: 150, y: 150 }),
      getAbsoluteTransform: () => ({ copy: () => ({ invert: () => ({ point: p => p }) }) }) }
    act(() => stage.konvaProps.onClick({ target: { getStage: () => realStage } }))
    expect(container.querySelector('[name="wiring-draw-preview"]').getAttribute('stroke')).toBe('#f05a28')
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={{ ...mockDraft, wirings: wires }}
      layers={{ wirings: true }} tool="wire" drawingWireMethod="concealed_under_floor" />)
    expect(container.querySelector('[name="wiring-draw-preview"]').getAttribute('stroke')).toBe('#2563eb')
    expect(container.querySelector('[name="wiring-draw-preview"]').getAttribute('dash')).toBeTruthy()
  })

  it('moves named devices in source coordinates, clamps bounds and hides rejected devices', () => {
    const onUpdateSymbol = vi.fn()
    const draft = { ...mockDraft, symbols: [...mockDraft.symbols, { id: 'sym-0002', disposition: 'rejected', center: { x: 10, y: 10 } }] }
    const { container, rerender } = render(<DemoInterpretationCanvas width={400} height={300} draft={draft} tool="select"
      layers={{ walls: false, rooms: false, symbols: true, source: false }} onUpdateSymbol={onUpdateSymbol}
      presentations={{ 'sym-0001': { label: 'Reviewed troffer light', family: 'troffer', mapped: true } }} />)
    expect(screen.getByText('Reviewed troffer light')).toBeTruthy()
    const group = container.querySelector('[data-name="device-sym-0001"]')
    expect(group.konvaProps.draggable).toBe(true)
    expect(container.querySelector('[data-name="device-sym-0002"]')).toBeNull()
    const target = { x: () => 500, y: () => -20, position: vi.fn() }
    group.konvaProps.onDragEnd({ target })
    expect(onUpdateSymbol).toHaveBeenCalledWith(expect.objectContaining({ id: 'sym-0001', center: { x: 400, y: 0 } }), null)
    expect(draft.symbols[0].center).toEqual({ x: 100, y: 100 })
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={draft} tool="pan" layers={{ symbols: true }} onUpdateSymbol={onUpdateSymbol} />)
    expect(container.querySelector('[data-name="device-sym-0001"]').konvaProps.draggable).toBe(false)
    expect(container.querySelector('[data-konva="Stage"]').konvaProps.draggable).toBe(true)
  })

  it('removes a selected device via keyboard without stealing Delete from coordinate input', () => {
    const onDeleteSymbol = vi.fn()
    render(<><input aria-label="coordinate" /><DemoInterpretationCanvas width={400} height={300} draft={mockDraft}
      selected={{ kind: 'symbol', id: 'sym-0001' }} tool="select" onDeleteSymbol={onDeleteSymbol} layers={{ symbols: true }} /></>)
    fireEvent.keyDown(screen.getByLabelText('coordinate'), { key: 'Delete' })
    expect(onDeleteSymbol).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'Delete' })
    expect(onDeleteSymbol).toHaveBeenCalledWith('sym-0001')
  })

  it('renders canvas with viewport zoom controls and light-grid container', () => {
    render(
      <DemoInterpretationCanvas
        width={400}
        height={300}
        draft={mockDraft}
        selected={null}
        onSelect={vi.fn()}
        layers={{ source: true, walls: true, rooms: false, symbols: false }}
        tool="move"
      />,
    )

    expect(screen.getByRole('button', { name: 'Zoom In' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Zoom Out' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Fit to screen' })).toBeTruthy()
    expect(screen.getByText(/Walls use screen-space strokes/)).toBeTruthy()
    expect(screen.getByText(/Alt-drag moves a wall independently/)).toBeTruthy()
  })

  it('uses thin editing centerlines independent of source thickness, with optional footprints',()=>{
    const draft={...mockDraft,walls:[{...mockDraft.walls[0],estimated_thickness_pixels:80}]}
    const before=structuredClone(draft)
    const {container,rerender}=render(<DemoInterpretationCanvas width={400} height={300} draft={draft}
      layers={{walls:true}} tool="move" selected={{kind:'wall',id:'wall-0001'}} />)
    const line=container.querySelector('[name="wall-centerline-wall-0001"]')
    expect(line.konvaProps.strokeWidth).toBeLessThan(5)
    expect(line.konvaProps.hitStrokeWidth).toBeGreaterThan(line.konvaProps.strokeWidth)
    expect(container.querySelector('[data-konva="Line"][closed]')).toBeNull()
    expect(container.querySelectorAll('[data-konva="Circle"]').length).toBeGreaterThanOrEqual(2)
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={draft} layers={{walls:true}}
      tool="select" selected={{kind:'wall',id:'wall-0001'}} />)
    expect(container.querySelectorAll('[data-konva="Circle"]').length).toBeGreaterThanOrEqual(2)
    expect([...container.querySelectorAll('[data-konva="Circle"]')].every(n=>!n.konvaProps.draggable)).toBe(true)
    rerender(<DemoInterpretationCanvas width={400} height={300} draft={draft} layers={{walls:true,wallFootprints:true}} />)
    expect(container.querySelector('[name="wall-centerline-wall-0001"]').konvaProps.stroke).toBe('#0f172a')
    expect([...container.querySelectorAll('[data-konva="Line"]')].some(n=>n.konvaProps.closed&&n.konvaProps.fill)).toBe(true)
    expect(draft).toEqual(before)
  })

  it('shows the Esc pill when in draw mode', () => {
    render(
      <DemoInterpretationCanvas
        width={400}
        height={300}
        draft={mockDraft}
        selected={null}
        onSelect={vi.fn()}
        layers={{ source: true, walls: true, rooms: false, symbols: false }}
        tool="draw"
      />,
    )

    expect(screen.getByText('Press the "Esc" key to stop drawing walls')).toBeTruthy()
  })

  it('handles Delete key to trigger onDeleteWall for selected wall', () => {
    const onDeleteWall = vi.fn()
    render(
      <DemoInterpretationCanvas
        width={400}
        height={300}
        draft={mockDraft}
        selected={{ kind: 'wall', id: 'wall-0001' }}
        onSelect={vi.fn()}
        onDeleteWall={onDeleteWall}
        layers={{ source: true, walls: true, rooms: false, symbols: false }}
        tool="move"
      />,
    )

    fireEvent.keyDown(window, { key: 'Delete' })
    expect(onDeleteWall).toHaveBeenCalledWith('wall-0001')
  })

  it('handles Escape key to return to move tool', () => {
    const onToolChange = vi.fn()
    render(
      <DemoInterpretationCanvas
        width={400}
        height={300}
        draft={mockDraft}
        selected={null}
        onSelect={vi.fn()}
        onToolChange={onToolChange}
        layers={{ source: true, walls: true, rooms: false, symbols: false }}
        tool="draw"
      />,
    )

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onToolChange).toHaveBeenCalledWith('move')
  })
  it('does not commit a wall after a pointer drag, and Escape also cancels from an input',()=>{
    const add=vi.fn(),change=vi.fn()
    const {container}=render(<><input aria-label="drawing length"/><DemoInterpretationCanvas width={400} height={300}
      draft={{walls:[],symbols:[],rooms:[],wirings:[]}} tool="draw" onAddWall={add} onToolChange={change}/></>)
    let point={x:30,y:30}
    const model={getPointerPosition:()=>point,getAbsoluteTransform:()=>({copy:()=>({invert:()=>({point:p=>p})})})}
    const event={target:{getStage:()=>model}},stage=container.querySelector('[data-konva="Stage"]')
    act(()=>stage.konvaProps.onClick(event))
    act(()=>stage.konvaProps.onMouseDown(event))
    point={x:200,y:30}
    act(()=>{stage.konvaProps.onMouseMove(event);stage.konvaProps.onMouseUp(event);stage.konvaProps.onClick(event)})
    expect(add).not.toHaveBeenCalled()
    fireEvent.keyDown(screen.getByLabelText('drawing length'),{key:'Escape'})
    expect(change).toHaveBeenCalledWith('move')
  })
})
