/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('react-konva', () => {
  const container = (name) => function MockContainer({ children, ...props }) {
    return <div data-konva={name} data-name={props.name} ref={(node) => { if (node) node.konvaProps = props }} onClick={props.onClick}>{children}</div>
  }
  const shape = (name) => function MockShape({ text, ...props }) {
    return <span data-konva={name} {...props}>{text}</span>
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
    expect(onUpdateSymbol).toHaveBeenCalledWith(expect.objectContaining({ id: 'sym-0001', center: { x: 400, y: 0 } }))
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
    expect(screen.getByText(/Walls are rendered as centerlines with estimated thickness/)).toBeTruthy()
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
})
