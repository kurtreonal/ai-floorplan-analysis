const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
const configuredAuthEnabled = import.meta.env.VITE_AUTH_ENABLED?.trim().toLowerCase()

export const AUTH_ENABLED = configuredAuthEnabled === 'true'

if (AUTH_ENABLED && !configuredApiBaseUrl) {
  throw new Error('VITE_API_BASE_URL is required when authentication is enabled.')
}

export const API_BASE_URL = (configuredApiBaseUrl || '').replace(/\/+$/, '')

export const AUTH_LOGIN_URL = `${API_BASE_URL}/api/auth/login`
export const AUTH_ME_URL = `${API_BASE_URL}/api/auth/me`
export const AUTH_LOGOUT_URL = `${API_BASE_URL}/api/auth/logout`

export function beginOAuthSignIn(location = window.location) {
  location.assign(AUTH_LOGIN_URL)
}

export async function fetchCurrentUser({ signal } = {}) {
  const response = await fetch(AUTH_ME_URL, {
    credentials: 'include',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  if (response.status === 401) {
    return null
  }

  if (!response.ok) {
    throw new Error('The authentication service is unavailable.')
  }

  return response.json()
}

export async function endLocalSession() {
  const response = await fetch(AUTH_LOGOUT_URL, {
    method: 'POST',
    credentials: 'include',
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error('The sign-out service is unavailable.')
  }
}
