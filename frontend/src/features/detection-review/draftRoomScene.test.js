import { describe, expect, it } from 'vitest'
import { buildDraftRoomScene } from './draftRoomScene.js'
const room = { id: 'r1', disposition: 'accepted', boundary: [{ x: 20, y: 10 }, { x: 80, y: 10 }, { x: 80, y: 50 }, { x: 20, y: 50 }] }
describe('relative draft room preview', () => {
  it('uses the same room coordinates without approving or mutating them', () => {
    const draft = { rooms: [structuredClone(room)], symbols: [{ id: 'ignored' }] }
    const before = JSON.stringify(draft)
    const scene = buildDraftRoomScene(draft, 100, 60)
    expect(scene.rooms[0].boundary[0]).toEqual({ x: 2, y: 1 })
    expect(scene.walls).toHaveLength(4)
    expect(scene.previewOnly).toBe(true)
    expect(scene.unit).toBe('relative')
    expect(scene.symbols).toEqual([])
    expect(JSON.stringify(draft)).toBe(before)
  })
  it('updates geometry, excludes rejected rooms and supports flat previews', () => {
    expect(buildDraftRoomScene({ rooms: [{ ...room, disposition: 'rejected' }] }, 100, 60).walls).toHaveLength(0)
    expect(buildDraftRoomScene({ rooms: [room] }, 100, 60, 0).walls).toHaveLength(0)
    const moved = { ...room, boundary: room.boundary.map((p) => ({ x: p.x + 10, y: p.y })) }
    expect(buildDraftRoomScene({ rooms: [moved] }, 100, 60).rooms[0].boundary[0].x).toBe(3)
  })
  it('renders 3D walls directly from draft.walls and excludes rejected walls', () => {
    const wall1 = { id: 'wall-1', disposition: 'accepted', start: { x: 10, y: 10 }, end: { x: 90, y: 10 }, estimated_thickness_pixels: 8 }
    const wall2 = { id: 'wall-2', disposition: 'rejected', start: { x: 10, y: 10 }, end: { x: 10, y: 50 } }
    const draft = { walls: [wall1, wall2], rooms: [] }
    const scene = buildDraftRoomScene(draft, 100, 60, 0.8)
    expect(scene.walls).toHaveLength(1)
    expect(scene.walls[0].id).toBe('wall-1')
    expect(scene.walls[0].position[0]).toBeCloseTo(5) // (1 + 9) / 2
    expect(scene.walls[0].position[1]).toBeCloseTo(0.4) // relativeHeight / 2
    expect(scene.walls[0].position[2]).toBeCloseTo(1) // (1 + 1) / 2
    expect(scene.walls[0].size[0]).toBeCloseTo(8) // length = 80 * (10/100) = 8
  })
  it('rejects unsafe dimensions and malformed/out-of-bounds points', () => {
    expect(() => buildDraftRoomScene({ rooms: [room] }, 0, 60)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [room] }, 100, 60, Infinity)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [{ ...room, boundary: [{ x: -1, y: 0 }, ...room.boundary] }] }, 100, 60)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [{ ...room, boundary: [room.boundary[0], room.boundary[2], room.boundary[1], room.boundary[3]] }] }, 100, 60)).toThrow(/crosses/)
  })
})
