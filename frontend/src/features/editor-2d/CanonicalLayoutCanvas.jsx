import { useEffect, useMemo, useRef, useState } from 'react'
import { Hand, Maximize, MousePointer2, Minus, Plus } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'
import { DeviceGlyph } from '../detection-review/DeviceGlyph.jsx'
import { deviceFamily } from '../detection-review/devicePresentation.js'
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
  clampSourcePixelPoint,
  fitSourcePlane,
  metricPointToPixel,
  metricPointsToPixels,
  sourcePixelPointToMetric,
} from './layoutCanvasGeometry.js'

export function CanonicalLayoutCanvas({
  geometry,
  routeSegments = [],
  blueprintImage,
  visibility,
  selectedSymbolId = null,
  canEdit = false,
  editDisabled = false,
  onSelectSymbol = () => {},
  onMoveSymbol = () => {},
}) {
  const containerRef = useRef(null)
  const [availableWidth, setAvailableWidth] = useState(960)
  const [mode, setMode] = useState('select')
  const [viewport, setViewport] = useState({ zoom: 1, x: 0, y: 0 })
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
  const selectedSymbol = geometry.symbols.find((symbol) => symbol.id === selectedSymbolId) ?? null

  function zoomAt(factor, pointer = { x: stage.width / 2, y: stage.height / 2 }) {
    setViewport((current) => {
      const zoom = Math.max(1, Math.min(6, current.zoom * factor))
      const ratio = zoom / current.zoom
      return { zoom, x: pointer.x - (pointer.x - current.x) * ratio, y: pointer.y - (pointer.y - current.y) * ratio }
    })
  }

  function handleWheel(event) {
    event.evt.preventDefault()
    const pointer = event.target.getStage().getPointerPosition()
    if (pointer) zoomAt(event.evt.deltaY < 0 ? 1.15 : 1 / 1.15, pointer)
  }

  function clampDraggedNode(event) {
    const node = event.target
    const bounded = clampSourcePixelPoint(node.position(), coordinateSystem)
    node.position(bounded)
    return bounded
  }

  function finishSymbolMove(symbolId, event) {
    const bounded = clampDraggedNode(event)
    onMoveSymbol(symbolId, sourcePixelPointToMetric(bounded, coordinateSystem))
  }

  return (
    <section className="layout-canvas-card" aria-label="Current canonical 2D layout canvas">
      <div className="studio-canvas-toolbar" role="toolbar" aria-label="2D viewport tools">
        <Button variant={mode === 'select' ? 'secondary' : 'ghost'} size="sm" aria-pressed={mode === 'select'} onClick={() => setMode('select')}><MousePointer2 aria-hidden="true" />Select</Button>
        <Button variant={mode === 'pan' ? 'secondary' : 'ghost'} size="sm" aria-pressed={mode === 'pan'} onClick={() => setMode('pan')}><Hand aria-hidden="true" />Pan</Button>
        <span className="studio-toolbar-divider" />
        <Button variant="ghost" size="icon" aria-label="Zoom out" disabled={viewport.zoom <= 1} onClick={() => zoomAt(1 / 1.25)}><Minus aria-hidden="true" /></Button>
        <output className="mono" aria-label="Viewport zoom">{Math.round(viewport.zoom * 100)}%</output>
        <Button variant="ghost" size="icon" aria-label="Zoom in" disabled={viewport.zoom >= 6} onClick={() => zoomAt(1.25)}><Plus aria-hidden="true" /></Button>
        <Button variant="ghost" size="sm" onClick={() => setViewport({ zoom: 1, x: 0, y: 0 })}><Maximize aria-hidden="true" />Fit plan</Button>
      </div>
      <div ref={containerRef} className="layout-canvas-wrap" data-testid="layout-canvas-container">
        <Stage
          width={stage.width}
          height={stage.height}
          scaleX={stage.scale * viewport.zoom}
          scaleY={stage.scale * viewport.zoom}
          x={viewport.x}
          y={viewport.y}
          draggable={mode === 'pan'}
          onWheel={handleWheel}
          onDragEnd={(event) => {
            if (event.target === event.target.getStage()) setViewport((current) => ({ ...current, x: event.target.x(), y: event.target.y() }))
          }}
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

          <Layer name="symbols" visible={visibility.symbols} listening={visibility.symbols && mode === 'select'}>
            {geometry.symbols.map((symbol) => {
              const point = metricPointToPixel(symbol.position, coordinateSystem)
              const manual = symbol.source_type === 'manual'
              return (
                <Group
                  key={symbol.id}
                  name={`canonical-symbol-${symbol.id}`}
                  x={point.x}
                  y={point.y}
                  draggable={canEdit && !editDisabled && visibility.symbols && mode === 'select'}
                  onClick={() => onSelectSymbol(symbol.id)}
                  onTap={() => onSelectSymbol(symbol.id)}
                  onDragStart={() => onSelectSymbol(symbol.id)}
                  onDragMove={clampDraggedNode}
                  onDragEnd={(event) => finishSymbolMove(symbol.id, event)}
                >
                  <Circle
                    radius={Math.max(7 / stage.scale, 3)}
                    fill={manual ? '#7c3aed' : '#d9480f'}
                    stroke="#ffffff"
                    strokeWidth={Math.max(2 / stage.scale, 1)}
                  />
                  <DeviceGlyph family={deviceFamily(symbol.class.name)} color="#c94e28" scale={stage.scale * viewport.zoom} />
                  <Text
                    text={`${symbol.class.name} · ${manual ? 'manual' : 'reviewed'}`}
                    x={18 / (stage.scale * viewport.zoom)}
                    y={-6 / (stage.scale * viewport.zoom)}
                    fontSize={11 / (stage.scale * viewport.zoom)}
                    fill="#17202a"
                    listening={false}
                  />
                </Group>
              )
            })}
          </Layer>

          <Layer name="routes" visible={visibility.routes} listening={false}>
            {routeSegments.map((segment, index) => <Line key={`generated-${index}`}
              points={metricPointsToPixels([segment.start, segment.end], coordinateSystem)}
              stroke="#00897b" strokeWidth={Math.max(3 / stage.scale, 1)} />)}
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

          <Layer name="selection-ui" listening={false}>
            {selectedSymbol && visibility.symbols && (() => {
              const point = metricPointToPixel(selectedSymbol.position, coordinateSystem)
              return (
                <Circle
                  name="selected-symbol-outline"
                  x={point.x}
                  y={point.y}
                  radius={Math.max(12 / stage.scale, 5)}
                  stroke="#0b63ce"
                  strokeWidth={Math.max(2 / stage.scale, 1)}
                  dash={[4 / stage.scale, 3 / stage.scale]}
                />
              )
            })()}
          </Layer>
        </Stage>
      </div>
      <p className="studio-canvas-status mono">{mode === 'pan' ? 'Drag to pan · wheel to zoom' : canEdit ? 'Select or drag a symbol · changes require saving' : 'Inspection only · select a symbol for its saved position'} · viewport changes do not alter measurements</p>
    </section>
  )
}
