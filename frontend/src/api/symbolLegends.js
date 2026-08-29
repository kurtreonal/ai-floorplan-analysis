import { API_BASE_URL } from './auth.js'

const GENERIC_ERROR = 'The approved symbol classes could not be loaded.'

export class SymbolLegendApiError extends Error {
  constructor(message = GENERIC_ERROR, status = 0, code = null) {
    super(message)
    this.name = 'SymbolLegendApiError'
    this.status = status
    this.code = code
  }
}

function positiveId(value) {
  return Number.isSafeInteger(value) && value > 0
}

function validLegend(legend) {
  return legend
    && JSON.stringify(Object.keys(legend).sort()) === JSON.stringify(['class_id', 'id', 'name'])
    && positiveId(legend.id)
    && Number.isInteger(legend.class_id)
    && legend.class_id >= 0
    && typeof legend.name === 'string'
    && legend.name.length > 0
    && legend.name.length <= 255
}

async function safeError(response) {
  try {
    const payload = await response.json()
    const error = payload?.detail?.error
    return {
      code: typeof error?.code === 'string' ? error.code : null,
      message: typeof error?.message === 'string' ? error.message : GENERIC_ERROR,
    }
  } catch {
    return { code: null, message: GENERIC_ERROR }
  }
}

export async function fetchSymbolLegends({ signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/symbol-legends`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new SymbolLegendApiError()
  }
  if (!response.ok) {
    const error = await safeError(response)
    throw new SymbolLegendApiError(error.message, response.status, error.code)
  }
  try {
    const payload = await response.json()
    if (!Array.isArray(payload) || !payload.every(validLegend)) throw new SymbolLegendApiError()
    return payload
  } catch (error) {
    if (error instanceof SymbolLegendApiError) throw error
    throw new SymbolLegendApiError()
  }
}
