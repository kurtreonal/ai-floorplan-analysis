import { useEffect, useMemo, useRef, useState } from 'react'
import { Circle, Group, Image as KonvaImage, Layer, Line, Rect, Stage } from 'react-konva'

import {
  fitCanvas,
  STATUS_PRESENTATION,
  symbolRectangle,
  symbolPresentation,
  wallLinePoints,
} from './detectionCanvasGeometry.js'

export function DetectionReviewCanvas({ image, imageWidth, imageHeight, walls, symbols, selectedId, onSelect }) {
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
  const selected = symbols.find((symbol) => symbol.id === selectedId)

  return (
    <section className="detection-canvas-card" aria-label="Read-only detection canvas">
      <div ref={containerRef} className="detection-canvas-wrap" data-testid="canvas-container">
        <Stage width={stage.width} height={stage.height} scaleX={stage.scale} scaleY={stage.scale}>
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
                <Group key={symbol.id} onClick={() => onSelect(symbol.id)} onTap={() => onSelect(symbol.id)}>
                  <Rect {...rectangle} stroke={style.color} strokeWidth={3 / stage.scale} dash={style.dash} fill={isDeleted ? 'rgba(107,114,128,0.22)' : 'rgba(255,255,255,0.08)'} opacity={isDeleted ? 0.72 : 1} />
                  <Circle x={symbol.center.x} y={symbol.center.y} radius={4 / stage.scale} fill={style.color} />
                </Group>
              )
            })}
          </Layer>
          <Layer listening={false}>
            {selected && <Rect {...symbolRectangle(selected)} stroke="#111827" strokeWidth={6 / stage.scale} dash={[4 / stage.scale, 3 / stage.scale]} />}
          </Layer>
        </Stage>
      </div>
      <p className="detection-canvas-note">Normalized blueprint reference. Overlays are read-only and remain in source pixel coordinates.</p>
    </section>
  )
}
