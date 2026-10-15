import { useUserPreferences } from './useUserPreferences.js'

export function UserSettingsPage() {
  const { preferences, updatePreferences, storageError } = useUserPreferences()
  return <section className="studio-panel studio-settings" aria-labelledby="user-settings-title">
    <span className="project-kicker mono">YOUR WORKSPACE</span>
    <h1 id="user-settings-title">User settings</h1>
    <p>Saved for your account in this browser. Project geometry and engineering measurements are unchanged.</p>
    {storageError && <p role="alert">{storageError}</p>}
    <fieldset><legend>Appearance &amp; measurements</legend>
      <label className="studio-field">Theme<select value={preferences.theme} onChange={(event) => updatePreferences({ theme: event.target.value })}>
        <option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option>
      </select></label>
      <label className="studio-field">Display units<select value={preferences.units} onChange={(event) => updatePreferences({ units: event.target.value })}>
        <option value="metric">Metric (m)</option><option value="imperial">Imperial (ft)</option>
      </select></label>
      <small>Display lengths only; coordinates and saved measurements remain in their original units.</small>
    </fieldset>
    <fieldset><legend>Editor defaults</legend>
      <label><input type="checkbox" checked={preferences.snapping} onChange={(event) => updatePreferences({ snapping: event.target.checked })} />Enable drawing and device magnets</label>
      <p>Layer defaults apply when opening an editor, not to an editor already in use.</p>
      {['blueprint', 'symbols', 'walls', 'wiring'].map((key) => <label key={key}>
        <input type="checkbox" checked={preferences[key]} onChange={(event) => updatePreferences({ [key]: event.target.checked })} />Show {key}
      </label>)}
    </fieldset>
    <p role="status">Preferences apply automatically.</p>
  </section>
}
