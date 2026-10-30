export function notify(message, kind = 'success') {
  window.dispatchEvent(new CustomEvent('ved:notification', { detail: { message, kind } }))
}
