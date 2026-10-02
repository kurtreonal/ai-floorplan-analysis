// Illustrative equipment dimensions in metres, not engineering specifications.
// The saved plan anchor is never changed by a visual mounting default.
const profiles = {
  troffer: { size: [0.6, 0.09, 1.2], mount: 'ceiling' },
  'linear-light': { size: [0.12, 0.08, 1.2], mount: 'ceiling' },
  'round-light': { size: [0.2, 0.06, 0.2], mount: 'ceiling' },
  detector: { size: [0.1, 0.04, 0.1], mount: 'ceiling' },
  outlet: { size: [0.07, 0.115, 0.018], mount: 'wall', height: 0.3 },
  switch: { size: [0.07, 0.115, 0.018], mount: 'wall', height: 1.2 },
  panel: { size: [0.45, 0.6, 0.15], mount: 'wall', height: 1.5 },
  'pull-station': { size: [0.09, 0.14, 0.04], mount: 'wall', height: 1.2 },
  alarm: { size: [0.12, 0.12, 0.06], mount: 'wall', height: 2.2 },
  annotation: { size: [0.12, 0.015, 0.12], mount: 'plan' },
  unknown: { size: [0.1, 0.1, 0.1], mount: 'plan' },
}

export function sceneCeiling(scene) {
  const walls = scene.mountingWalls || scene.walls
  return scene.ceilingElevation ?? (walls.length
    ? Math.max(...walls.map((wall) => wall.position[1] + wall.size[1] / 2))
    : scene.elevation + 3 * (scene.unitsPerMeter ?? 1))
}

export function devicePlacement(symbol, scene, family) {
  const profile = profiles[family] || profiles.unknown
  const unit = scene.unitsPerMeter ?? 1
  const size = profile.size.map((value) => value * unit)
  const position = [...symbol.position]
  let rotation = 0
  let nearest = null
  for (const wall of scene.mountingWalls || scene.walls) {
    const angle = -wall.rotation[1], dx = Math.cos(angle), dz = Math.sin(angle)
    const along = Math.max(-wall.size[0] / 2, Math.min(wall.size[0] / 2,
      (position[0] - wall.position[0]) * dx + (position[2] - wall.position[2]) * dz))
    const x = wall.position[0] + along * dx, z = wall.position[2] + along * dz
    const distance = Math.hypot(position[0] - x, position[2] - z)
    if (!nearest || distance < nearest.distance) nearest = { wall, x, z, dx, dz, distance }
  }
  const ceiling = scene.ceilingElevation ?? (nearest
    ? nearest.wall.position[1] + nearest.wall.size[1] / 2 : sceneCeiling(scene))
  if (profile.mount === 'ceiling') position[1] = ceiling - size[1] / 2
  else if (profile.mount === 'wall') {
    position[1] = scene.elevation + Math.min(profile.height * unit, Math.max(size[1] / 2, ceiling - scene.elevation - size[1] / 2))
    // Only mount to a nearby wall; never teleport an uncertain device across a room.
    if (nearest && nearest.distance <= 0.6 * unit + nearest.wall.size[2] / 2) {
      let nx = -nearest.dz, nz = nearest.dx
      const side = (position[0] - nearest.x) * nx + (position[2] - nearest.z) * nz
      const facing = Math.abs(side) > 1e-7 ? side
        : (scene.width / 2 - nearest.x) * nx + (scene.depth / 2 - nearest.z) * nz
      if (facing < 0) { nx *= -1; nz *= -1 }
      const offset = nearest.wall.size[2] / 2 + size[2] / 2 + 0.002 * unit
      position[0] = nearest.x + nx * offset
      position[2] = nearest.z + nz * offset
      rotation = Math.atan2(nx, nz)
    }
  } else position[1] = scene.elevation + size[1] / 2 + 0.002 * unit
  return { position, size, rotation, mount: profile.mount,
    anchorOffset: [position[0] - symbol.position[0], position[2] - symbol.position[2]] }
}
