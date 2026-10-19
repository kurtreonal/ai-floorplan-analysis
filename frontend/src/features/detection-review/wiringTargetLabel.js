export function wiringTargetLabel(target, presentations = {}) {
  if (target.kind === 'junction') return `Path ${target.wireId}`
  const name = presentations[target.symbolId]?.label || presentations[target.symbolId]?.name
  const terminal = target.terminalId === 'design-anchor' ? 'design anchor' : target.terminalId
  return `${name ? `${name} · ` : ''}${target.symbolId}${terminal ? ` · ${terminal}` : ''}`
}
