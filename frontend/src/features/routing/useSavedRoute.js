import { useEffect, useState } from 'react'
import { routingRequest } from '../../api/routing.js'

export function useSavedRoute(projectId, layoutId) {
  const [state, setState] = useState(null)
  useEffect(() => {
    if (!layoutId) return undefined
    const controller = new AbortController()
    routingRequest(projectId, { signal: controller.signal }).then((record) => {
      if (!controller.signal.aborted) setState((current) => {
        const hasNewerRoute = current?.layoutId === layoutId && current.record
          && (!record || current.record.version_number > record.version_number)
        return hasNewerRoute ? current : { layoutId, record }
      })
    }).catch(() => {})
    return () => controller.abort()
  }, [projectId, layoutId])
  return [state && state.layoutId === layoutId ? state.record : null, (record) => setState({ layoutId, record })]
}
