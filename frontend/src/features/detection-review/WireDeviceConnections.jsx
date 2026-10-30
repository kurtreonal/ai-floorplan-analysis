import { findWireDeviceSnap } from './deviceConnections.js'
import { orderNamed } from '../../utils/listOrder.js'
import { Button } from '../../components/ui/button.jsx'

// Keyboard/click alternative to dragging; both use the same eligibility rules.
export function WireDeviceConnections({ wire, draft, presentations, onConnect, onDetach, disabled,focus=false,focusEndpoint=null }) {
  return <details open={focus || undefined} data-wire-connections><summary>Start &amp; end connections</summary>
    {[0,wire.points.length-1].map((index,i) => {
      const attachment = (wire.device_attachments || []).find(a => a.point_index === index)
      const devicePresent=attachment && draft.symbols.some(s=>s.id===attachment.symbol_id && s.disposition!=='rejected')
      const junction=(wire.junction_attachments || []).find(a=>a.point_index===index)
      const options = orderNamed((draft.symbols || []).flatMap(symbol => {
        const snap = findWireDeviceSnap(symbol.center,wire.id,index,draft,presentations,0,null,symbol.id)
        return snap?.symbolId === symbol.id ? [{symbol,snap}] : []
      }), ({symbol}) => presentations[symbol.id]?.label || symbol.id)
      const attention=focus && (focusEndpoint==null || focusEndpoint===index)
      const intended=options.find(o=>o.symbol.id===(i?wire.target_kind==='device'?wire.target_id:null:wire.source_device_id))
      return <div key={index} className={attention?'wiring-setting-attention':undefined}>
        {attention && <strong>{i?'End connection':'Start connection'} needs a device or wire</strong>}
        <label>{i ? 'End device' : 'Start device'}<select data-wire-connection={index} autoFocus={attention} disabled={disabled} value={attachment?.symbol_id || (junction?'__junction__':'')}
          onChange={event => { const option = options.find(o => o.symbol.id === event.target.value); if (option) onConnect(index,option.snap) }}>
          <option value="" disabled>Not connected</option>
          {junction && !attachment && <option value="__junction__" disabled>Connected to another wire</option>}
          {attachment && !options.some(o => o.symbol.id === attachment.symbol_id) &&
            <option value={attachment.symbol_id} disabled>{presentations[attachment.symbol_id]?.label || attachment.symbol_id} · {devicePresent?'connected':'device missing'}</option>}
          {options.map(({symbol}) => <option key={symbol.id} value={symbol.id}>{presentations[symbol.id]?.label || symbol.id} · {symbol.id}</option>)}
        </select></label>
        {attention && !attachment && !junction && intended && <Button variant="outline" disabled={disabled} onClick={()=>onConnect(index,intended.snap)}>Connect to {presentations[intended.symbol.id]?.label || intended.symbol.id}</Button>}
        {attachment && <Button variant="ghost" disabled={disabled} onClick={() => onDetach(index)}>Disconnect {i ? 'end' : 'start'}</Button>}
      </div>
    })}
    <p>{focus?'The orange point on the plan is the connection to fix. Choose its device here or drag that point until it snaps to a device or wire.':'Choose a start/end device here, or snap the endpoint to an existing wire.'}</p>
  </details>
}
