import { useId, useRef } from 'react'
import { Button } from '../../components/ui/button.jsx'
import { MAX_ROUTE_OBSTACLES, OBSTACLE_FIELDS, routeObstacleRowError } from './routeObstacles.js'

const LABELS = {
  min_x: 'minimum x', min_y: 'minimum y', max_x: 'maximum x', max_y: 'maximum y',
  bottom: 'bottom elevation', top: 'top elevation',
}

export function RoutingObstacles({ rows, onChange, disabled = false, scope = 'Circuit' }) {
  const groupId = useId()
  const nextId = useRef(Math.max(0, ...rows.map((row) => row.row_id)) + 1)
  function add() {
    if (disabled || rows.length >= MAX_ROUTE_OBSTACLES) return
    onChange([...rows, { row_id: nextId.current++, ...Object.fromEntries(OBSTACLE_FIELDS.map((key) => [key, ''])) }])
  }
  function change(rowId, key, value) {
    if (!disabled) onChange(rows.map((row) => row.row_id === rowId ? { ...row, [key]: value } : row))
  }
  return <fieldset disabled={disabled} aria-label={`${scope} routing obstacles`}>
    <legend>{scope} routing obstacles</legend>
    <p>Enter rectangular barriers in this floor’s saved x/y coordinates and absolute elevations, in meters. These bounds constrain the service path and vertical passages. Empty means no additional entered barriers.</p>
    <p>{rows.length}/{MAX_ROUTE_OBSTACLES} obstacles</p>
    {rows.map((row, index) => {
      const error = routeObstacleRowError(row)
      const errorId = `${groupId}-${row.row_id}-error`
      return <fieldset key={row.row_id} aria-describedby={error ? errorId : undefined}>
        <legend>{scope} obstacle {index + 1}</legend>
        {OBSTACLE_FIELDS.map((key) => <label className="studio-field" key={key}>
          {scope} obstacle {index + 1} {LABELS[key]} (m)
          <input type="number" step="any" required value={row[key]}
            aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}
            onChange={(event) => change(row.row_id, key, event.target.value)} />
        </label>)}
        {error && <p id={errorId}>{error}</p>}
        <Button variant="outline" disabled={disabled} onClick={() => {
          if (!disabled) onChange(rows.filter((item) => item.row_id !== row.row_id))
        }}>Remove {scope.toLowerCase()} obstacle {index + 1}</Button>
      </fieldset>
    })}
    <Button variant="outline" disabled={disabled || rows.length >= MAX_ROUTE_OBSTACLES} onClick={add}>Add {scope.toLowerCase()} obstacle</Button>
  </fieldset>
}
