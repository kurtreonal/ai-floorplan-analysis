// Defaults are supplied by the backend's VED policy, never inferred from meshes.
export function withMountingDefaults(symbol, presentation, defaults = {}) {
  const name=presentation?.name || ''
  if(!presentation?.mapped || symbol.disposition==='rejected' || /\b(data|telephone|network|panel|switchboard|home.?run|notation)\b/i.test(name))return symbol
  const family=/\b(outlet|receptacle|socket)\b/i.test(name) ? 'outlet' : /\bswitch(?:es)?\b/i.test(name) ? 'switch' : null
  const value=defaults[family]
  if(!Number.isFinite(value) || (symbol.mounting_height_meters!=null && symbol.mounting_height_source!=='ved_default') || symbol.mounting_reference && symbol.mounting_reference!=='device_center')return symbol
  return {...symbol,mounting_height_meters:value,mounting_reference:'device_center',mounting_height_source:'ved_default'}
}
