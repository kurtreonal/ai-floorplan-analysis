/* @vitest-environment jsdom */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Viewer3DErrorBoundary } from './Viewer3DErrorBoundary.jsx'

let shouldBreak = true

function RecoverableViewer() {
  if (shouldBreak) throw new Error('private renderer detail')
  return <p>Viewer restored</p>
}

afterEach(() => {
  cleanup()
  shouldBreak = true
})

describe('3D viewer error isolation', () => {
  it('keeps surrounding application content and exposes only a safe fallback', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <div>
        <header>Protected application shell</header>
        <Viewer3DErrorBoundary projectId={15} title="3D canvas unavailable">
          <RecoverableViewer />
        </Viewer3DErrorBoundary>
      </div>,
    )
    expect(screen.getByText('Protected application shell')).toBeTruthy()
    expect(screen.getByRole('heading', { name: '3D canvas unavailable' })).toBeTruthy()
    expect(screen.getByRole('alert').textContent).not.toContain('private renderer detail')
    expect(screen.getByRole('link', { name: 'Back to project' }).getAttribute('href')).toBe('#/app/projects/15')
    shouldBreak = false
    fireEvent.click(screen.getByRole('button', { name: 'Try viewer again' }))
    expect(screen.getByText('Viewer restored')).toBeTruthy()
    console.error.mockRestore()
  })
})
