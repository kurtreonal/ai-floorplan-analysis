import { useEffect, useState } from 'react'
import { normalizePreferences, preferenceKey, readPreferences } from './userPreferences.js'
import { PreferencesContext } from './useUserPreferences.js'

export function UserPreferencesProvider({ userId, children }) {
  const [preferences, setPreferences] = useState(() => readPreferences(userId))
  const [storageError, setStorageError] = useState(null)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)')
    const change = (event) => setSystemDark(event.matches)
    query?.addEventListener('change', change)
    return () => query?.removeEventListener('change', change)
  }, [])
  function updatePreferences(patch) {
    const next = normalizePreferences({ ...preferences, ...patch })
    setPreferences(next)
    try {
      localStorage.setItem(preferenceKey(userId), JSON.stringify(next))
      setStorageError(null)
    } catch { setStorageError('Preferences apply for this session but could not be saved in this browser.') }
  }
  const theme = preferences.theme === 'system' ? (systemDark ? 'dark' : 'light') : preferences.theme
  return <PreferencesContext.Provider value={{ preferences, updatePreferences, storageError }}>
    <div className="studio-preferences-root" data-theme={theme}>{children}</div>
  </PreferencesContext.Provider>
}
