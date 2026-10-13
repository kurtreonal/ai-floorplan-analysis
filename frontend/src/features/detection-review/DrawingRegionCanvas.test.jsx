/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('react-konva', () => {
  const container = (name) => function Container({ children, ...props }) {
    return <div data-konva={name} data-name={props.name} ref={(node) => { if (node) node.konvaProps = props }}>{children}</div>
  }
  return Object.fromEntries(['Stage', 'Layer', 'Group', 'Image', 'Line', 'Rect', 'Circle', 'Text'].map((name) => [name, container(name)]))
})
import { DemoInterpretationCanvas } from './DemoInterpretationCanvas.jsx'
afterEach(cleanup)

describe('drawing selection in a panned and zoomed canvas', () => {
  it('selects wiring and edits its source point without mutating the original trace', () => {
    const wire = { id: 'w', disposition: 'unresolved', points: [{ x: 50, y: 40 }, { x: 150, y: 40 }] }
    const onSelect = vi.fn(), onMoveWirePoint = vi.fn()
    const { container } = render(<DemoInterpretationCanvas width={400} height={300} tool="select"
      draft={{ walls: [], rooms: [], symbols: [], wirings: [wire] }} layers={{ wirings: true }}
      selected={{ kind: 'wiring', id: 'w' }} onSelect={onSelect} onMoveWirePoint={onMoveWirePoint} />)
    const line = container.querySelector('[data-name="observed-wiring-w"]')
    expect(line.parentElement.konvaProps.listening).toBe(true)
    line.konvaProps.onClick({ cancelBubble: false })
    expect(onSelect).toHaveBeenCalledWith({ kind: 'wiring', id: 'w' })
    const target = { x: () => 180, y: () => 60, position: vi.fn() }
    container.querySelector('[data-name="wiring-point-1"]').konvaProps.onDragEnd({ target })
    expect(onMoveWirePoint).toHaveBeenCalledWith('w',1,{ x: 180, y: 60 })
    expect(target.position).toHaveBeenCalledWith(wire.points[1])
    expect(wire.points[1]).toEqual({ x: 150, y: 40 })
  })
  it('continues A to B to C, ignores zero-length clicks and finishes with Escape', () => {
    const onAddWall = vi.fn(), onToolChange = vi.fn()
    const props = { width: 400, height: 300, draft: { walls: [], rooms: [], symbols: [] }, tool: 'draw', onAddWall, onToolChange }
    const { container, rerender } = render(<DemoInterpretationCanvas {...props} editingSession={0} />)
    let pointer = { x: 50, y: 40 }
    const transform = { copy: () => transform, invert: () => transform, point: p => p }
    const stage = { getPointerPosition: () => pointer, getAbsoluteTransform: () => transform }
    const click = () => act(() => container.querySelector('[data-konva="Stage"]').konvaProps.onClick({ target: { getStage: () => stage } }))
    click(); pointer = { x: 150, y: 40 }; click(); click()
    pointer = { x: 150, y: 140 }; click()
    expect(onAddWall).toHaveBeenCalledTimes(2)
    expect(onAddWall.mock.calls[0][0]).toMatchObject({ start: { x: 50, y: 40 }, end: { x: 150, y: 40 } })
    expect(onAddWall.mock.calls[1][0]).toMatchObject({ start: { x: 150, y: 40 }, end: { x: 150, y: 140 } })
    fireEvent.keyDown(window,{ key: 'Escape' })
    expect(onToolChange).toHaveBeenCalledWith('move')
    rerender(<DemoInterpretationCanvas {...props} editingSession={1} />)
    pointer = { x: 200, y: 160 }; click()
    expect(onAddWall).toHaveBeenCalledTimes(2)
    pointer = { x: 250, y: 160 }; click()
    expect(onAddWall.mock.calls[2][0]).toMatchObject({ start: { x: 200, y: 160 }, end: { x: 250, y: 160 } })
  })
  it('draws manual wiring from fresh click positions in source coordinates without changing walls', () => {
    const onAddWire = vi.fn(), onAddWall = vi.fn()
    const { container } = render(<DemoInterpretationCanvas width={400} height={300}
      draft={{ walls: [], rooms: [], symbols: [] }} tool="wire" onAddWire={onAddWire} onAddWall={onAddWall} />)
    let pointer = { x: 160, y: 140 }
    const transform = { copy: () => transform, invert: () => transform,
      point: ({ x, y }) => ({ x: (x - 60) / 2, y: (y - 60) / 2 }) }
    const stage = { getPointerPosition: () => pointer, getAbsoluteTransform: () => transform }
    const click = () => act(() => container.querySelector('[data-konva="Stage"]').konvaProps.onClick({ target: { getStage: () => stage } }))
    click(); pointer = { x: 360, y: 180 }; click()
    expect(onAddWire).toHaveBeenCalledWith([{ x: 50, y: 40 }, { x: 150, y: 60 }])
    expect(onAddWall).not.toHaveBeenCalled()
    click(); fireEvent.keyDown(window, { key: 'Escape' }); pointer = { x: 400, y: 200 }; click()
    expect(onAddWire).toHaveBeenCalledTimes(1)
    fireEvent.keyDown(window, { key: 'Shift' }); pointer = { x: 560, y: 220 }; click()
    fireEvent.keyUp(window, { key: 'Shift' })
    expect(onAddWire).toHaveBeenLastCalledWith([{ x: 170, y: 70 }, { x: 250, y: 70 }])
  })
  it('inverts the current viewport, uses click position, and does not modify reviewed geometry', () => {
    const onAnalysisRegionChange = vi.fn()
    const onSelect = vi.fn()
    const onAddWall = vi.fn()
    const { container } = render(<DemoInterpretationCanvas width={400} height={300}
      draft={{ walls: [], rooms: [], symbols: [] }} tool="region" onSelect={onSelect} onAddWall={onAddWall}
      onAnalysisRegionChange={onAnalysisRegionChange} />)
    let pointer = { x: 160, y: 140 }
    const transform = { copy: () => transform, invert: () => transform,
      point: ({ x, y }) => ({ x: (x - 60) / 2, y: (y - 60) / 2 }) }
    const stage = { getPointerPosition: () => pointer, getAbsoluteTransform: () => transform }
    const click = () => act(() => container.querySelector('[data-konva="Stage"]').konvaProps.onClick({ target: { getStage: () => stage } }))
    click()
    pointer = { x: 760, y: 580 }
    click()
    expect(onAnalysisRegionChange).toHaveBeenCalledWith({ x: 50, y: 40, width: 300, height: 220 })
    expect(onSelect).not.toHaveBeenCalled()
    expect(onAddWall).not.toHaveBeenCalled()
  })
  it('cancels anchor with Escape, isolates new tool sessions, and exposes the immutable overlay', () => {
    const onAnalysisRegionChange = vi.fn()
    const props = { width: 400, height: 300, draft: { walls: [], rooms: [], symbols: [] }, tool: 'region', onAnalysisRegionChange }
    const { container, rerender } = render(<DemoInterpretationCanvas {...props} regionSession={0} />)
    let pointer = { x: 10, y: 20 }
    const transform = { copy: () => transform, invert: () => transform, point: (point) => point }
    const stage = { getPointerPosition: () => pointer, getAbsoluteTransform: () => transform }
    const click = () => act(() => container.querySelector('[data-konva="Stage"]').konvaProps.onClick({ target: { getStage: () => stage } }))
    click()
    fireEvent.keyDown(window, { key: 'Escape' })
    pointer = { x: 50, y: 60 }; click()
    expect(onAnalysisRegionChange).not.toHaveBeenCalled()
    rerender(<DemoInterpretationCanvas {...props} regionSession={1} />)
    pointer = { x: 100, y: 110 }; click()
    expect(onAnalysisRegionChange).not.toHaveBeenCalled()
    pointer = { x: 150, y: 160 }; click()
    expect(onAnalysisRegionChange).toHaveBeenCalledWith({ x: 100, y: 110, width: 50, height: 50 })
    rerender(<DemoInterpretationCanvas {...props} tool="select" analysisRegion={{ x: 100, y: 110, width: 50, height: 50 }} />)
    const overlay = container.querySelector('[data-name="drawing-region-outline"]').konvaProps
    expect(overlay).toMatchObject({ x: 100, y: 110, width: 50, height: 50, listening: false })
    expect(container.querySelector('[data-name="drawing-region-hit"]')).toBeNull()
  })
})
