import { STATUS_PRESENTATION } from './detectionCanvasGeometry.js'

function coordinates(symbol) {
  const box = symbol.bounding_box
  return `${box.x_min}, ${box.y_min} → ${box.x_max}, ${box.y_max}`
}

export function DetectionInspector({ symbols, selectedId, onSelect }) {
  const selected = symbols.find((symbol) => symbol.id === selectedId) || null
  return (
    <section className="detection-inspector" aria-labelledby="detection-list-title">
      <h2 id="detection-list-title">Electrical symbol detections</h2>
      {symbols.length === 0 ? (
        <p>No persisted detections are available for this processing job.</p>
      ) : (
        <div className="detection-table-scroll">
          <table>
            <thead><tr><th>Class</th><th>Status</th><th>Confidence</th><th>Threshold</th><th>Center</th></tr></thead>
            <tbody>
              {symbols.map((symbol) => (
                <tr key={symbol.id} className={symbol.id === selectedId ? 'is-selected' : undefined}>
                  <td><button type="button" onClick={() => onSelect(symbol.id)}>{symbol.original_class.name}</button></td>
                  <td>{STATUS_PRESENTATION[symbol.status].label}</td>
                  <td>{(symbol.original_confidence * 100).toFixed(1)}%</td>
                  <td>{(symbol.confidence_threshold * 100).toFixed(1)}%</td>
                  <td>{symbol.center.x}, {symbol.center.y}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="detection-details" aria-live="polite">
        <h3>Selected detection</h3>
        {!selected ? <p>Select a symbol box or table row to inspect it.</p> : (
          <dl>
            <div><dt>Original class</dt><dd>{selected.original_class.id} — {selected.original_class.name}</dd></div>
            <div><dt>Original confidence</dt><dd>{selected.original_confidence}</dd></div>
            <div><dt>Applied threshold</dt><dd>{selected.confidence_threshold}</dd></div>
            <div><dt>Status</dt><dd>{STATUS_PRESENTATION[selected.status].label}</dd></div>
            <div><dt>Bounding box</dt><dd>{coordinates(selected)}</dd></div>
            <div><dt>Center</dt><dd>{selected.center.x}, {selected.center.y}</dd></div>
            <div><dt>Detection ID</dt><dd>{selected.id}</dd></div>
            <div><dt>Prediction index</dt><dd>{selected.prediction_index}</dd></div>
            <div><dt>Processing-job ID</dt><dd>{selected.processing_job_id}</dd></div>
          </dl>
        )}
      </div>
    </section>
  )
}
