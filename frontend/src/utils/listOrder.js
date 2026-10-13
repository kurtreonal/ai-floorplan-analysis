// Display ordering only. Never sort canonical points or mutate server arrays.
const collator = new Intl.Collator('en', { numeric: true, sensitivity: 'base' })

export function compareLabels(left, right) {
  const a = String(left ?? '').normalize('NFKC').trim()
  const b = String(right ?? '').normalize('NFKC').trim()
  if (!a || !b) return a ? -1 : b ? 1 : 0
  return collator.compare(a, b)
}

export function orderList(items, ...keys) {
  return [...items].sort((a, b) => {
    for (const key of keys) {
      const compared = compareLabels(key(a), key(b))
      if (compared) return compared
    }
    return compareLabels(a.id ?? a.row_id ?? a.path_id, b.id ?? b.row_id ?? b.path_id)
  })
}

export function orderNamed(items, name = item => item.name) {
  return orderList(items, name)
}

export function orderFloors(items) {
  return orderList(items, item => item.sort_order, item => item.name)
}
