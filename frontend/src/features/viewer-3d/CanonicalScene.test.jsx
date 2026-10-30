import { expect, it, vi } from 'vitest'
import { CanonicalScene } from './CanonicalScene.jsx'
import { JoinedWallMesh } from './JoinedWallMesh.jsx'
import { WALL_APPEARANCE } from '../detection-review/wallAppearance.js'
vi.mock('react', async importOriginal => ({...await importOriginal(),useMemo:fn=>fn(),useEffect:()=>{}}))

it('uses studio wall materials independently of dark navy 2D walls without changing geometry',()=>{
  const wall={id:'wall-0001',position:[2,1.5,0],rotation:[0,0,0],size:[4,3,.15]}
  const before=structuredClone(wall)
  const scene={width:10,depth:8,elevation:0,rooms:[],walls:[wall],symbols:[],routeSegments:[]}
  const fallback=CanonicalScene({scene}).props.children[3][0]
  expect(fallback.props.children[1].props.selected).toBe(false)
  expect(fallback.props.children[1].props.wall).toBe(wall)
  expect(fallback.props.position).toEqual(wall.position)
  expect(fallback.props.children[0].props.args).toEqual(wall.size)
  const joined={id:wall.id,elevation:0,height:3,footprints:[[{x:0,y:0},{x:4,y:0},{x:4,y:.15},{x:0,y:.15}]],boundary:[]}
  const mesh=JoinedWallMesh({wall:joined})
  expect(mesh.props.children.props.selected).toBe(false)
  expect(WALL_APPEARANCE.normal).toBe('#0f172a')
  expect(wall).toEqual(before)
  mesh.props.geometry.dispose()
})

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
