// @vitest-environment jsdom
import { afterEach,expect,it,vi } from 'vitest'
import { cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react'
import { AdminAssemblies } from './AdminAssemblies.jsx'
import { adminAssemblies,adminMaterialCatalog } from '../../api/materialPrices.js'
vi.mock('../../api/materialPrices.js',()=>({adminAssemblies:vi.fn(),adminMaterialCatalog:vi.fn()}))
afterEach(()=>{cleanup();vi.resetAllMocks()})

it('saves a default whole-device recipe with component quantities, not shipping or a client-side total',async()=>{
  adminAssemblies.mockResolvedValue({writable:true,assemblies:[]})
  adminMaterialCatalog.mockResolvedValue([{id:1,name:'Panasonic switch mechanism',unit:'piece',unit_price:'95',currency:'PHP',is_active:true}])
  render(<AdminAssemblies/> )
  const add=await screen.findByRole('button',{name:'Add assembly'})
  await waitFor(()=>expect(add.disabled).toBe(false));fireEvent.click(add)
  fireEvent.change(screen.getByLabelText('Name'),{target:{value:'One gang switch — Panasonic'}})
  fireEvent.change(screen.getByLabelText('Code'),{target:{value:'ASSEMBLY-SWITCH'}})
  fireEvent.change(screen.getByLabelText('Device type'),{target:{value:'switch_1gang'}})
  fireEvent.click(screen.getByLabelText('Use as the default for this device type'))
  fireEvent.change(screen.getByLabelText('Component 1'),{target:{value:'1'}})
  fireEvent.change(screen.getByLabelText('Component quantity 1'),{target:{value:'2'}})
  fireEvent.click(screen.getByRole('button',{name:'Save assembly'}))
  await waitFor(()=>expect(adminAssemblies).toHaveBeenCalledWith(expect.objectContaining({brand:'Panasonic',device_type:'switch_1gang',
    is_default:true,components:[{material_id:1,quantity:'2'}]}),undefined))
  expect(adminAssemblies.mock.calls.at(-1)[0]).not.toHaveProperty('unit_price')
  expect((await screen.findByRole('status')).textContent).toContain('Assembly saved')
})

it('keeps storage limitations visible without permitting an unsaved default',async()=>{
  adminAssemblies.mockResolvedValue({writable:false,assemblies:[]});adminMaterialCatalog.mockResolvedValue([])
  render(<AdminAssemblies/> )
  expect((await screen.findByRole('note')).textContent).toContain('administrator setup')
  expect(screen.getByRole('button',{name:'Add assembly'}).disabled).toBe(true)
})
