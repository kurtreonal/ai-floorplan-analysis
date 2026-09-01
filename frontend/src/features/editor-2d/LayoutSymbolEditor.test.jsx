/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { normalizeCanonicalGeometry } from '../../geometry/canonicalGeometry.js'
import { LayoutSymbolEditor } from './LayoutSymbolEditor.jsx'
import fixtureData from '../../../../fixtures/canonical_geometry_v1.json'

const geometry = normalizeCanonicalGeometry(fixtureData)

afterEach(cleanup)

describe('layout symbol editor', () => {
  it('provides accessible detected/manual selection and authoritative metadata', () => {
    const onSelectSymbol = vi.fn()
    render(
      <LayoutSymbolEditor
        geometry={geometry}
        selectedSymbolId="detected:501"
        canEdit
        onSelectSymbol={onSelectSymbol}
        onGeometryChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('table', { name: /Canonical symbols/ })).toBeTruthy()
    expect(screen.getByText('Power outlet')).toBeTruthy()
    expect(screen.getByText('Wall light')).toBeTruthy()
    expect(screen.getByText('confirmed')).toBeTruthy()
    expect(screen.getByText('manually_added')).toBeTruthy()
    const buttons = screen.getAllByRole('button', { name: /Select/ })
    expect(buttons[0].getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(buttons[1])
    expect(onSelectSymbol).toHaveBeenCalledWith('manual:601')
  })

  it('moves with finite inclusive meter input through canonical geometry', () => {
    const onGeometryChange = vi.fn()
    render(
      <LayoutSymbolEditor
        geometry={geometry}
        selectedSymbolId="manual:601"
        canEdit
        onSelectSymbol={vi.fn()}
        onGeometryChange={onGeometryChange}
      />,
    )
    fireEvent.change(screen.getByLabelText('X position (meters)'), { target: { value: '6.4' } })
    fireEvent.change(screen.getByLabelText('Y position (meters)'), { target: { value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply position' }))
    const next = onGeometryChange.mock.calls[0][0]
    expect(next.symbols[1].position).toEqual({ x: 6.4, y: 0 })
    expect(next.symbols[0]).toEqual(geometry.symbols[0])
    expect(Object.isFrozen(next)).toBe(true)
  })

  it('preserves textual intermediate values and announces invalid bounds', () => {
    const onGeometryChange = vi.fn()
    render(
      <LayoutSymbolEditor
        geometry={geometry}
        selectedSymbolId="detected:501"
        canEdit
        onSelectSymbol={vi.fn()}
        onGeometryChange={onGeometryChange}
      />,
    )
    const x = screen.getByLabelText('X position (meters)')
    fireEvent.change(x, { target: { value: '-' } })
    expect(x.value).toBe('-')
    fireEvent.click(screen.getByRole('button', { name: 'Apply position' }))
    expect(screen.getByRole('alert').textContent).toMatch(/Enter X from 0/)
    expect(onGeometryChange).not.toHaveBeenCalled()
  })

  it('keeps Admin inspection-only and renders the empty state', () => {
    const { rerender } = render(
      <LayoutSymbolEditor
        geometry={geometry}
        selectedSymbolId="detected:501"
        canEdit={false}
        onSelectSymbol={vi.fn()}
        onGeometryChange={vi.fn()}
      />,
    )
    expect(screen.getByText('Inspection only')).toBeTruthy()
    expect(screen.queryByLabelText('X position (meters)')).toBeNull()
    const empty = structuredClone(fixtureData); empty.symbols = []
    rerender(
      <LayoutSymbolEditor
        geometry={normalizeCanonicalGeometry(empty)}
        selectedSymbolId={null}
        canEdit={false}
        onSelectSymbol={vi.fn()}
        onGeometryChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/contains no canonical symbols/)).toBeTruthy()
  })
})
