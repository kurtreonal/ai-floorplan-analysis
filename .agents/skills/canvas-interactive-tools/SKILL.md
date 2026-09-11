---
name: canvas-interactive-tools
description: >-
  Comprehensive guide and runbook for developing 2D interactive floor plan canvases
  and editor components using Konva.js and React-Konva. Use when implementing 2D canvas
  interactions, layered blueprint overlays, symbol dragging, wall editing, selection gizmos,
  snapping algorithms, pan/zoom viewports, and high-performance React-Konva rendering.
---

# Interactive 2D Canvas Design (Konva.js / React-Konva)

This skill provides expert technical guidance, architectural patterns, and UI/UX best practices for building high-performance, interactive 2D electrical floor plan editors in VED Electrical Services using `Konva.js` and `react-konva`.

---

## 1. Core Principles & Technology Constraints

1. **JavaScript Only (No TypeScript)**: Source files must be `.js` / `.jsx`. No `.ts`, `.tsx`, or TypeScript-only syntax.
2. **Never Bake Overlays into the Blueprint**: The original blueprint raster image remains immutable on Layer 1. All walls, room polygons, symbols, and routes are dynamic vector overlays rendered on separate Konva layers.
3. **Canonical Geometry Contract**: The 2D canvas consumes and emits coordinates in canonical geometry units (meters and source pixel coordinates with explicit scale `pixels_per_meter`). Konva node transforms are transient view state; persisted coordinates must always be canonical.
4. **Subtle Micro-Animations & Sleek Aesthetics**: Use clean visual feedback for selection, hover, dragging, and connection snaps.

---

## 2. Seven-Layer Architecture

Structure the `<Stage>` with strict layer separation:

```jsx
<Stage width={stageWidth} height={stageHeight} onWheel={handleWheel} {...stagePanProps}>
  {/* Layer 1: Immutable uploaded blueprint raster image */}
  <Layer id="layer-blueprint" listening={false}>
    <BlueprintImage image={blueprintImg} />
  </Layer>

  {/* Layer 2: Wall line segments & structural boundaries */}
  <Layer id="layer-walls">
    <WallSegments walls={canonicalGeometry.walls} onWallSelect={handleWallSelect} />
  </Layer>

  {/* Layer 3: Room boundary polygons with subtle transparent fill */}
  <Layer id="layer-rooms" listening={activeTool === 'room'}>
    <RoomPolygons rooms={canonicalGeometry.rooms} />
  </Layer>

  {/* Layer 4: Electrical symbols (outlets, switches, lights, panels) */}
  <Layer id="layer-symbols">
    <SymbolGlyphs
      symbols={canonicalGeometry.symbols}
      selectedId={selectedSymbolId}
      onSelect={handleSymbolSelect}
      onDragEnd={handleSymbolDragEnd}
    />
  </Layer>

  {/* Layer 5: Wiring runs & circuit connections */}
  <Layer id="layer-wiring">
    <WiringRoutes routes={canonicalGeometry.routes} />
  </Layer>

  {/* Layer 6: Conduits & raceways */}
  <Layer id="layer-conduits">
    <ConduitSegments conduits={canonicalGeometry.conduits} />
  </Layer>

  {/* Layer 7: Interactive UI overlays, selection bounds, transformer gizmos */}
  <Layer id="layer-interaction">
    <Transformer ref={transformerRef} {...transformerConfig} />
    <SnappingGuideLines guides={activeGuides} />
    <MeasurementTooltip activeDrag={dragState} />
  </Layer>
</Stage>
```

---

## 3. Coordinate System & Transform Pipeline

Maintain a clear distinction between three coordinate spaces:
1. **Screen / Viewport Space**: Mouse event coordinates on the HTML canvas DOM element (`evt.evt.clientX`, `evt.evt.clientY`).
2. **Stage Space**: Scaled and panned coordinates inside the Konva stage:
   ```javascript
   export function getStagePointerPosition(stage) {
     const transform = stage.getAbsoluteTransform().copy().invert();
     return transform.point(stage.getPointerPosition());
   }
   ```
3. **Canonical Meter Space**: Real-world meters converted via `pixels_per_meter`:
   ```javascript
   export function stagePixelsToMeters(point, pixelsPerMeter) {
     return {
       x: Number((point.x / pixelsPerMeter).toFixed(4)),
       y: Number((point.y / pixelsPerMeter).toFixed(4)),
     };
   }

   export function metersToStagePixels(point, pixelsPerMeter) {
     return {
       x: point.x * pixelsPerMeter,
       y: point.y * pixelsPerMeter,
     };
   }
   ```

---

## 4. Pan & Zoom Viewport Mechanics

Implement smooth, mouse-centered zooming and pan controls:

```javascript
export function handleStageZoom(e, stage, setScale, setPosition) {
  e.evt.preventDefault();
  const scaleBy = 1.1;
  const oldScale = stage.scaleX();
  const pointer = stage.getPointerPosition();

  const mousePointTo = {
    x: (pointer.x - stage.x()) / oldScale,
    y: (pointer.y - stage.y()) / oldScale,
  };

  const newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
  // Clamp zoom between 0.1x and 10x
  const clampedScale = Math.max(0.1, Math.min(newScale, 10));

  setScale(clampedScale);
  setPosition({
    x: pointer.x - mousePointTo.x * clampedScale,
    y: pointer.y - mousePointTo.y * clampedScale,
  });
}
```

---

## 5. Wall Snapping & Alignment

When dragging electrical symbols or drawing walls, calculate snapping points to nearby wall line segments within a threshold (e.g., 10 pixels):

```javascript
export function snapPointToLineSegment(point, lineStart, lineEnd, threshold = 12) {
  const dx = lineEnd.x - lineStart.x;
  const dy = lineEnd.y - lineStart.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return null;

  // Project point onto segment
  const t = Math.max(0, Math.min(1, ((point.x - lineStart.x) * dx + (point.y - lineStart.y) * dy) / lenSq));
  const projX = lineStart.x + t * dx;
  const projY = lineStart.y + t * dy;

  const dist = Math.hypot(point.x - projX, point.y - projY);
  if (dist <= threshold) {
    const angle = Math.atan2(dy, dx);
    return {
      x: projX,
      y: projY,
      wallAngle: angle,
      isSnapped: true,
    };
  }
  return null;
}
```

---

## 6. Selection Transformer & Sleek Visual Gizmos

Configure `Konva.Transformer` with refined dark-mode styling:

```javascript
export const VED_TRANSFORMER_THEME = {
  anchorSize: 8,
  anchorCornerRadius: 4,
  anchorStroke: '#3b82f6',
  anchorFill: '#1e293b',
  anchorStrokeWidth: 1.5,
  borderStroke: '#3b82f6',
  borderStrokeWidth: 1.5,
  borderDash: [4, 4],
  rotateAnchorOffset: 20,
  keepRatio: true,
  enabledAnchors: ['top-left', 'top-right', 'bottom-left', 'bottom-right'],
};
```

---

## 7. Performance Optimizations for Large Drawings

- **`listening={false}` on Static Layers**: Keep the blueprint layer and inactive layers non-listening to bypass hit-detection overhead.
- **Node Caching**: For complex SVG glyphs or symbol clusters, call `.cache()` when not dragging.
- **Debounced Persistence**: During drag, update local Konva position immediately; sync to Redux/backend only on `dragEnd`.
