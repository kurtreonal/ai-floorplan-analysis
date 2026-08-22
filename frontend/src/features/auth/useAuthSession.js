import { useCallback, useEffect, useState } from 'react'

import { endLocalSession, fetchCurrentUser } from '../../api/auth.js'


const DISABLED_SESSION = {
  status: 'unauthenticated',
  user: null,
}


export function useAuthSession({ enabled = true } = {}) {
  const [refreshKey, setRefreshKey] = useState(0)
  const [session, setSession] = useState({
    status: 'loading',
    user: null,
  })
  const [signOutState, setSignOutState] = useState({
    isSigningOut: false,
    error: null,
  })

  useEffect(() => {
    if (!enabled) {
      return undefined
    }

    const controller = new AbortController()

    async function restoreSession() {
      setSession({ status: 'loading', user: null })

      try {
        const user = await fetchCurrentUser({ signal: controller.signal })
        setSession({
          status: user ? 'authenticated' : 'unauthenticated',
          user,
        })
      } catch (error) {
        if (error.name !== 'AbortError') {
          setSession({ status: 'error', user: null })
        }
      }
    }

    restoreSession()
    return () => controller.abort()
  }, [enabled, refreshKey])

  const retry = useCallback(() => {
    setRefreshKey((currentKey) => currentKey + 1)
  }, [])

  const signOut = useCallback(async () => {
    setSignOutState({ isSigningOut: true, error: null })

    try {
      await endLocalSession()
      setSession({ status: 'unauthenticated', user: null })
      setSignOutState({ isSigningOut: false, error: null })
      window.location.replace('#/signin')
    } catch {
      setSignOutState({
        isSigningOut: false,
        error: 'We couldn’t sign you out. Please try again.',
      })
    }
  }, [])

  return {
    ...(enabled ? session : DISABLED_SESSION),
    ...signOutState,
    retry,
    signOut,
  }
}
