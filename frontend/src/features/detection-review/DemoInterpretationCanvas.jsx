import { useEffect, useMemo, useRef, useState } from 'react'
import { Circle, Image as KonvaImage, Layer, Line, Stage } from 'react-konva'

import { fitCanvas } from './detectionCanvasGeometry.js'


function points(boundary) {
  return boundary.flatMap((point) => [point.x, point.y])
}


export function DemoInterpretationCanvas({
  image,
  width,
  height,
  draft,
  selected,
  onSelect,
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
    () => fitCanvas(width, height, availableWidth, 760),
    [availableWidth, height, width],
  )
  const strokeWidth = 3 / stage.scale

  function style(entity, kind) {
    const active = selected?.kind === kind && selected?.id === entity.id
    if (active) return { stroke: '#111827', strokeWidth: 6 / stage.scale }
    if (entity.disposition === 'rejected') {
      return { stroke: '#8b2f2f', strokeWidth, dash: [8 / stage.scale, 5 / stage.scale], opacity: 0.48 }
    }
    return { stroke: kind === 'room' ? '#6d28d9' : kind === 'wall' ? '#06708f' : '#e14c1f', strokeWidth }
  }

  return (
    <section className="demo-canvas-card" aria-label="Unified room wall and symbol review canvas">
      <div ref={containerRef} className="detection-canvas-wrap">
        <Stage width={stage.width} height={stage.height} scaleX={stage.scale} scaleY={stage.scale}>
          <Layer listening={false}>
            <KonvaImage image={image} width={width} height={height} />
          </Layer>
          <Layer>
            {draft.rooms.map((room) => (
              <Line
                key={room.id}
                points={points(room.boundary)}
                closed
                fill={room.disposition === 'accepted' ? 'rgba(109,40,217,0.08)' : undefined}
                {...style(room, 'room')}
                onClick={() => onSelect({ kind: 'room', id: room.id })}
                onTap={() => onSelect({ kind: 'room', id: room.id })}
              />
            ))}
          </Layer>
          <Layer>
            {draft.walls.map((wall) => (
              <Line
                key={wall.id}
                points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
                {...style(wall, 'wall')}
                onClick={() => onSelect({ kind: 'wall', id: wall.id })}
                onTap={() => onSelect({ kind: 'wall', id: wall.id })}
              />
            ))}
          </Layer>
          <Layer>
            {draft.symbols.map((symbol) => (
              <Circle
                key={symbol.id}
                x={symbol.center.x}
                y={symbol.center.y}
                radius={10 / stage.scale}
                fill={symbol.disposition === 'accepted' ? 'rgba(225,76,31,0.28)' : 'rgba(139,47,47,0.12)'}
                {...style(symbol, 'symbol')}
                onClick={() => onSelect({ kind: 'symbol', id: symbol.id })}
                onTap={() => onSelect({ kind: 'symbol', id: symbol.id })}
              />
            ))}
          </Layer>
        </Stage>
      </div>
      <p className="detection-canvas-note">Purple rooms, blue walls, and orange unknown-class symbol proposals share exact normalized source pixels. Dashed red items are rejected but retained in review history.</p>
    </section>
  )
}
