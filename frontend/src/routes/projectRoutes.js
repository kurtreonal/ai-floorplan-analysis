export function parseProjectRoute(route) {
  if (route === '/app') {
    return { view: 'dashboard', projectId: null }
  }

  const match = route.match(/^\/app\/projects\/([^/]+)$/)
  if (!match || !/^[1-9]\d*$/.test(match[1])) {
    return { view: 'invalid', projectId: null }
  }

  const projectId = Number(match[1])
  if (!Number.isSafeInteger(projectId)) {
    return { view: 'invalid', projectId: null }
  }

  return { view: 'project', projectId }
}

export function getProjectHref(projectId) {
  return `#/app/projects/${projectId}`
}
