/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DetectionReviewCanvas } from './DetectionReviewCanvas.jsx'

vi.mock('react-konva', () => {
  const container = (name) => function MockContainer({ children, onClick }) {
    return <div data-konva={name} onClick={onClick}>{children}</div>
  }
  const shape = (name) => function MockShape() { return <span data-konva={name} /> }
  return {
    Stage: container('Stage'), Layer: container('Layer'), Group: container('Group'),
    Image: shape('Image'), Line: shape('Line'), Rect: shape('Rect'), Circle: shape('Circle'),
  }
})

afterEach(cleanup)

describe('detection review canvas', () => {
  it('uses four layers and keeps wall/symbol selection read-only', () => {
    const onSelect = vi.fn()
    const walls = [
      { id: 1, status: 'detected', raw_pixels: { start: { x: 0, y: 1 }, end: { x: 10, y: 1 } } },
      { id: 2, status: 'verified', raw_pixels: { start: { x: 0, y: 2 }, end: { x: 10, y: 2 } } },
    ]
    const symbols = [{
      id: 4, status: 'needs_review', center: { x: 4, y: 5 },
      bounding_box: { x_min: 2, y_min: 3, x_max: 8, y_max: 9 },
    }]
    const { container } = render(
      <DetectionReviewCanvas image={{}} imageWidth={100} imageHeight={80} walls={walls} symbols={symbols} selectedId={4} onSelect={onSelect} />,
    )
    expect(container.querySelectorAll('[data-konva="Layer"]')).toHaveLength(4)
    expect(container.querySelectorAll('[data-konva="Line"]')).toHaveLength(2)
    expect(container.querySelectorAll('[data-konva="Rect"]')).toHaveLength(2)
    fireEvent.click(container.querySelector('[data-konva="Group"]'))
    expect(onSelect).toHaveBeenCalledWith(4)
    expect(screen.getByText(/source pixel coordinates/)).toBeTruthy()
    expect(container.querySelector('[draggable]')).toBeNull()
  })
})
