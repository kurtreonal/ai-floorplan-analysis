/* @vitest-environment jsdom */
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DevicePicker } from './DevicePicker.jsx'
afterEach(cleanup)
const legends=[{id:1,class_id:1,name:'1-gang switch [sheet-1:L01]',category:'Switches',code:'SW-1',aliases:['Single switch']},
  {id:2,class_id:2,name:'2-gang switch',specification:'2 gangs, flush-mounted'},
  {id:3,class_id:3,name:'Duplex convenience outlet',catalog_code:'OUT-2'},
  {id:4,class_id:4,name:'Inactive switch',is_active:false},
  {id:5,class_id:5,name:'Circuit homerun notation'},
  {id:6,class_id:6,name:'Raceway conduit concealed in ceiling [pdf-123456789abc:p1:L01]'}]
function Picker(props) { const [value,setValue]=useState('');return <DevicePicker legends={legends} value={value} onChange={setValue} {...props}/> }

it.each([['2 gang','2-gang switch'],['Single switch','1-gang switch'],['SW-1','1-gang switch'],['OUT-2','Duplex convenience outlet'],['Switches','1-gang switch']])('searches approved display, alias, type and code metadata without changing mappings: %s',(query,name)=>{
  const source=structuredClone(legends),change=vi.fn()
  render(<DevicePicker legends={legends} value="" onChange={change}/>)
  fireEvent.change(screen.getByLabelText('Search available devices'),{target:{value:query}})
  expect(screen.getByRole('option',{name:new RegExp(name)})).toBeTruthy()
  expect(change).not.toHaveBeenCalled()
  expect(legends).toEqual(source)
})

it('excludes inactive/unavailable entries, retains distinguishing specifications, and passes the approved ID into placement',()=>{
  render(<Picker/>)
  expect(screen.queryByRole('option',{name:/Inactive|homerun|Raceway/})).toBeNull()
  expect(screen.getByRole('option',{name:/2 gangs, flush-mounted/})).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Device to place'),{target:{value:'2'}})
  expect(screen.getByText(/Ready to place: 2-gang switch/)).toBeTruthy()
  expect(screen.getByLabelText('Device to place').value).toBe('2')
})

it('supports search-to-list keyboard focus, clear/empty states, escape cancellation and selection confirmation',()=>{
  const cancel=vi.fn()
  render(<Picker onCancel={cancel}/>)
  const search=screen.getByLabelText('Search available devices'),select=screen.getByLabelText('Device to place')
  search.focus();fireEvent.keyDown(search,{key:'ArrowDown'})
  expect(document.activeElement).toBe(select)
  fireEvent.change(select,{target:{value:'1'}})
  fireEvent.keyDown(select,{key:'Enter'})
  expect(document.activeElement).not.toBe(select)
  fireEvent.change(search,{target:{value:'nothing matches'}})
  expect(screen.getByText('No matching approved devices.')).toBeTruthy()
  expect(screen.getByText(/Ready to place: 1-gang/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Clear device search'}))
  expect(search.value).toBe('');expect(document.activeElement).toBe(search)
  fireEvent.keyDown(search,{key:'Escape'});expect(cancel).toHaveBeenCalledOnce()
})

it('preserves an exact selected active alias ID and locks placement while unavailable',()=>{
  const aliases=[{id:8,class_id:8,name:'Duplex outlet [sheet-1:L02]'}, {id:9,class_id:9,name:'Duplex outlet [sheet-2:L03]'}]
  render(<DevicePicker legends={aliases} value="9" disabled onChange={vi.fn()}/>)
  expect(screen.getByLabelText('Device to place').value).toBe('9')
  expect(screen.getByLabelText('Device to place').disabled).toBe(true)
  expect(screen.getByLabelText('Search available devices').disabled).toBe(true)
})
