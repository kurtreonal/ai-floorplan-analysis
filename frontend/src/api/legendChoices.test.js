import { expect, it } from 'vitest'
import { groupLegendChoices } from './legendChoices.js'

const row = (id, name, is_active = true) => ({ id, class_id: id + 100, name, is_active })

it('sorts display descriptions alphabetically with natural numbers while retaining a selected alias', () => {
  const records=[row(9,'Switch 10'),row(3,'light'),row(5,'Switch 2'),row(10,'light [sheet-2:L04]')]
  const result=groupLegendChoices(records,{selectedId:10})
  expect(result.map(item=>item.displayName)).toEqual(['light','Switch 2','Switch 10'])
  expect(result[0].id).toBe(10)
  expect(records.map(item=>item.id)).toEqual([9,3,5,10])
})

it('groups only complete equal descriptions, retaining every source ID without mutating records', () => {
  const rows = [row(3, 'Panelboard [sheet-13:L04]'), row(1, 'Panelboard'), row(2, 'Panelboard [pdf-76f411c60b6d:p1:L12]')]
  const before = JSON.stringify(rows)
  const grouped = groupLegendChoices(rows)
  expect(grouped).toHaveLength(1)
  expect(grouped[0].id).toBe(1)
  expect(grouped[0].displayName).toBe('Panelboard')
  expect(grouped[0].aliases.map(alias => alias.id)).toEqual([1, 2, 3])
  expect(JSON.stringify(rows)).toBe(before)
  expect(groupLegendChoices(rows, { selectedId: 3 })[0].id).toBe(3)
})

it('never merges ratings, mounting, switch subtypes, unresolved marks or inactive decisions', () => {
  const names = ['One gang device switch', 'Two gang device switch', 'Three way device switch',
    '1 x 40 watts fluorescent lamp', '2 x 40 watts fluorescent lamp', 'Duplex floor outlet',
    'Duplex wall outlet', 'Smoke detector', 'Smoke detector (new)', 'Smoke detector [weatherproof]']
  const rows = names.map((name, i) => row(i + 1, name))
  rows.push(row(20, 'Smoke detector', false), row(21, 'Switch subtype unresolved [sheet-10:L01]'),
    row(22, 'Switch subtype unresolved [sheet-13:L01]'))
  expect(groupLegendChoices(rows)).toHaveLength(rows.length)
})
