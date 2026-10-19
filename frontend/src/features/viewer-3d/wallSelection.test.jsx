import { expect, it, vi } from 'vitest'
import { CanonicalScene } from './CanonicalScene.jsx'
import { JoinedWallMesh } from './JoinedWallMesh.jsx'
vi.mock('react', async importOriginal => ({ ...await importOriginal(), useMemo: fn => fn(), useEffect: () => {} }))

it('highlights only the selected wall in joined and legacy scenes without changing footprints or dimensions', () => {
  const fallback = id => ({ id, position: [2, 1.5, 0], rotation: [0, 0, 0], size: [4, 3, .15] })
  const joined = { id: 'joined', elevation: 0, height: 3,
    footprints: [[{ x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: .15 }, { x: 0, y: .15 }]], boundary: [] }
  const scene = { width: 10, depth: 8, elevation: 0, rooms: [], walls: [fallback('one'), fallback('two'), joined], symbols: [], routeSegments: [] }
  const before = structuredClone(scene)
  const normal = CanonicalScene({ scene }).props.children[3][0].props.children[1].props.color
  const walls = CanonicalScene({ scene, selectedWallId: 'two' }).props.children[3]
  expect(walls[0].props.children[1].props.color).toBe(normal)
  expect(walls[1].props.children[1].props.color).toBe('#ff7a45')
  expect(walls[1].props.position).toBe(scene.walls[1].position)
  expect(walls[2].props.selected).toBe(false)
  const selected = CanonicalScene({ scene, selectedWallId: 'joined' }).props.children[3][2]
  expect(selected.props.wall).toBe(joined)
  const mesh = JoinedWallMesh(selected.props)
  expect(mesh.props.children.props.color).toBe('#ff7a45')
  expect(scene).toEqual(before)
  mesh.props.geometry.dispose()
})
