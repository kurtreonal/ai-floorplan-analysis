import { LAYOUT_LAYER_LABELS } from './layoutLayers.js'

export function LayoutLayerControls({ visibility, onChange }) {
  return (
    <fieldset className="layout-layer-controls">
      <legend>Layer visibility</legend>
      {Object.entries(LAYOUT_LAYER_LABELS).map(([key, label]) => (
        <label key={key}>
          <input
            type="checkbox"
            checked={visibility[key]}
            onChange={() => onChange(key)}
          />
          <span>{label}</span>
        </label>
      ))}
    </fieldset>
  )
}
