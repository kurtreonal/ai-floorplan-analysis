import { expect, it, vi } from 'vitest'
import { DraftWiring3D } from './DraftWiring3D.jsx'
import { ROUTE_DISPLAY_RADIUS } from '../routing/routeMesh.js'
vi.mock('react', async importOriginal => ({...await importOriginal(),useMemo:fn=>fn()}))

it('applies the same ceiling/underground tube design to observed and generated paths, including wall attachments', () => {
  const start = [1, .75, 2], end = [3, .75, 2]
  const wires = ['observed', 'generated'].map((origin, index) => ({ id: `wire${index}`, origin,
    installationMethod: 'concealed_in_ceiling', lineStyle: 'solid', points: [start, end],
    segments: [{ start, end }, { start: end, end: [3, .3, 2], previewDrop: true }] }))
  const before = structuredClone(wires)
  const groups = DraftWiring3D({ scene: { unitsPerMeter: .25, draftWires: wires } }).props.children
  for (const group of groups) {
    expect(group.props.children[0][0].props.color).toBe('#f05a28')
    expect(group.props.children[0][0].props.radius).toBe(ROUTE_DISPLAY_RADIUS*.25)
    expect(group.props.children[0][1].props.color).toBe('#c8816a')
    expect(group.props.userData).toMatchObject({ installationMethod: 'concealed_in_ceiling', lineStyle: 'solid' })
  }
  const floor = DraftWiring3D({ scene: { unitsPerMeter: .25,
    draftWires: [{ ...wires[0], installationMethod: 'concealed_under_floor' }] } }).props.children[0]
  expect(floor.props.children[0][0].props.color).toBe('#2563eb')
  expect(floor.props.children[0][0].props.xray).toBe(true)
  expect(groups[0].props.children[0][0].props.xray).toBe(false)
  expect(wires).toEqual(before)
})

it('keeps tubing smaller than the smallest wall faceplate at every preview scale', () => {
  for (const unit of [.02,.25,1,2]) {
    const wire={id:'wire',segments:[{start:[0,1,0],end:[1,1,0]}],points:[[0,1,0],[1,1,0]]}
    const tube=DraftWiring3D({scene:{unitsPerMeter:unit,draftWires:[wire]}}).props.children[0].props.children[0][0]
    expect(tube.props.radius*2).toBeLessThan(.07*unit*.25)
  }
})

it('renders selectable tubes and editing handles for each original vertex, not derived drop points', () => {
  const onSelectWire = vi.fn(), onMoveWirePoint = vi.fn()
  const points = [[1,.75,2],[3,.75,2],[3,.75,4]]
  const scene = { unitsPerMeter: .25, draftWires: [{ id: 'wire1', points, illustrativeHeight: true,
    segments: [{ start: points[0], end: points[1] },{ start: points[1], end: points[2] },{ start: points[2], end: [3,.3,4], previewDrop: true }] }] }
  const tree = DraftWiring3D({ scene, selectedWireId: 'wire1', onSelectWire, onMoveWirePoint })
  const wire = tree.props.children[0]
  expect(wire.props.userData).toMatchObject({ wireId: 'wire1', previewOnly: true })
  const tubes = wire.props.children[0], handles = wire.props.children[1]
  expect(tubes).toHaveLength(2)
  expect(handles).toHaveLength(3)
  const event = { stopPropagation: vi.fn() }
  tubes[0].props.onClick(event)
  expect(event.stopPropagation).toHaveBeenCalled()
  expect(onSelectWire).toHaveBeenCalledWith('wire1',event)
  handles[1].props.onMove({ x: 4, y: 5 })
  expect(onMoveWirePoint).toHaveBeenCalledWith('wire1',1,{ x: 4, y: 5 })
  expect(DraftWiring3D({ scene }).props.children[0].props.children[1]).toBeUndefined()
})
