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
  it('rejects unsafe dimensions and malformed/out-of-bounds points', () => {
    expect(() => buildDraftRoomScene({ rooms: [room] }, 0, 60)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [room] }, 100, 60, Infinity)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [{ ...room, boundary: [{ x: -1, y: 0 }, ...room.boundary] }] }, 100, 60)).toThrow()
    expect(() => buildDraftRoomScene({ rooms: [{ ...room, boundary: [room.boundary[0], room.boundary[2], room.boundary[1], room.boundary[3]] }] }, 100, 60)).toThrow(/crosses/)
  })
})
