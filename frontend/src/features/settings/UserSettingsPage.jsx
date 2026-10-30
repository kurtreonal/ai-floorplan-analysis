import { useUserPreferences } from './useUserPreferences.js'
import { AdminDefaults } from '../admin/AdminDefaults.jsx'
import { AccountSignInSettings } from './AccountSignInSettings.jsx'
import { AdminUsers } from '../admin/AdminUsers.jsx'
import { AdminWorkspaceReset } from '../admin/AdminWorkspaceReset.jsx'
import { Button } from '../../components/ui/button.jsx'
import { useState } from 'react'

export function UserSettingsPage({isAdmin=false}) {
  const { preferences, updatePreferences, storageError } = useUserPreferences()
  const [section, setSection] = useState('account')
  return <section className="studio-panel studio-settings" aria-labelledby="user-settings-title">
    <span className="project-kicker mono">{isAdmin ? 'ADMINISTRATION':'YOUR WORKSPACE'}</span>
    <h1 id="user-settings-title">{isAdmin ? 'Admin settings':'User settings'}</h1>
    <p>{isAdmin ? 'Shared defaults for new work, account security and personal preferences.':'Manage your sign-in methods and workspace preferences.'}</p>
    {storageError && <p role="alert">{storageError}</p>}
    <nav className="account-settings-tabs" aria-label="Settings sections"><Button variant={section === 'account' ? 'default' : 'outline'} onClick={() => setSection('account')} aria-pressed={section === 'account'}>Sign-in methods</Button><Button variant={section === 'preferences' ? 'default' : 'outline'} onClick={() => setSection('preferences')} aria-pressed={section === 'preferences'}>Workspace</Button>{isAdmin && <><Button variant={section === 'users' ? 'default' : 'outline'} onClick={() => setSection('users')} aria-pressed={section === 'users'}>Users</Button><Button variant={section === 'defaults' ? 'default' : 'outline'} onClick={() => setSection('defaults')} aria-pressed={section === 'defaults'}>Shared defaults</Button></>}{isAdmin && <Button variant={section === 'workspace-data' ? 'default' : 'outline'} onClick={() => setSection('workspace-data')} aria-pressed={section === 'workspace-data'}>Workspace data</Button>}</nav>
    {isAdmin && section === 'users' && <AdminUsers/>}
    {isAdmin && section === 'defaults' && <AdminDefaults/>}
    {isAdmin && section === 'workspace-data' && <AdminWorkspaceReset/>}
    {section === 'account' && <AccountSignInSettings/>}
    <div hidden={section !== 'preferences'}>
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
    </div>
  </section>
}
