export function fitCanvas(sourceWidth, sourceHeight, availableWidth, availableHeight) {
  if (![sourceWidth, sourceHeight, availableWidth, availableHeight].every(
    (value) => Number.isFinite(value) && value > 0,
  )) throw new Error('Canvas dimensions must be positive finite numbers.')
  const scale = Math.min(availableWidth / sourceWidth, availableHeight / sourceHeight)
  return { scale, width: sourceWidth * scale, height: sourceHeight * scale }
}

export function wallLinePoints(wall) {
  const { start, end } = wall.raw_pixels
  if (![start.x, start.y, end.x, end.y].every((value) => Number.isFinite(value) && value >= 0)) {
    throw new Error('Wall coordinates are invalid.')
  }
  return [start.x, start.y, end.x, end.y]
}

export function symbolRectangle(symbol) {
  const { x_min: x, y_min: y, x_max, y_max } = symbol.bounding_box
  if (![x, y, x_max, y_max].every((value) => Number.isFinite(value) && value >= 0)
    || x_max < x || y_max < y) throw new Error('Symbol coordinates are invalid.')
  return { x, y, width: x_max - x, height: y_max - y }
}

export function stagePointToSource(pointer, scale, imageWidth, imageHeight) {
  if (!pointer || !Number.isFinite(pointer.x) || !Number.isFinite(pointer.y)
    || !Number.isFinite(scale) || scale <= 0
    || !Number.isFinite(imageWidth) || imageWidth <= 0
    || !Number.isFinite(imageHeight) || imageHeight <= 0) {
    throw new Error('Placement coordinates are invalid.')
  }
  const x = pointer.x / scale
  const y = pointer.y / scale
  if (x < 0 || y < 0 || x > imageWidth || y > imageHeight) {
    throw new Error('Placement coordinates are outside the image.')
  }
  return {
    x: Number(x.toFixed(6)),
    y: Number(y.toFixed(6)),
  }
}

export function detectedSelectionKey(id) {
  return `detected:${id}`
}

export function manualSelectionKey(id) {
  return `manual:${id}`
}

export const STATUS_PRESENTATION = Object.freeze({
  detected: { label: 'Detected — awaiting Designer review', color: '#146c94', dash: [] },
  needs_review: { label: 'Needs review — below threshold', color: '#b54708', dash: [8, 4] },
  verified: { label: 'Verified', color: '#297a4a', dash: [] },
})

export const REVIEW_PRESENTATION = Object.freeze({
  pending: { label: 'Pending Designer decision', color: null, dash: null },
  confirmed: { label: 'Confirmed by Designer', color: '#297a4a', dash: [] },
  deleted: { label: 'Rejected by Designer', color: '#6b7280', dash: [5, 4] },
})

export const MANUAL_PRESENTATION = Object.freeze({
  label: 'Manually added',
  color: '#7c3aed',
  dash: [],
})

export function symbolPresentation(symbol) {
  const decision = symbol.review?.decision || 'pending'
  const reviewStyle = REVIEW_PRESENTATION[decision]
  if (!reviewStyle) throw new Error('Symbol review decision is invalid.')
  return decision === 'pending' ? STATUS_PRESENTATION[symbol.status] : reviewStyle
}
