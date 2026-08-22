import { useCallback, useEffect, useState } from 'react'

import { fetchCurrentUser } from '../../api/auth.js'


export function useAuthSession() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [session, setSession] = useState({
    status: 'loading',
    user: null,
  })

  useEffect(() => {
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
  }, [refreshKey])

  const retry = useCallback(() => {
    setRefreshKey((currentKey) => currentKey + 1)
  }, [])

  return { ...session, retry }
}
