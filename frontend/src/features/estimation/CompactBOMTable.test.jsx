/* @vitest-environment jsdom */
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { CompactBOMTable } from './CompactBOMTable.jsx'
afterEach(cleanup)

it('keeps known subtotals and a numeric total visible while other costs are missing',()=>{
  render(<CompactBOMTable planning={{items:[],display_groups:[],cost_summary:{incomplete:true,currencies:{
    PHP:{devices:'14445',conduit:'500',wire:'240',total:'15185'},
    USD:{devices:'0',conduit:'0',wire:'0',total:'0'},
  }}}}/> )
  const footer=screen.getByRole('table').querySelector('tfoot')
  expect(footer.rows).toHaveLength(8)
  expect(footer.textContent).toContain('Devices subtotal (PHP)₱14,445.00')
  expect(footer.textContent).toContain('Conduit subtotal (PHP)₱500.00')
  expect(footer.textContent).toContain('Wire/cable subtotal (PHP)₱240.00')
  expect(footer.textContent).toContain('Total so far (PHP)Partial₱15,185.00')
  expect(footer.textContent).toContain('Total so far (USD)Partial$0.00')
})

it('shows server-grouped quantities and costs with only a reference dropdown',()=>{
  const planning={items:[],unpriced_items:0,priced_subtotals:{PHP:'50'},display_groups:[{
    key:'lamps',kind:'device',name:'Lamp',members:[{id:'symbol-0001',floor_plan_id:1},{id:'symbol-0002',floor_plan_id:1}],
    components:[{quantity:'2',unit:'piece',unit_price:'25',currency:'PHP'}],costs:{PHP:'50'},incomplete:false}]}
  const before=JSON.stringify(planning)
  render(<CompactBOMTable planning={planning}/>)
  const row=screen.getByRole('table').querySelector('tbody tr')
  expect(row.textContent).toContain('2 piece')
  expect(row.cells[3].textContent).toBe('₱50.00')
  const refs=screen.getByRole('combobox',{name:'Symbols in Lamp'})
  expect(Array.from(refs.options).map(option=>option.textContent)).toEqual(['2 symbols','symbol-0001 · Plan 1','symbol-0002 · Plan 1'])
  expect(screen.queryByText('Calculation basis')).toBeNull()
  expect(screen.getByRole('table').querySelector('tfoot').textContent).toBe('Total (PHP)₱50.00')
  expect(JSON.stringify(planning)).toBe(before)
})

it('pairs conduit and cable, displays combined backend costs and keeps currencies separate',()=>{
  render(<CompactBOMTable planning={{items:[],unpriced_items:1,priced_subtotals:{PHP:296,USD:5},display_groups:[{
    key:'paths',kind:'path',name:'Wiring paths',members:[{id:'segment-0001'},{id:'segment-0002'}],
    components:[{material_kind:'conduit',quantity:8,unit:'meter',unit_price:25,currency:'PHP'},
      {material_kind:'wire',quantity:8,unit:'meter',unit_price:12,currency:'PHP'}],
    costs:{PHP:296},incomplete:false}]}}/>)
  const row=screen.getByRole('table').querySelector('tbody tr')
  expect(row.cells[3].textContent).toBe('₱296.00')
  expect(within(row).getByRole('combobox').options).toHaveLength(3)
  const footer=screen.getByRole('table').querySelector('tfoot')
  expect(footer.rows).toHaveLength(2)
  expect(footer.textContent).toContain('Priced subtotal (PHP)')
  expect(footer.textContent).toContain('Priced subtotal (USD)')
})
