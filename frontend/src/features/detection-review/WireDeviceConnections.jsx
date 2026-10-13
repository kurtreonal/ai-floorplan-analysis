import { findWireDeviceSnap } from './deviceConnections.js'
import { orderNamed } from '../../utils/listOrder.js'
import { Button } from '../../components/ui/button.jsx'

// Keyboard/click alternative to dragging; both use the same eligibility rules.
export function WireDeviceConnections({ wire, draft, presentations, onConnect, onDetach, disabled }) {
  return <details><summary>Device connections</summary>
    {[0,wire.points.length-1].map((index,i) => {
      const attachment = (wire.device_attachments || []).find(a => a.point_index === index)
      const options = orderNamed((draft.symbols || []).flatMap(symbol => {
        const snap = findWireDeviceSnap(symbol.center,wire.id,index,draft,presentations,0)
        return snap?.symbolId === symbol.id ? [{symbol,snap}] : []
      }), ({symbol}) => presentations[symbol.id]?.label || symbol.id)
      return <div key={index}>
        <label>{i ? 'End device' : 'Start device'}<select disabled={disabled} value={attachment?.symbol_id || ''}
          onChange={event => { const option = options.find(o => o.symbol.id === event.target.value); if (option) onConnect(index,option.snap) }}>
          <option value="" disabled>Not connected</option>
          {attachment && !options.some(o => o.symbol.id === attachment.symbol_id) &&
            <option value={attachment.symbol_id} disabled>{presentations[attachment.symbol_id]?.label || attachment.symbol_id} · connected</option>}
          {options.map(({symbol}) => <option key={symbol.id} value={symbol.id}>{presentations[symbol.id]?.label || symbol.id} · {symbol.id}</option>)}
        </select></label>
        {attachment && <Button variant="ghost" disabled={disabled} onClick={() => onDetach(index)}>Disconnect {i ? 'end' : 'start'}</Button>}
      </div>
    })}
    <p>Touching endpoints connect automatically. Green magnets guide manual edits. Disconnect stays disconnected; ambiguous contacts need review.</p>
  </details>
}
