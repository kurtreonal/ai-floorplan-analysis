import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Circle,
  Group,
  Image as KonvaImage,
  Layer,
  Line,
  Rect,
  Stage,
  Text,
} from 'react-konva'

import {
  fitSourcePlane,
  metricPointToPixel,
  metricPointsToPixels,
} from './layoutCanvasGeometry.js'

export function CanonicalLayoutCanvas({ geometry, blueprintImage, visibility }) {
  const containerRef = useRef(null)
  const [availableWidth, setAvailableWidth] = useState(960)
  const coordinateSystem = geometry.coordinate_system

  useEffect(() => {
    const element = containerRef.current
    if (!element) return undefined
    const update = () => setAvailableWidth(Math.max(280, element.clientWidth || 960))
    update()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', update)
      return () => window.removeEventListener('resize', update)
    }
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const stage = useMemo(() => fitSourcePlane(
    coordinateSystem.image_width_pixels,
    coordinateSystem.image_height_pixels,
    availableWidth,
    760,
  ), [availableWidth, coordinateSystem.image_height_pixels, coordinateSystem.image_width_pixels])

  return (
    <section className="layout-canvas-card" aria-label="Current canonical 2D layout canvas">
      <div ref={containerRef} className="layout-canvas-wrap" data-testid="layout-canvas-container">
        <Stage
          width={stage.width}
          height={stage.height}
          scaleX={stage.scale}
          scaleY={stage.scale}
        >
          <Layer name="blueprint" visible={visibility.blueprint} listening={false}>
            <Rect
              x={0}
              y={0}
              width={coordinateSystem.image_width_pixels}
              height={coordinateSystem.image_height_pixels}
              fill="#f3f4f6"
            />
            {blueprintImage && (
              <KonvaImage
                image={blueprintImage}
                width={coordinateSystem.image_width_pixels}
                height={coordinateSystem.image_height_pixels}
              />
            )}
          </Layer>

          <Layer name="walls" visible={visibility.walls} listening={false}>
            {geometry.walls.map((wall) => (
              <Line
                key={wall.id}
                points={metricPointsToPixels([wall.start, wall.end], coordinateSystem)}
                stroke={wall.status === 'verified' ? '#136f63' : '#355070'}
                strokeWidth={Math.max(2 / stage.scale, 1)}
                dash={wall.status === 'verified' ? [] : [7 / stage.scale, 3 / stage.scale]}
              />
            ))}
          </Layer>

          <Layer name="rooms" visible={visibility.rooms} listening={false}>
            {geometry.rooms.map((room) => (
              <Line
                key={room.id}
                points={metricPointsToPixels(room.boundary, coordinateSystem)}
                closed
                fill="rgba(51, 105, 152, 0.08)"
                stroke="#336998"
                strokeWidth={Math.max(1.5 / stage.scale, 0.75)}
              />
            ))}
          </Layer>

          <Layer name="symbols" visible={visibility.symbols} listening={false}>
            {geometry.symbols.map((symbol) => {
              const point = metricPointToPixel(symbol.position, coordinateSystem)
              const manual = symbol.source_type === 'manual'
              return (
                <Group key={symbol.id} x={point.x} y={point.y}>
                  <Circle
                    radius={Math.max(7 / stage.scale, 3)}
                    fill={manual ? '#7c3aed' : '#d9480f'}
                    stroke="#ffffff"
                    strokeWidth={Math.max(2 / stage.scale, 1)}
                  />
                  <Text
                    text={manual ? 'M' : 'D'}
                    x={5 / stage.scale}
                    y={-11 / stage.scale}
                    fontSize={11 / stage.scale}
                    fill="#17202a"
                  />
                </Group>
              )
            })}
          </Layer>

          <Layer name="routes" visible={visibility.routes} listening={false}>
            {geometry.routes.map((route) => (
              <Line
                key={route.id}
                points={metricPointsToPixels(route.points, coordinateSystem)}
                stroke="#8a5a00"
                strokeWidth={Math.max(2 / stage.scale, 1)}
                dash={[9 / stage.scale, 4 / stage.scale]}
              />
            ))}
          </Layer>

          <Layer name="selection-ui" listening={false} />
        </Stage>
      </div>
    </section>
  )
}
