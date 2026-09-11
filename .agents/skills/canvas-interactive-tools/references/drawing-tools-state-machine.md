# 2D Canvas Interactive State Machine & Tool Modes

This reference documents the interactive tool state machine for the Konva 2D floor plan editor.

---

## 1. Tool Modes Overview

The 2D editor operates in five primary tool modes:

1. **`select` (Default)**:
   - Click to select walls, symbols, or route segments.
   - Click + Drag to move selected symbols with magnetic snapping to nearby walls.
   - Click empty canvas to clear selection.
   - Drag bounding box for multi-select.

2. **`draw_wall`**:
   - Click to establish starting vertex `(x0, y0)`.
   - Mouse move shows dynamic rubber-band preview line with length and angle indicators.
   - Shift key locks angle to orthogonal increments (0°, 45°, 90°, 180°).
   - Click again to finalize wall segment and chain next wall start point.
   - Double-click or `Escape` finishes the wall drawing chain.

3. **`place_symbol`**:
   - Active palette item specifies symbol class (e.g., Duplex Receptacle, Single-Pole Switch).
   - Cursor displays a ghost icon with snapping crosshair.
   - When cursor is near a wall line, snaps directly to the wall segment and computes orientation angle tangent or normal to the wall.
   - Click commits the symbol to canonical geometry with status `manually_added`.

4. **`draw_route`**:
   - Click starting electrical panel or device.
   - Rubber-band preview follows cursor, routing through orthogonal corridors or user waypoints.
   - Click intermediate waypoints or target device to commit conduit/wire run.

5. **`measure`**:
   - Two-point measurement tool displaying calibrated distance in meters and feet using `pixels_per_meter`.

---

## 2. Snapping Algorithm Implementation

```javascript
/**
 * Snaps a 2D stage point to nearby wall segments.
 * @param {{x: number, y: number}} point - Current mouse position in stage pixels.
 * @param {Array<{id: string, start: {x: number, y: number}, end: {x: number, y: number}}>} walls
 * @param {number} threshold - Snapping distance threshold in stage pixels (e.g. 14px).
 * @returns {{x: number, y: number, wallId: string, wallAngle: number} | null}
 */
export function findSnapToWall(point, walls, threshold = 14) {
  let closestSnap = null;
  let minDistance = threshold;

  for (const wall of walls) {
    const dx = wall.end.x - wall.start.x;
    const dy = wall.end.y - wall.start.y;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) continue;

    // Parameter t represents projection onto segment clamped between [0, 1]
    const t = Math.max(0, Math.min(1, ((point.x - wall.start.x) * dx + (point.y - wall.start.y) * dy) / lenSq));
    const projX = wall.start.x + t * dx;
    const projY = wall.start.y + t * dy;

    const dist = Math.hypot(point.x - projX, point.y - projY);
    if (dist < minDistance) {
      minDistance = dist;
      const angle = Math.atan2(dy, dx);
      closestSnap = {
        x: projX,
        y: projY,
        wallId: wall.id,
        wallAngle: angle,
        distance: dist,
      };
    }
  }

  return closestSnap;
}
```

---

## 3. Orthogonal Angle Lock Helper

```javascript
/**
 * Constrains a dynamic line end point to 45-degree or 90-degree increments.
 * @param {{x: number, y: number}} start - Anchor point.
 * @param {{x: number, y: number}} current - Current mouse position.
 * @param {number} snapAngleDeg - Angle increment in degrees (default: 45).
 * @returns {{x: number, y: number}}
 */
export function constrainOrthogonal(start, current, snapAngleDeg = 45) {
  const dx = current.x - start.x;
  const dy = current.y - start.y;
  const distance = Math.hypot(dx, dy);
  if (distance === 0) return current;

  const rawAngle = Math.atan2(dy, dx);
  const stepRad = (snapAngleDeg * Math.PI) / 180;
  const snappedAngle = Math.round(rawAngle / stepRad) * stepRad;

  return {
    x: start.x + distance * Math.cos(snappedAngle),
    y: start.y + distance * Math.sin(snappedAngle),
  };
}
```
