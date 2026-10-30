export function parseProjectRoute(route) {
  const query=new URLSearchParams(route.includes('?') ? route.slice(route.indexOf('?')+1):'')
  route=route.split('?')[0]
  const measurementAction=['view','scale','wiring','heights','wire-height','device-height','material-wire','material-wire-length','material-conduit-length','material-conductor-count','product','product-conductors','product-wire-length','product-conduit-length','product-wire','product-conduit'].includes(query.get('measure')) ? query.get('measure'):null
  const measurementTarget=/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(query.get('target') || '') ? query.get('target'):null
  const measurementTargets=(query.get('targets') || '').split(',').filter(id=>/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(id)).slice(0,2048)
  if (route === '/app/settings') return { view: 'settings', projectId: null }
  const clientProjects = route.match(/^\/app\/clients\/([^/]+)\/projects$/)
  if (clientProjects) {
    try { return { view: 'dashboard', projectId: null, section: 'projects', clientFilter: decodeURIComponent(clientProjects[1]) } }
    catch { return { view: 'invalid', projectId: null } }
  }
  if (route === '/app/clients' || route === '/app/projects') {
    return { view: 'dashboard', projectId: null, section: route === '/app/clients' ? 'clients' : 'projects' }
  }
  if (route === '/app') {
    return { view: 'dashboard', projectId: null }
  }

  const estimateMatch = route.match(/^\/app\/projects\/([1-9]\d*)\/estimates$/)
  if (estimateMatch && Number.isSafeInteger(Number(estimateMatch[1]))) {
    return { view: 'estimates', projectId: Number(estimateMatch[1]) }
  }

  const viewer3dMatch = route.match(
    /^\/app\/projects\/([^/]+)\/floors\/([^/]+)\/viewer-3d$/,
  )
  if (viewer3dMatch) {
    const identifiers = viewer3dMatch.slice(1)
    if (!identifiers.every((value) => /^[1-9]\d*$/.test(value))) {
      return { view: 'invalid', projectId: null }
    }
    const [projectId, projectFloorId] = identifiers.map(Number)
    if (![projectId, projectFloorId].every(Number.isSafeInteger)) {
      return { view: 'invalid', projectId: null }
    }
    return { view: 'viewer-3d', projectId, projectFloorId }
  }

  const interpretationMatch = route.match(
    /^\/app\/projects\/([^/]+)\/floors\/([^/]+)\/floor-plans\/([^/]+)\/interpretation\/([^/]+)$/,
  )
  if (interpretationMatch) {
    const identifiers = interpretationMatch.slice(1)
    if (!identifiers.every((value) => /^[1-9]\d*$/.test(value))) {
      return { view: 'invalid', projectId: null }
    }
    const [projectId, projectFloorId, floorPlanId, processingJobId] = identifiers.map(Number)
    if (![projectId, projectFloorId, floorPlanId, processingJobId].every(Number.isSafeInteger)) {
      return { view: 'invalid', projectId: null }
    }
    return {
      view: 'demo-interpretation', projectId, projectFloorId, floorPlanId, processingJobId,
      ...(measurementAction ? {measurementAction}:{}),
      ...(measurementTarget ? {measurementTarget}:{}),
      ...(measurementTargets.length ? {measurementTargets}:{}),
    }
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

export function getEstimateHref(projectId) {
  return `${getProjectHref(projectId)}/estimates`
}

export function getLayoutHref(projectId, projectFloorId) {
  if (![projectId, projectFloorId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid layout route identifiers.')
  return `#/app/projects/${projectId}/floors/${projectFloorId}/layout`
}

export function getViewer3dHref(projectId, projectFloorId) {
  if (![projectId, projectFloorId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid 3D viewer route identifiers.')
  return `#/app/projects/${projectId}/floors/${projectFloorId}/viewer-3d`
}

export function getDetectionReviewHref(projectId, floorPlanId, processingJobId) {
  if (![projectId, floorPlanId, processingJobId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid detection review route identifiers.')
  return `#/app/projects/${projectId}/floor-plans/${floorPlanId}/detections/${processingJobId}`
}

export function getDemoInterpretationHref(projectId, projectFloorId, floorPlanId, processingJobId) {
  if (![projectId, projectFloorId, floorPlanId, processingJobId].every(
    (value) => Number.isSafeInteger(value) && value > 0,
  )) throw new Error('Invalid demo interpretation route identifiers.')
  return `#/app/projects/${projectId}/floors/${projectFloorId}/floor-plans/${floorPlanId}/interpretation/${processingJobId}`
}
