import { orderNamed } from '../utils/listOrder.js'

// A catalog view, not a database migration or an approval. Keep every alias ID.
const SOURCE_SUFFIX = / \[(?:sheet-\d+:L[\w-]+|pdf-[a-f0-9]{12}:p\d+:L\d+|u:[\w-]+)\]$/

export function legendDescription(name) {
  return name.replace(SOURCE_SUFFIX, '')
}

export function groupLegendChoices(records, { selectedId = null } = {}) {
  const groups = new Map()
  for (const record of records) {
    const description = legendDescription(record.name)
    const text = description.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase()
    const meaning = /\b(unknown|unresolved|unclassified|unspecified)\b/.test(text) ? `id:${record.id}` : text
    // An inactive alias must never disappear into an active representative.
    const key = JSON.stringify([meaning, record.is_active ?? true])
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(record)
  }
  return orderNamed([...groups.values()].map((aliases) => {
    const ordered = [...aliases].sort((a, b) => a.id - b.id)
    const representative = ordered.find((record) => record.id === selectedId) || ordered[0]
    return { ...representative, displayName: legendDescription(representative.name), aliases: ordered }
  }), item => item.displayName)
}
