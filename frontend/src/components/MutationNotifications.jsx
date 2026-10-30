import { useEffect, useState } from 'react'
import { CheckCircle2, AlertCircle, X } from 'lucide-react'
import { API_BASE_URL } from '../api/auth.js'
import './notifications.css'
import { notify } from './notifications.js'

function actionMessage(path, method) {
  if (/\/auth\/|\/notifications/.test(path)) return null
  if (/\/workspace-reset\/\d+\/cancel$/.test(path)) return 'Reset cancelled. Workspace data kept.'
  if (/\/workspace-reset$/.test(path)) return 'Reset scheduled. You have five minutes to cancel.'
  if (/\/client\/projects\/\d+\/floor-plans$/.test(path)) return 'Floor plan sent to Admin.'
  if (/\/client\/projects$/.test(path) && method==='POST') return 'Project request sent to Admin.'
  if (/\/floor-plans\/\d+\/name$/.test(path)) return 'Floor-plan name saved.'
  if (/\/floors\/\d+$/.test(path) && method==='PATCH') return 'Floor name saved.'
  if (/\/floors$/.test(path) && method==='POST') return 'Floor added.'
  if (/\/item-assignments\/materials$/.test(path)) return 'Material choices saved. BOM updated.'
  if (/\/preview|\/bom\/|\/draft-preview|\/heartbeat|\/poll/.test(path)) return null
  if (/\/approval$/.test(path)) return 'Approved versions published to the client.'
  if (/\/assignment$/.test(path)) return 'Project assignment saved.'
  if (/\/submission$/.test(path)) return 'Saved draft submitted to Admin.'
  if (/\/draft-submissions\//.test(path)) return 'Draft review decision saved.'
  if (/\/client-pricing$/.test(path) && method === 'DELETE') return 'Client pricing removed. Saved estimates are unchanged.'
  if (/\/admin\/accounts/.test(path)) return method === 'DELETE' ? 'User access removed.' : method === 'POST' ? 'User account created.' : 'User changes saved.'
  if (/\/process|\/interpretation.*jobs|\/drawing-selection/.test(path)) return 'Analysis request accepted.'
  if (/\/symbol-legends/.test(path)) return 'Legend changes saved.'
  if (/\/prices|\/pricing|\/materials|\/assemblies/.test(path)) return 'Material pricing updated.'
  if (/\/application-defaults/.test(path)) return 'Shared defaults saved.'
  if (/\/measurement|\/scale|\/elevation/.test(path)) return 'Plan settings saved.'
  if (/\/reviews|\/review$/.test(path)) return 'Draft changes saved.'
  if (/\/projects(?:\/\d+)?$/.test(path)) return method === 'DELETE' ? 'Project removed from active projects.' : method === 'POST' ? 'Project created.' : 'Project details saved.'
  return 'Changes saved.'
}

export function MutationNotifications() {
  const [items, setItems] = useState([])
  useEffect(() => {
    const timers = new Set()
    const receive = event => {
      if (!event.detail?.message) return
      const id = crypto.randomUUID()
      setItems(current => [...current.slice(-2), { ...event.detail, id }])
      const timer = setTimeout(() => { setItems(current => current.filter(x => x.id !== id)); timers.delete(timer) }, 5500)
      timers.add(timer)
    }
    window.addEventListener('ved:notification', receive)
    // Observe existing API writes without altering their bodies, responses,
    // retries or per-form errors. No provider/third-party request is observed.
    const original = window.fetch
    const origin = new URL(API_BASE_URL || '/', window.location.origin).origin
    const observed = async (input, options) => {
      const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, window.location.origin)
      const method = (options?.method || input?.method || 'GET').toUpperCase()
      const message = url.origin === origin && url.pathname.startsWith('/api/') && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) ? actionMessage(url.pathname, method) : null
      try {
        const response = await original(input, options)
        if (message) notify(response.ok ? message : 'Changes were not saved. See the page for details.', response.ok ? 'success' : 'error')
        return response
      } catch (error) {
        if (message && error.name !== 'AbortError') notify('Connection interrupted. Your changes may need to be retried.', 'error')
        throw error
      }
    }
    window.fetch = observed
    return () => { window.removeEventListener('ved:notification', receive); timers.forEach(clearTimeout); if (window.fetch === observed) window.fetch = original }
  }, [])
  return <div className="ved-notifications" aria-live="polite" aria-atomic="false">{items.map(item => <div className={`ved-notification ved-notification-${item.kind}`} key={item.id} role="status">{item.kind === 'error' ? <AlertCircle size={18}/> : <CheckCircle2 size={18}/>}<span>{item.message}</span><button type="button" aria-label="Dismiss notification" onClick={() => setItems(current => current.filter(x => x.id !== item.id))}><X size={16}/></button></div>)}</div>
}
