import { expect, it } from 'vitest'
import { wiringDesign } from './wiringDesign.js'
import { routeAppearance } from './routeProjection.js'

it('shares installation design across observed, manual and generated wiring without inferring it from origin', () => {
  for (const origin of [undefined, 'observed', 'generated']) {
    const ceiling = { origin, installation_method: 'concealed_in_ceiling', line_style: 'solid' }
    const floor = { origin, installation_method: 'concealed_under_floor', line_style: 'dashed' }
    expect(wiringDesign(ceiling)).toEqual({ color: routeAppearance('ceiling_service').color, dash: undefined })
    expect(wiringDesign(floor)).toEqual({ color: routeAppearance('underground').color, dash: [8, 5] })
    expect(wiringDesign({ origin })).toMatchObject({ color: routeAppearance().color })
    expect(wiringDesign(ceiling, false, { previewDrop: true }).color).toBe(routeAppearance('wall_drop').color)
    expect(wiringDesign(floor, false, { previewDrop: true }).color).toBe(routeAppearance('underground_rise').color)
  }
})

it('preserves source line conventions in both coordinate adapters and changes only selection styling', () => {
  const source = { installation_method: 'concealed_in_ceiling', line_style: 'dashed', points: [{ x: 1, y: 2 }, { x: 3, y: 2 }] }
  const before = structuredClone(source)
  expect(wiringDesign(source)).toEqual(wiringDesign({ installationMethod: source.installation_method, lineStyle: source.line_style }))
  expect(wiringDesign(source, true)).toEqual({ color: '#2563eb', dash: [8, 5] })
  expect(wiringDesign({ line_style: 'dashed' }).color).toBe('#8a5a00')
  expect(source).toEqual(before)
})
