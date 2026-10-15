/* @vitest-environment jsdom */
import { useEffect, useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ViewportFrame } from './ViewportFrame.jsx'
import { WorkspacePanel } from './WorkspacePanel.jsx'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('keeps mounted viewport state through fallback fullscreen, Escape and panel close/reopen', async () => {
  const mounted = vi.fn(), unmounted = vi.fn()
  function Editor() {
    const [value, setValue] = useState('saved position')
    useEffect(() => { mounted(); return unmounted }, [])
    return <input aria-label="Draft position" value={value} onChange={(event) => setValue(event.target.value)} />
  }
  render(<ViewportFrame title="2D editor" status="Unsaved changes"><WorkspacePanel title="Inspector"><Editor /></WorkspacePanel></ViewportFrame>)
  fireEvent.change(screen.getByLabelText('Draft position'), { target: { value: 'edited position' } })
  fireEvent.click(screen.getByRole('button', { name: 'Fullscreen 2D editor' }))
  await waitFor(() => expect(document.querySelector('.is-expanded')).toBeTruthy())
  expect(screen.getByRole('status').textContent).toBe('Unsaved changes')
  fireEvent.click(screen.getByRole('button', { name: 'Close Inspector' }))
  expect(screen.queryByRole('textbox')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Reopen Inspector' }))
  expect(screen.getByLabelText('Draft position').value).toBe('edited position')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(document.querySelector('.is-expanded')).toBeNull()
  expect(document.body.style.overflow).toBe('')
  expect(mounted).toHaveBeenCalledTimes(1)
  expect(unmounted).not.toHaveBeenCalled()
})

it('uses native fullscreen when available and restores controls on external exit', async () => {
  const request = vi.fn().mockResolvedValue(undefined)
  const view = render(<ViewportFrame title="3D viewer"><p>Same canvas</p></ViewportFrame>)
  const frame = screen.getByRole('region', { name: '3D viewer' })
  frame.requestFullscreen = request
  fireEvent.click(screen.getByRole('button', { name: 'Fullscreen 3D viewer' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button', { name: 'Exit fullscreen' })).toBeTruthy()
  fireEvent(document, new Event('fullscreenchange'))
  expect(screen.getByRole('button', { name: 'Fullscreen 3D viewer' })).toBeTruthy()
  view.unmount()
  expect(document.body.style.overflow).toBe('')
})
