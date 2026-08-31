export function parseProjectRoute(route) {
  if (route === '/app') {
    return { view: 'dashboard', projectId: null }
  }

  const layoutMatch = route.match(
    /^\/app\/projects\/([^/]+)\/floors\/([^/]+)\/layout$/,
  )
  if (layoutMatch) {
    const identifiers = layoutMatch.slice(1)
    if (!identifiers.every((value) => /^[1-9]\d*$/.test(value))) {
      return { view: 'invalid', projectId: null }
    }
    const [projectId, projectFloorId] = identifiers.map(Number)
    if (![projectId, projectFloorId].every(Number.isSafeInteger)) {
      return { view: 'invalid', projectId: null }
    }
    return { view: 'layout', projectId, projectFloorId }
  }

  const reviewMatch = route.match(
    /^\/app\/projects\/([^/]+)\/floor-plans\/([^/]+)\/detections\/([^/]+)$/,
  )
  if (reviewMatch) {
    const identifiers = reviewMatch.slice(1)
    if (!identifiers.every((value) => /^[1-9]\d*$/.test(value))) {
      return { view: 'invalid', projectId: null }
    }
    const [projectId, floorPlanId, processingJobId] = identifiers.map(Number)
    if (![projectId, floorPlanId, processingJobId].every(Number.isSafeInteger)) {
      return { view: 'invalid', projectId: null }
    }
    return { view: 'detection-review', projectId, floorPlanId, processingJobId }
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
  if (!Number.isSafeInteger(projectId) || projectId <= 0) throw new Error('Invalid project ID.')
  return `#/app/projects/${projectId}`
}

export function getLayoutHref(projectId, projectFloorId) {
  if (![projectId, projectFloorId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid layout route identifiers.')
  return `#/app/projects/${projectId}/floors/${projectFloorId}/layout`
}

export function getDetectionReviewHref(projectId, floorPlanId, processingJobId) {
  if (![projectId, floorPlanId, processingJobId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid detection review route identifiers.')
  return `#/app/projects/${projectId}/floor-plans/${floorPlanId}/detections/${processingJobId}`
}
