import { API_BASE_URL } from './auth.js'

export async function importMaterialPrices(file, selection, { signal } = {}) {
  const form = new FormData()
  form.append('file', file)
  if (selection) form.append('selection', JSON.stringify(selection))
  const response = await fetch(`${API_BASE_URL}/api/admin/materials/import/${selection ? 'apply' : 'preview'}`, {
    method: 'POST', credentials: 'include', signal, body: form, headers: { Accept: 'application/json' },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(response.status === 403 ? 'Only an Admin can import material prices.'
    : response.status === 401 ? 'Sign in again to import prices.' : body?.detail?.error?.message || 'Import unavailable. Preview again before retrying.')
  if (!body || !/^[a-f0-9]{64}$/.test(body.file_sha256) || (!selection && (!Array.isArray(body.rows) || !Array.isArray(body.issues)))
    || (selection && !['created', 'updated', 'unchanged'].every(key => Number.isInteger(body[key]) && body[key] >= 0))) {
    throw new Error('Invalid import response. No changes are confirmed.')
  }
  return body
}
