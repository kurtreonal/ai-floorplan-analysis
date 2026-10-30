import { useEffect, useState } from 'react'
import { normalizePreferences, preferenceKey, readPreferences } from './userPreferences.js'
import { PreferencesContext } from './useUserPreferences.js'
import { applicationDefaults } from '../../api/applicationDefaults.js'

export function UserPreferencesProvider({ userId, children, loadSharedDefaults = true }) {
  const [preferences, setPreferences] = useState(() => readPreferences(userId))
  const [storageError, setStorageError] = useState(null)
  const [defaultsReady,setDefaultsReady]=useState(!loadSharedDefaults)
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false)
  useEffect(() => {
    if (!loadSharedDefaults) return undefined
    const request=new AbortController()
    const timeout=setTimeout(()=>request.abort(),3000)
    let active=true
    applicationDefaults(null,request.signal).then(({settings})=>{
      if(!active)return
      let saved={}
      try{saved=JSON.parse(localStorage.getItem(preferenceKey(userId))) || {}}catch{/* Keep browser defaults if storage cannot be read. */}
      setPreferences(normalizePreferences({units:settings.display_units,snapping:settings.editor_snapping,
        blueprint:settings.show_blueprint,walls:settings.show_walls,symbols:settings.show_symbols,wiring:settings.show_wiring,...saved}))
    }).catch(()=>{/* Unavailable shared settings never prevent access to the editor. */}).finally(()=>{clearTimeout(timeout);if(active)setDefaultsReady(true)})
    return()=>{active=false;clearTimeout(timeout);request.abort()}
  },[userId,loadSharedDefaults])
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
  return <PreferencesContext.Provider value={{ preferences, updatePreferences, storageError, resolvedTheme: theme }}>
    <div className="studio-preferences-root" data-theme={theme}>{defaultsReady ? children:<p role="status">Opening workspace…</p>}</div>
  </PreferencesContext.Provider>
}
