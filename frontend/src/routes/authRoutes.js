export function getProtectedRouteRedirect(status) {
  return status === 'unauthenticated'
    ? '#/signin?reason=authentication-required'
    : null
}
