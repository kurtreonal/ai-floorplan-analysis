/* @vitest-environment jsdom */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { UserPreferencesProvider } from './UserPreferences.jsx'
import { UserSettingsPage } from './UserSettingsPage.jsx'
import { formatDisplayLength, normalizePreferences, preferenceKey } from './userPreferences.js'
vi.mock('../../api/applicationDefaults.js',()=>({applicationDefaults:vi.fn(async()=>({settings:{display_units:'metric',editor_snapping:true,show_blueprint:true,show_walls:true,show_symbols:true,show_wiring:true},revision:0,writable:true}))}))

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks() })
const page = (id) => <UserPreferencesProvider key={id} userId={id}><UserSettingsPage /></UserPreferencesProvider>

it('saves validated preferences per user and restores them after reload', async () => {
  const view = render(page(10))
  await screen.findByLabelText('Theme')
  fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'dark' } })
  fireEvent.change(screen.getByLabelText('Display units'), { target: { value: 'imperial' } })
  fireEvent.click(screen.getByLabelText('Show walls'))
  expect(document.querySelector('[data-theme]').dataset.theme).toBe('dark')
  expect(JSON.parse(localStorage.getItem(preferenceKey(10)))).toMatchObject({ theme: 'dark', units: 'imperial', walls: false })
  view.rerender(page(11))
  await screen.findByLabelText('Theme')
  expect(screen.getByLabelText('Theme').value).toBe('system')
  expect(screen.getByLabelText('Show walls').checked).toBe(true)
  view.rerender(page(10))
  await screen.findByLabelText('Theme')
  expect(screen.getByLabelText('Display units').value).toBe('imperial')
  expect(screen.getByLabelText('Show walls').checked).toBe(false)
})

it('tracks system theme changes and cleans up the listener', () => {
  let changed
  const removeEventListener = vi.fn()
  vi.spyOn(window, 'matchMedia', 'get').mockReturnValue(() => ({ matches: false, addEventListener: (_, cb) => { changed = cb }, removeEventListener }))
  const view = render(page(1))
  act(() => changed({ matches: true }))
  expect(document.querySelector('[data-theme]').dataset.theme).toBe('dark')
  view.unmount()
  expect(removeEventListener).toHaveBeenCalled()
})

it('handles corrupted or unavailable storage without changing engineering data', async () => {
  localStorage.setItem(preferenceKey(1), '{bad')
  render(page(1))
  await screen.findByLabelText('Theme')
  expect(screen.getByLabelText('Theme').value).toBe('system')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  fireEvent.change(screen.getByLabelText('Theme'), { target: { value: 'dark' } })
  expect(screen.getByRole('alert').textContent).toContain('could not be saved')
  expect(formatDisplayLength(0.3048, 'imperial')).toBe('1.000 ft')
  expect(normalizePreferences({ theme: 'invalid', walls: 'false' })).toMatchObject({ theme: 'system', walls: true })
})
