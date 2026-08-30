import { useState } from 'react'

import {
  detectedSelectionKey,
  manualSelectionKey,
  MANUAL_PRESENTATION,
  REVIEW_PRESENTATION,
  STATUS_PRESENTATION,
} from './detectionCanvasGeometry.js'

function coordinates(symbol) {
  const box = symbol.bounding_box
  return `${box.x_min}, ${box.y_min} → ${box.x_max}, ${box.y_max}`
}

function ClassificationControls({
  selected,
  legends,
  onClassification,
  classificationStatus,
}) {
  const matchingLegend = legends.find((legend) => (
    legend.class_id === selected.authoritative_class.id
    && legend.name === selected.authoritative_class.name
  ))
  const [legendId, setLegendId] = useState(
    matchingLegend ? String(matchingLegend.id) : '',
  )
  const chosenLegend = legends.find((legend) => legend.id === Number(legendId)) || null
  const unchanged = chosenLegend
    && chosenLegend.class_id === selected.authoritative_class.id
    && chosenLegend.name === selected.authoritative_class.name

  return (
    <div className="detection-classification-actions" aria-label="Correct selected detection classification">
      <label htmlFor="symbol-legend-select">Approved symbol class</label>
      {legends.length === 0 ? (
        <p>No approved symbol classes are configured yet. Classification correction is unavailable.</p>
      ) : (
        <>
          <select id="symbol-legend-select" value={legendId} disabled={classificationStatus === 'saving'} onChange={(event) => setLegendId(event.target.value)}>
            <option value="">Choose an approved class</option>
            {legends.map((legend) => <option key={legend.id} value={legend.id}>{legend.class_id} — {legend.name}</option>)}
          </select>
          <button className="btn btn-dark" type="button" disabled={!chosenLegend || unchanged || classificationStatus === 'saving'} onClick={() => onClassification(chosenLegend.id)}>Save corrected class</button>
        </>
      )}
    </div>
  )
}

export function DetectionInspector({
  symbols,
  manualSymbols,
  legends,
  selectedKey,
  onSelect,
  onReview,
  reviewStatus,
  onClassification,
  classificationStatus,
}) {
  const selected = symbols.find(
    (symbol) => detectedSelectionKey(symbol.id) === selectedKey,
  ) || null
  const selectedManual = manualSymbols.find(
    (symbol) => manualSelectionKey(symbol.id) === selectedKey,
  ) || null
  return (
    <section className="detection-inspector" aria-labelledby="detection-list-title">
      <h2 id="detection-list-title">Electrical symbol detections</h2>
      {symbols.length === 0 ? (
        <p>No persisted detections are available for this processing job.</p>
      ) : (
        <div className="detection-table-scroll">
          <table>
            <thead><tr><th>Class</th><th>Machine status</th><th>Designer decision</th><th>Confidence</th><th>Threshold</th><th>Center</th></tr></thead>
            <tbody>
              {symbols.map((symbol) => (
                <tr key={symbol.id} className={detectedSelectionKey(symbol.id) === selectedKey ? 'is-selected' : undefined}>
                  <td><button type="button" onClick={() => onSelect(detectedSelectionKey(symbol.id))}>{symbol.authoritative_class.name}</button></td>
                  <td>{STATUS_PRESENTATION[symbol.status].label}</td>
                  <td>{REVIEW_PRESENTATION[symbol.review?.decision || 'pending'].label}</td>
                  <td>{(symbol.original_confidence * 100).toFixed(1)}%</td>
                  <td>{(symbol.confidence_threshold * 100).toFixed(1)}%</td>
                  <td>{symbol.center.x}, {symbol.center.y}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h2>Manually added symbols</h2>
      {manualSymbols.length === 0 ? (
        <p>No manual symbols are saved for this processing job.</p>
      ) : (
        <div className="detection-table-scroll">
          <table>
            <thead><tr><th>Class</th><th>Status</th><th>Center</th><th>Created</th></tr></thead>
            <tbody>
              {manualSymbols.map((symbol) => (
                <tr key={symbol.id} className={manualSelectionKey(symbol.id) === selectedKey ? 'is-selected' : undefined}>
                  <td><button type="button" onClick={() => onSelect(manualSelectionKey(symbol.id))}>{symbol.authoritative_class.name}</button></td>
                  <td>{MANUAL_PRESENTATION.label}</td>
                  <td>{symbol.center.x}, {symbol.center.y}</td>
                  <td>{symbol.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="detection-details" aria-live="polite">
        <h3>Selected symbol</h3>
        {!selected && !selectedManual ? <p>Select a symbol marker or table row to inspect it.</p> : selected ? (
          <dl>
            <div><dt>Original class</dt><dd>{selected.original_class.id} — {selected.original_class.name}</dd></div>
            <div><dt>Authoritative class</dt><dd>{selected.authoritative_class.id} — {selected.authoritative_class.name}</dd></div>
            <div><dt>Latest correction</dt><dd>{selected.correction ? `${selected.correction.old_class.name} → ${selected.correction.new_class.name}` : 'None'}</dd></div>
            <div><dt>Corrected at</dt><dd>{selected.correction?.corrected_at || 'Not corrected'}</dd></div>
            <div><dt>Original confidence</dt><dd>{selected.original_confidence}</dd></div>
            <div><dt>Applied threshold</dt><dd>{selected.confidence_threshold}</dd></div>
            <div><dt>Machine status</dt><dd>{STATUS_PRESENTATION[selected.status].label}</dd></div>
            <div><dt>Designer decision</dt><dd>{REVIEW_PRESENTATION[selected.review?.decision || 'pending'].label}</dd></div>
            <div><dt>Bounding box</dt><dd>{coordinates(selected)}</dd></div>
            <div><dt>Center</dt><dd>{selected.center.x}, {selected.center.y}</dd></div>
            <div><dt>Detection ID</dt><dd>{selected.id}</dd></div>
            <div><dt>Prediction index</dt><dd>{selected.prediction_index}</dd></div>
            <div><dt>Processing-job ID</dt><dd>{selected.processing_job_id}</dd></div>
          </dl>
        ) : (
          <dl>
            <div><dt>Authoritative class</dt><dd>{selectedManual.authoritative_class.id} â€” {selectedManual.authoritative_class.name}</dd></div>
            <div><dt>Status</dt><dd>{MANUAL_PRESENTATION.label}</dd></div>
            <div><dt>Center</dt><dd>{selectedManual.center.x}, {selectedManual.center.y}</dd></div>
            <div><dt>Image dimensions</dt><dd>{selectedManual.image_width_pixels} Ã— {selectedManual.image_height_pixels} px</dd></div>
            <div><dt>Manual-symbol ID</dt><dd>{selectedManual.id}</dd></div>
            <div><dt>Processing-job ID</dt><dd>{selectedManual.processing_job_id}</dd></div>
            <div><dt>Created</dt><dd>{selectedManual.created_at}</dd></div>
          </dl>
        )}
        {selected && (
          <>
            <ClassificationControls
              key={`${selected.id}:${selected.authoritative_class.id}:${selected.authoritative_class.name}`}
              selected={selected}
              legends={legends}
              onClassification={onClassification}
              classificationStatus={classificationStatus}
            />
            <div className="detection-review-actions" aria-label="Review selected detection">
              <button className="btn btn-dark" type="button" disabled={reviewStatus === 'saving'} onClick={() => onReview('confirmed')}>Confirm detection</button>
              <button className="btn detection-reject-button" type="button" disabled={reviewStatus === 'saving'} onClick={() => onReview('deleted')}>Reject detection</button>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
