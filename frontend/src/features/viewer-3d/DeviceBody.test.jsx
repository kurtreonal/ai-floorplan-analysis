import { expect, it } from 'vitest'
import { DeviceBody } from './DeviceBody.jsx'

function parts(node, name) {
  if (!node || typeof node !== 'object') return []
  if (Array.isArray(node)) return node.flatMap(n => parts(n, name))
  return [...(node.props?.name === name ? [node] : []), ...parts(node.props?.children, name)]
}
it('shows two side-by-side grounded sockets on a horizontal plate, and separate data-port cavities', () => {
  const outlet = DeviceBody({ family: 'outlet' })
  const sockets = parts(outlet, 'grounded-socket')
  expect(sockets.map(s => s.props.position)).toEqual([[-.23,0,.51],[.23,0,.51]])
  expect(parts(outlet, 'socket-contact')).toHaveLength(4)
  expect(parts(outlet, 'ground-contact')).toHaveLength(2)
  expect(parts(outlet, 'horizontal-outlet-plate')).toHaveLength(1)
  const data = DeviceBody({ family: 'outlet', label: '2 data ports RJ45' })
  expect(parts(data, 'keystone-opening')).toHaveLength(2)
  expect(parts(data, 'socket-contact')).toHaveLength(0)
})
it('renders exactly one or two fluorescent tubes from the existing label, not a troffer surrogate', () => {
  expect(parts(DeviceBody({ family: 'linear-light', label: '1 x 40 watts fluorescent lamp' }), 'fluorescent-tube')).toHaveLength(1)
  expect(parts(DeviceBody({ family: 'linear-light', label: '2×40 watts fluorescent lamp' }), 'fluorescent-tube')).toHaveLength(2)
  expect(parts(DeviceBody({ family: 'troffer' }), 'diffuser')).toHaveLength(1)
  expect(parts(DeviceBody({ family: 'switch' }), 'switch-paddle')).toHaveLength(1)
})

it('lights selected faceplates and fixture lenses while leaving socket contacts readable', () => {
  for (const [family,part] of [['outlet','horizontal-outlet-plate'],['outlet','outlet-backbox'],['switch','switch-paddle'],['troffer','diffuser'],['troffer','fixture-housing'],['linear-light','luminaire-spine'],['panel','panel-door'],['panel','panel-housing']]) {
    const off=parts(DeviceBody({family}),part)[0]
    const on=parts(DeviceBody({family,selected:true}),part)[0]
    expect(off.props.selected).toBe(false)
    expect(on.props.selected).toBe(true)
  }
  const outlet=DeviceBody({family:'outlet',selected:true})
  expect(parts(outlet,'socket-contact').every(p=>!p.props.selected)).toBe(true)
  const off=parts(DeviceBody({family:'linear-light'}),'fluorescent-tube')[0].props.children[1].props
  const on=parts(DeviceBody({family:'linear-light',selected:true}),'fluorescent-tube')[0].props.children[1].props
  expect(on.emissiveIntensity).toBeGreaterThan(off.emissiveIntensity)
  expect(on.emissive).toBe('#ffb94f')
})
