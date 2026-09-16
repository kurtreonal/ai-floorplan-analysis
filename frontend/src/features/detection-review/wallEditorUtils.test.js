import { describe, expect, it } from 'vitest'
import {
  constrainPoint,
  findSnapPoint,
  formatWallDimension,
  wallMidpoint,
  wallTextRotation,
} from './wallEditorUtils.js'

describe('wallEditorUtils', () => {
  describe('formatWallDimension', () => {
    it('returns unscaled pixels when scale is absent', () => {
      expect(formatWallDimension(150.4)).toBe('150px (unscaled)')
      expect(formatWallDimension(0)).toBe('0px (unscaled)')
      expect(formatWallDimension(-10)).toBe('0px (unscaled)')
    })

    it('formats feet and inches when approved scale is provided', () => {
      // 100 pixels_per_meter, 4.572 meters = 15 feet = 457.2 pixels
      expect(formatWallDimension(457.2, 100)).toBe('15\'0"')
      // 17 feet = 5.1816 meters = 518.16 pixels
      expect(formatWallDimension(518.16, 100)).toBe('17\'0"')
    })
  })

  describe('constrainPoint', () => {
    it('returns current point when disabled', () => {
      expect(constrainPoint({ x: 10, y: 10 }, { x: 25, y: 15 }, false)).toEqual({ x: 25, y: 15 })
    })

    it('constrains horizontally when dx >= dy', () => {
      expect(constrainPoint({ x: 10, y: 10 }, { x: 40, y: 15 }, true)).toEqual({ x: 40, y: 10 })
    })

    it('constrains vertically when dy > dx', () => {
      expect(constrainPoint({ x: 10, y: 10 }, { x: 15, y: 50 }, true)).toEqual({ x: 10, y: 50 })
    })
  })

  describe('findSnapPoint', () => {
    const walls = [
      { id: 'w1', disposition: 'accepted', start: { x: 50, y: 50 }, end: { x: 150, y: 50 } },
      { id: 'w2', disposition: 'rejected', start: { x: 200, y: 200 }, end: { x: 250, y: 200 } },
    ]

    it('snaps to closest wall endpoint within threshold', () => {
      const result = findSnapPoint({ x: 53, y: 48 }, walls, { threshold: 10 })
      expect(result.snapped).toBe(true)
      expect(result.x).toBe(50)
      expect(result.y).toBe(50)
    })

    it('does not snap if outside threshold', () => {
      const result = findSnapPoint({ x: 80, y: 80 }, walls, { threshold: 10 })
      expect(result.snapped).toBe(false)
      expect(result.x).toBe(80)
      expect(result.y).toBe(80)
    })

    it('ignores rejected walls and excluded wall id', () => {
      const res1 = findSnapPoint({ x: 202, y: 198 }, walls, { threshold: 10 })
      expect(res1.snapped).toBe(false)
      const res2 = findSnapPoint({ x: 52, y: 49 }, walls, { threshold: 10, excludeWallId: 'w1' })
      expect(res2.snapped).toBe(false)
    })
  })

  describe('wallMidpoint and wallTextRotation', () => {
    it('calculates midpoint correctly', () => {
      expect(wallMidpoint({ x: 10, y: 20 }, { x: 50, y: 60 })).toEqual({ x: 30, y: 40 })
    })

    it('keeps text rotation within readable range [-90, 90]', () => {
      expect(wallTextRotation({ x: 0, y: 0 }, { x: 100, y: 0 })).toBe(0)
      expect(wallTextRotation({ x: 100, y: 0 }, { x: 0, y: 0 })).toBe(0)
      expect(wallTextRotation({ x: 0, y: 0 }, { x: 0, y: 100 })).toBe(90)
    })
  })
})
