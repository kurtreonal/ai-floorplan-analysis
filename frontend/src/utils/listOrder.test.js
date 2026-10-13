import { expect, it } from 'vitest'
import { compareLabels, orderNamed, orderList, orderFloors } from './listOrder.js'

it('sorts case-insensitive names and embedded numbers without mutating records', () => {
  const items = Object.freeze([{id:10,name:'wire 10'}, {id:2,name:'Wire 2'}, {id:3,name:'  outlet '}, {id:4,name:null}].map(Object.freeze))
  expect(orderNamed(items).map(item => item.id)).toEqual([3,2,10,4])
  expect(items.map(item => item.id)).toEqual([10,2,3,4])
  expect(compareLabels('Ａ', 'a')).toBe(0)
})

it('retains explicit floor order, stable identity ties and numeric page sequence', () => {
  expect(orderFloors([{id:2,name:'Attic',sort_order:10},{id:3,name:'Ground',sort_order:0},{id:1,name:'Upper',sort_order:2}]).map(item=>item.id)).toEqual([3,1,2])
  expect(orderNamed([{id:10,name:'Light'},{id:2,name:'light'}]).map(item=>item.id)).toEqual([2,10])
  expect(orderList([{id:3,plan:2,page:10},{id:2,plan:2,page:2},{id:1,plan:1,page:1}],item=>item.plan,item=>item.page).map(item=>item.id)).toEqual([1,2,3])
})
