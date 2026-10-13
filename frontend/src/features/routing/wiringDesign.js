// Shared display palette. These are not conductor sizes or electrical rules.
export const WIRING_COLORS = Object.freeze({
  ceiling: '#f05a28',
  wall: '#c8816a',
  underground: '#2563eb',
  riser: '#9c36b5',
  unresolved: '#8a5a00',
  selected: '#2563eb',
})

export function wiringDesign(wire, selected = false, segment = null) {
  const method = wire.installation_method ?? wire.installationMethod
  const floor = method === 'concealed_under_floor'
  const ceiling = method === 'concealed_in_ceiling'
  const wall = method === 'concealed_in_wall' || method === 'exposed_on_wall'
  const style = wire.line_style ?? wire.lineStyle
  return {
    color: selected ? WIRING_COLORS.selected : floor ? WIRING_COLORS.underground
      : segment?.previewDrop || wall ? WIRING_COLORS.wall
        : ceiling ? WIRING_COLORS.ceiling : WIRING_COLORS.unresolved,
    dash: floor || style === 'dashed' ? [8, 5]
      : style === 'solid' ? undefined : [5, 4],
  }
}
