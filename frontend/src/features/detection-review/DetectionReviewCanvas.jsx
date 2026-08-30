import { useEffect, useMemo, useRef, useState } from 'react'
import { Circle, Group, Image as KonvaImage, Layer, Line, Rect, Stage } from 'react-konva'

import {
  fitCanvas,
  detectedSelectionKey,
  manualSelectionKey,
  MANUAL_PRESENTATION,
  stagePointToSource,
  STATUS_PRESENTATION,
  symbolRectangle,
  symbolPresentation,
  wallLinePoints,
} from './detectionCanvasGeometry.js'

export function DetectionReviewCanvas({
  image,
  imageWidth,
  imageHeight,
  walls,
  symbols,
  manualSymbols = [],
  selectedKey,
  onSelect,
  placementMode = false,
  draft = null,
  onPlace = () => {},
}) {
  const containerRef = useRef(null)
  const [availableWidth, setAvailableWidth] = useState(900)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return undefined
    const update = () => setAvailableWidth(Math.max(280, element.clientWidth || 900))
    update()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', update)
      return () => window.removeEventListener('resize', update)
    }
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const stage = useMemo(
    () => fitCanvas(imageWidth, imageHeight, availableWidth, 720),
    [availableWidth, imageHeight, imageWidth],
  )
  const selectedDetected = symbols.find(
    (symbol) => detectedSelectionKey(symbol.id) === selectedKey,
  )
  const selectedManual = manualSymbols.find(
    (symbol) => manualSelectionKey(symbol.id) === selectedKey,
  )

  function place(event) {
    if (!placementMode) return
    const stageNode = event.target.getStage()
    onPlace(stagePointToSource(
      stageNode.getPointerPosition(),
      stage.scale,
      imageWidth,
      imageHeight,
    ))
  }

  function select(event, key) {
    event.cancelBubble = true
    if (!placementMode) onSelect(key)
  }

  return (
    <section className="detection-canvas-card" aria-label="Detection review and manual placement canvas">
      <div ref={containerRef} className="detection-canvas-wrap" data-testid="canvas-container">
        <Stage width={stage.width} height={stage.height} scaleX={stage.scale} scaleY={stage.scale} onClick={place} onTap={place}>
          <Layer listening={false}>
            <KonvaImage image={image} width={imageWidth} height={imageHeight} />
          </Layer>
          <Layer listening={false}>
            {walls.map((wall) => {
              const style = STATUS_PRESENTATION[wall.status]
              return <Line key={wall.id} points={wallLinePoints(wall)} stroke={style.color} strokeWidth={3 / stage.scale} dash={style.dash} />
            })}
          </Layer>
          <Layer>
            {symbols.map((symbol) => {
              const rectangle = symbolRectangle(symbol)
              const style = symbolPresentation(symbol)
              const isDeleted = symbol.review?.decision === 'deleted'
              return (
                <Group key={`detected:${symbol.id}`} onClick={(event) => select(event, detectedSelectionKey(symbol.id))} onTap={(event) => select(event, detectedSelectionKey(symbol.id))}>
                  <Rect {...rectangle} stroke={style.color} strokeWidth={3 / stage.scale} dash={style.dash} fill={isDeleted ? 'rgba(107,114,128,0.22)' : 'rgba(255,255,255,0.08)'} opacity={isDeleted ? 0.72 : 1} />
                  <Circle x={symbol.center.x} y={symbol.center.y} radius={4 / stage.scale} fill={style.color} />
                </Group>
              )
            })}
            {manualSymbols.map((symbol) => (
              <Group key={`manual:${symbol.id}`} onClick={(event) => select(event, manualSelectionKey(symbol.id))} onTap={(event) => select(event, manualSelectionKey(symbol.id))}>
                <Circle x={symbol.center.x} y={symbol.center.y} radius={9 / stage.scale} fill="rgba(124,58,237,0.18)" stroke={MANUAL_PRESENTATION.color} strokeWidth={3 / stage.scale} />
                <Line points={[symbol.center.x - 5 / stage.scale, symbol.center.y, symbol.center.x + 5 / stage.scale, symbol.center.y]} stroke={MANUAL_PRESENTATION.color} strokeWidth={2 / stage.scale} />
                <Line points={[symbol.center.x, symbol.center.y - 5 / stage.scale, symbol.center.x, symbol.center.y + 5 / stage.scale]} stroke={MANUAL_PRESENTATION.color} strokeWidth={2 / stage.scale} />
              </Group>
            ))}
          </Layer>
          <Layer listening={false}>
            {selectedDetected && <Rect {...symbolRectangle(selectedDetected)} stroke="#111827" strokeWidth={6 / stage.scale} dash={[4 / stage.scale, 3 / stage.scale]} />}
            {selectedManual && <Circle x={selectedManual.center.x} y={selectedManual.center.y} radius={14 / stage.scale} stroke="#111827" strokeWidth={4 / stage.scale} dash={[4 / stage.scale, 3 / stage.scale]} />}
            {draft && <Circle x={draft.x} y={draft.y} radius={11 / stage.scale} stroke="#c2410c" strokeWidth={4 / stage.scale} dash={[5 / stage.scale, 3 / stage.scale]} />}
          </Layer>
        </Stage>
      </div>
      <p className="detection-canvas-note">Normalized blueprint reference. Persisted overlays remain in source pixel coordinates.{placementMode ? ' Placement mode is active.' : ''}</p>
    </section>
  )
}
