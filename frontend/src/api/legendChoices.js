import { orderNamed } from '../utils/listOrder.js'

// A catalog view, not a database migration or an approval. Keep every alias ID.
const SOURCE_SUFFIX = /(?:\s*\[(?:sheet[- :][^\]]+|pdf-[^\]]+|pec-[^\]]+|u:[^\]]+)\])+\s*$/i

export const legendSourceSuffix=name=>name.match(SOURCE_SUFFIX)?.[0].trim() || ''

export function legendDescription(name) {
  return name.replace(SOURCE_SUFFIX, '')
}

export const legendDisplayName=name=>legendDescription(name).replace(/\s*\((new|old)\)\s*$/i,'')

export function legendSearchText(value) {
  return String(value ?? '').normalize('NFKC').toLocaleLowerCase('en')
    .replace(/\boutlets\b/g,'outlet').replace(/\breceptacles\b/g,'outlet')
    .replace(/\breceptacle\b/g,'outlet').replace(/\bsockets?\b/g,'outlet')
    .replace(/\bswitches\b/g,'switch').replace(/[^\p{L}\p{N}]+/gu,' ').trim()
}

export function deviceChoiceName(name) {
  const clean=legendDescription(name)
  if (/\b(?:data|voice|telephone|fiber|network)\b/i.test(clean))return clean
  if (/\bduplex\b/i.test(clean) && /\b(?:outlet|receptacle)\b/i.test(clean)) {
    if (/\bGFCI\b/i.test(clean))return 'Duplex outlet with GFCI'
    if (/\bweatherproof\b/i.test(clean))return 'Weatherproof duplex outlet'
    if (/\bfloor\b/i.test(clean))return 'Floor duplex outlet'
    return 'Duplex outlet'
  }
  if (/\bsimplex\b/i.test(clean) && /\b(?:outlet|receptacle)\b/i.test(clean))return 'Simplex outlet'
  return clean
}

export function groupLegendChoices(records, { selectedId = null, combineInactive = false } = {}) {
  const groups = new Map()
  for (const record of records) {
    const description = legendDisplayName(record.name)
    const text = description.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase()
    const meaning = /\b(unknown|unresolved|unclassified|unspecified)\b/.test(text) ? `id:${record.id}` : text
    // An inactive alias must never disappear into an active representative.
    const key = JSON.stringify([meaning, combineInactive ? null : record.is_active ?? true])
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(record)
  }
  return orderNamed([...groups.values()].map((aliases) => {
    const ordered = [...aliases].sort((a, b) => a.id - b.id)
    const representative = ordered.find((record) => record.id === selectedId) || (combineInactive && ordered.find(record=>record.is_active)) || ordered[0]
    return { ...representative, ...(combineInactive?{is_active:ordered.some(record=>record.is_active)}:{}),displayName: legendDisplayName(representative.name), aliases: ordered }
  }), item => item.displayName)
}
