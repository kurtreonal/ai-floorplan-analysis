import { sceneCeiling } from './devicePlacement.js'

// Prefer room footprints. When absent, a simple wall-envelope cover is only a
// visibility aid, not inferred roof construction (courtyards/openings unknown).
export function roofPreview(scene) {
  const elevation = sceneCeiling(scene)
  const rooms = scene.roofRooms || scene.rooms
  if (rooms.length) return rooms.map((room) => ({ ...room, elevation }))
  const points = (scene.mountingWalls || scene.walls).flatMap((wall) => {
    const angle = -wall.rotation[1], dx = Math.cos(angle) * wall.size[0] / 2, dz = Math.sin(angle) * wall.size[0] / 2
    return [[wall.position[0] - dx, wall.position[2] - dz], [wall.position[0] + dx, wall.position[2] + dz]]
  })
  if (!points.length) return []
  const x0 = Math.min(...points.map(([x]) => x)), x1 = Math.max(...points.map(([x]) => x))
  const y0 = Math.min(...points.map(([, y]) => y)), y1 = Math.max(...points.map(([, y]) => y))
  if (x1 - x0 < 1e-6 || y1 - y0 < 1e-6) return []
  return [{ id: 'wall-envelope-cover', elevation, boundary: [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }] }]
}
