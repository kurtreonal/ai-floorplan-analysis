import { expect, it, vi } from 'vitest'
import { CanonicalScene } from './CanonicalScene.jsx'
vi.mock('react', async importOriginal => ({...await importOriginal(),useMemo:fn=>fn()}))

it('renders stored paths as continuous tubes with the shared design without inventing installation from elevation or origin', () => {
  const segments = ['observed', 'generated'].map((provenance, segmentIndex) => ({
    routeId: 'route', segmentIndex, provenance, installationMethod: 'unresolved', elevationState: 'stored',
    start: [1, 2.8, 3], end: [4, 2.8, 3],
  }))
  const before = structuredClone(segments)
  const scene = { width: 10, depth: 8, elevation: 0, rooms: [], walls: [], symbols: [], routeSegments: segments }
  const groups = CanonicalScene({ scene }).props.children[4]
  for (const group of groups) {
    expect(group.props.userData).toMatchObject({ installationMethod: 'unresolved', displayRadiusOnly: true })
    expect(group.props.children.props.run.points).toEqual([[1,2.8,3],[4,2.8,3]])
    expect(group.props.children.props.run.laneOffset).toBe(0)
    expect(group.props.children.props.color).toBe('#8a5a00')
  }
  expect(segments).toEqual(before)
})
