import { useEffect, useState } from 'react'


function readHashRoute() {
  const hash=window.location.hash.slice(1)
  let route=hash.split('?')[0]
  if (/\/interpretation\/[1-9]\d*$/.test(route)) {
    const action=new URLSearchParams(hash.includes('?')?hash.slice(hash.indexOf('?')+1):'').get('measure')
    if(['view','scale','wiring','heights','wire-height','device-height','material-wire','material-wire-length','material-conduit-length','material-conductor-count','product','product-conductors','product-wire-length','product-conduit-length','product-wire','product-conduit'].includes(action)){
      route+='?measure='+action
      const target=new URLSearchParams(hash.slice(hash.indexOf('?')+1)).get('target')
      if(target && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(target))route+='&target='+encodeURIComponent(target)
      const targets=(new URLSearchParams(hash.slice(hash.indexOf('?')+1)).get('targets') || '').split(',').filter(id=>/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(id)).slice(0,2048)
      if(targets.length)route+='&targets='+encodeURIComponent(targets.join(','))
    }
  }
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
