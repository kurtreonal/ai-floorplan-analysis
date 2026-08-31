export function fitSourcePlane(sourceWidth, sourceHeight, availableWidth, maximumHeight) {
  if (![sourceWidth, sourceHeight, availableWidth, maximumHeight].every(
    (value) => Number.isFinite(value) && value > 0,
  )) throw new Error('Canvas dimensions must be positive finite numbers.')
  const scale = Math.min(availableWidth / sourceWidth, maximumHeight / sourceHeight)
  return { scale, width: sourceWidth * scale, height: sourceHeight * scale }
}

export function metricPointToPixel(point, coordinateSystem) {
  const values = [
    point?.x, point?.y, coordinateSystem?.pixels_per_meter,
    coordinateSystem?.image_width_pixels, coordinateSystem?.image_height_pixels,
  ]
  if (!values.every(Number.isFinite)
    || point.x < 0 || point.y < 0
    || coordinateSystem.pixels_per_meter <= 0
    || coordinateSystem.image_width_pixels <= 0
    || coordinateSystem.image_height_pixels <= 0) {
    throw new Error('Canonical canvas coordinates are invalid.')
  }
  const x = point.x * coordinateSystem.pixels_per_meter
  const y = point.y * coordinateSystem.pixels_per_meter
  if (x < 0 || y < 0
    || x > coordinateSystem.image_width_pixels
    || y > coordinateSystem.image_height_pixels) {
    throw new Error('Canonical canvas coordinates are outside the source plane.')
  }
  return { x, y }
}

export function metricPointsToPixels(points, coordinateSystem) {
  if (!Array.isArray(points)) throw new Error('Canonical point collection is invalid.')
  return points.flatMap((point) => {
    const pixel = metricPointToPixel(point, coordinateSystem)
    return [pixel.x, pixel.y]
  })
}

export function resolveBlueprintProvenance(geometry) {
  const processingJobIds = new Set()
  for (const item of [...geometry.walls, ...geometry.symbols]) {
    if (item.processing_job_id !== null) processingJobIds.add(item.processing_job_id)
  }
  if (processingJobIds.size !== 1) return null
  const [processingJobId] = processingJobIds
  if (!Number.isSafeInteger(processingJobId) || processingJobId <= 0) return null
  return Object.freeze({ floorPlanId: geometry.floor_plan_id, processingJobId })
}
