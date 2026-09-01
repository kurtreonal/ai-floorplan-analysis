/* @vitest-environment jsdom */

import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { CanonicalLayoutCanvas } from './CanonicalLayoutCanvas.jsx'
import { LAYOUT_LAYER_NAMES } from './layoutLayers.js'
import fixtureData from '../../../../fixtures/canonical_geometry_v1.json'

vi.mock('react-konva', () => {
  const container = (kind) => function MockContainer(props) {
    const { children, name, visible = true, draggable = false, onClick } = props
    return (
      <div
        ref={(node) => { if (node) node.konvaProps = props }}
        data-konva={kind}
        name={name}
        data-visible={String(visible)}
        data-draggable={String(draggable)}
        onClick={onClick}
      >
        {children}
      </div>
    )
  }
  const shape = (kind) => function MockShape(props) {
    return <span data-konva={kind} data-fill={props.fill} name={props.name} />
  }
  return {
    Stage: container('Stage'), Layer: container('Layer'), Group: container('Group'),
    Image: shape('Image'), Line: shape('Line'), Rect: shape('Rect'),
    Circle: shape('Circle'), Text: shape('Text'),
  }
})

const fixture = fixtureData
const visible = { blueprint: true, walls: true, rooms: true, symbols: true, routes: true }

afterEach(cleanup)

describe('canonical layout canvas', () => {
  it('always mounts exactly six stable layers in the required order with isolated content', () => {
    const geometry = normalizeCanonicalGeometry(fixture)
    const before = JSON.stringify(geometry)
    const { container, rerender } = render(<CanonicalLayoutCanvas geometry={geometry} blueprintImage={{}} visibility={visible} />)
    const layers = [...container.querySelectorAll('[data-konva="Layer"]')]
    expect(layers).toHaveLength(6)
    expect(layers.map((layer) => layer.getAttribute('name'))).toEqual(LAYOUT_LAYER_NAMES)
    expect(layers[0].querySelectorAll('[data-konva="Image"]')).toHaveLength(1)
    expect(layers[1].querySelectorAll('[data-konva="Line"]')).toHaveLength(1)
    expect(layers[2].querySelectorAll('[data-konva="Line"]')).toHaveLength(1)
    expect(layers[3].querySelectorAll('[data-konva="Group"]')).toHaveLength(2)
    expect([...layers[3].querySelectorAll('[data-konva="Circle"]')].map(
      (node) => node.getAttribute('data-fill'),
    )).toEqual(['#d9480f', '#7c3aed'])
    expect(layers[4].querySelectorAll('[data-konva="Line"]')).toHaveLength(1)
    expect(layers[5].children).toHaveLength(0)
    expect([...layers[3].querySelectorAll('[data-konva="Group"]')].every(
      (node) => node.getAttribute('data-draggable') === 'false',
    )).toBe(true)
    rerender(<CanonicalLayoutCanvas geometry={geometry} blueprintImage={{}} visibility={{ ...visible, walls: false }} />)
    expect(container.querySelector('[name="walls"]')).toBeTruthy()
    expect(container.querySelector('[name="walls"]').getAttribute('data-visible')).toBe('false')
    expect(JSON.stringify(geometry)).toBe(before)
  })

  it('selects both symbol sources, enables only Designer dragging, clamps, and emits canonical meters', () => {
    const geometry = normalizeCanonicalGeometry(fixture)
    const onSelectSymbol = vi.fn()
    const onMoveSymbol = vi.fn()
    const { container, rerender } = render(
      <CanonicalLayoutCanvas
        geometry={geometry}
        blueprintImage={null}
        visibility={visible}
        selectedSymbolId="detected:501"
        canEdit
        onSelectSymbol={onSelectSymbol}
        onMoveSymbol={onMoveSymbol}
      />,
    )
    const groups = [...container.querySelectorAll('[data-konva="Group"]')]
    expect(groups).toHaveLength(2)
    expect(groups.every((node) => node.getAttribute('data-draggable') === 'true')).toBe(true)
    fireEvent.click(groups[0])
    fireEvent.click(groups[1])
    expect(onSelectSymbol.mock.calls.map(([id]) => id)).toEqual(['detected:501', 'manual:601'])
    expect(container.querySelector('[name="selection-ui"] [name="selected-symbol-outline"]')).toBeTruthy()

    let position = { x: 700, y: -10 }
    const target = {
      position: vi.fn((next) => { if (next) position = next; return position }),
    }
    groups[1].konvaProps.onDragEnd({ target })
    expect(position).toEqual({ x: 640, y: 0 })
    expect(onMoveSymbol).toHaveBeenCalledWith('manual:601', { x: 6.4, y: 0 })

    rerender(
      <CanonicalLayoutCanvas
        geometry={geometry}
        blueprintImage={null}
        visibility={{ ...visible, symbols: false }}
        selectedSymbolId="detected:501"
        canEdit
        editDisabled
        onSelectSymbol={onSelectSymbol}
        onMoveSymbol={onMoveSymbol}
      />,
    )
    expect(container.querySelector('[name="selection-ui"] [name="selected-symbol-outline"]')).toBeNull()
    expect([...container.querySelectorAll('[data-konva="Group"]')].every(
      (node) => node.getAttribute('data-draggable') === 'false',
    )).toBe(true)
  })

  it('keeps all six layers mounted for empty collections and no blueprint', () => {
    const empty = structuredClone(fixture)
    for (const key of ['walls', 'rooms', 'symbols', 'routes']) empty[key] = []
    const { container } = render(<CanonicalLayoutCanvas geometry={normalizeCanonicalGeometry(empty)} blueprintImage={null} visibility={visible} />)
    expect(container.querySelectorAll('[data-konva="Layer"]')).toHaveLength(6)
    expect(container.querySelector('[name="routes"]')).toBeTruthy()
    expect(container.querySelector('[name="blueprint"] [data-konva="Rect"]')).toBeTruthy()
  })
})
