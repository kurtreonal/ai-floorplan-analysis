import { useEffect, useState } from 'react'


function readHashRoute() {
  const route = window.location.hash.slice(1).split('?')[0]
  return route.startsWith('/') ? route : '/'
}

export function useHashRoute() {
  const [route, setRoute] = useState(readHashRoute)

  useEffect(() => {
    function handleHashChange() {
      setRoute(readHashRoute())
    }

    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  return route
}
