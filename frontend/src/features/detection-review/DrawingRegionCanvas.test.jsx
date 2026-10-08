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
