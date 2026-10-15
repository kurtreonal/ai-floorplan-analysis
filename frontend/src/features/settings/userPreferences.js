export const DEFAULT_PREFERENCES = Object.freeze({
  theme: 'system', units: 'metric', snapping: true,
  blueprint: true, walls: true, symbols: true, wiring: true,
})

export function normalizePreferences(value) {
  const input = value && typeof value === 'object' ? value : {}
  return {
    theme: ['light', 'dark', 'system'].includes(input.theme) ? input.theme : 'system',
    units: ['metric', 'imperial'].includes(input.units) ? input.units : 'metric',
    ...Object.fromEntries(['snapping', 'blueprint', 'walls', 'symbols', 'wiring'].map(
      (key) => [key, typeof input[key] === 'boolean' ? input[key] : DEFAULT_PREFERENCES[key]],
    )),
  }
}

export function preferenceKey(userId) {
  return `ved:user-preferences:v1:${userId}`
}

export function readPreferences(userId) {
  try { return normalizePreferences(JSON.parse(localStorage.getItem(preferenceKey(userId)))) }
  catch { return { ...DEFAULT_PREFERENCES } }
}

export function formatDisplayLength(meters, units = 'metric', digits = 3) {
  if (!Number.isFinite(meters)) return 'Unavailable'
  return units === 'imperial' ? `${(meters / 0.3048).toFixed(digits)} ft` : `${meters.toFixed(digits)} m`
}
