import { API_BASE_URL } from './auth.js'

export async function workflowRequest(path, { method = 'GET', body, signal } = {}) {
  const multipart=body instanceof FormData
  const response = await fetch(`${API_BASE_URL}/api${path}`, {
    method, credentials: 'include', signal,
    ...(path.startsWith('/auth/') ? { cache: 'no-store' } : {}),
    headers: { Accept: 'application/json', ...(body && !multipart ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body:multipart?body:JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const message = data?.detail?.error?.message || (typeof data?.detail === 'string' ? data.detail : Array.isArray(data?.detail)?data.detail.map(x=>`${String(x.loc?.at(-1) || 'Field').replaceAll('_',' ')}: ${x.msg}`).join('. '):null)
    throw new Error(message || (response.status === 403 ? 'Your account cannot perform this action.' : 'This request could not be completed.'))
  }
  return response.status === 204 ? null : response.json()
}
