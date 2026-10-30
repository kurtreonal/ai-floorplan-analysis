import {roomMeasurements,roomMeasurementLabels} from './roomMeasurements.js'

export function RoomMeasurementSummary({room,pixelsPerMeter,unit='m'}) {
  const measure=roomMeasurements(room.boundary,pixelsPerMeter),labels=roomMeasurementLabels(measure,unit)
  return <section className="room-measurement-summary" aria-label="Room measurements"><h4>Room measurements</h4><dl><div><dt>Area</dt><dd>{labels.area}</dd></div>{measure?.scaled && <><div><dt>{measure.rectangular?'Size':'Overall width × depth'}</dt><dd>{labels.dimensions}</dd></div><div><dt>Perimeter</dt><dd>{labels.perimeter}</dd></div></>}</dl>{measure?.scaled && !measure.rectangular && <p>Area follows the room outline. Side lengths appear on the selected room.</p>}</section>
}
