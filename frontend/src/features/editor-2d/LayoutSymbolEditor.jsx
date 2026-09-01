import { useState } from 'react'

import { moveCanonicalSymbol } from '../../geometry/canonicalGeometry.js'

function coordinateText(value) {
  return String(value)
}

export function LayoutSymbolEditor({
  geometry,
  selectedSymbolId,
  canEdit,
  disabled = false,
  onSelectSymbol,
  onGeometryChange,
}) {
  const selected = geometry.symbols.find((symbol) => symbol.id === selectedSymbolId) ?? null
  const [form, setForm] = useState({
    symbolId: null, positionX: null, positionY: null,
    xText: '', yText: '', error: '',
  })
  const formMatchesSelected = selected
    && form.symbolId === selected.id
    && form.positionX === selected.position.x
    && form.positionY === selected.position.y
  const xText = formMatchesSelected ? form.xText : selected ? coordinateText(selected.position.x) : ''
  const yText = formMatchesSelected ? form.yText : selected ? coordinateText(selected.position.y) : ''
  const error = formMatchesSelected ? form.error : ''

  function updateField(field, value) {
    if (!selected) return
    setForm({
      symbolId: selected.id,
      positionX: selected.position.x,
      positionY: selected.position.y,
      xText,
      yText,
      error: '',
      [field]: value,
    })
  }

  function setCurrentError(message) {
    if (!selected) return
    setForm({
      symbolId: selected.id,
      positionX: selected.position.x,
      positionY: selected.position.y,
      xText,
      yText,
      error: message,
    })
  }

  function submit(event) {
    event.preventDefault()
    if (!selected || !canEdit || disabled) return
    const x = Number(xText)
    const y = Number(yText)
    if (xText.trim() === '' || yText.trim() === ''
      || !Number.isFinite(x) || !Number.isFinite(y)
      || x < 0 || y < 0
      || x > geometry.coordinate_system.width_meters
      || y > geometry.coordinate_system.height_meters) {
      setCurrentError(
        `Enter X from 0 to ${geometry.coordinate_system.width_meters} and Y from 0 to ${geometry.coordinate_system.height_meters} meters.`,
      )
      return
    }
    try {
      const nextGeometry = moveCanonicalSymbol(geometry, selected.id, { x, y })
      onGeometryChange(nextGeometry)
    } catch {
      setCurrentError('The symbol position is invalid.')
    }
  }

  return (
    <section className="layout-symbol-editor" aria-labelledby="layout-symbol-editor-title">
      <div className="layout-symbol-editor-heading">
        <div>
          <h2 id="layout-symbol-editor-title">Symbols</h2>
          <p>Select a canonical symbol to inspect its authoritative position.</p>
        </div>
        {!canEdit && <span className="layout-inspection-badge">Inspection only</span>}
      </div>

      {geometry.symbols.length === 0 ? (
        <p className="layout-symbol-empty">This layout contains no canonical symbols.</p>
      ) : (
        <div className="layout-symbol-table-wrap">
          <table className="layout-symbol-table">
            <caption className="sr-only">Canonical symbols and their positions in meters</caption>
            <thead>
              <tr><th scope="col">Select</th><th scope="col">ID</th><th scope="col">Class</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">X (m)</th><th scope="col">Y (m)</th></tr>
            </thead>
            <tbody>
              {geometry.symbols.map((symbol) => {
                const isSelected = symbol.id === selectedSymbolId
                return (
                  <tr key={symbol.id} className={isSelected ? 'is-selected' : undefined}>
                    <td>
                      <button
                        type="button"
                        className="layout-symbol-select"
                        aria-pressed={isSelected}
                        onClick={() => onSelectSymbol(symbol.id)}
                      >
                        {isSelected ? 'Selected' : 'Select'}
                      </button>
                    </td>
                    <th scope="row" className="mono">{symbol.id}</th>
                    <td>{symbol.class.name}</td>
                    <td>{symbol.source_type}</td>
                    <td>{symbol.status}</td>
                    <td>{symbol.position.x}</td>
                    <td>{symbol.position.y}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && canEdit && (
        <form className="layout-coordinate-form" onSubmit={submit} noValidate>
          <fieldset disabled={disabled}>
            <legend>Move {selected.id}</legend>
            <label>
              <span>X position (meters)</span>
              <input
                type="text"
                inputMode="decimal"
                value={xText}
                aria-describedby={error ? 'layout-coordinate-error' : undefined}
                onChange={(event) => updateField('xText', event.target.value)}
              />
            </label>
            <label>
              <span>Y position (meters)</span>
              <input
                type="text"
                inputMode="decimal"
                value={yText}
                aria-describedby={error ? 'layout-coordinate-error' : undefined}
                onChange={(event) => updateField('yText', event.target.value)}
              />
            </label>
            <button className="btn btn-dark" type="submit">Apply position</button>
          </fieldset>
          {error && <p id="layout-coordinate-error" className="layout-coordinate-error" role="alert">{error}</p>}
        </form>
      )}
    </section>
  )
}
