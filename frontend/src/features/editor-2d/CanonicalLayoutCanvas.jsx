import { useEffect, useMemo, useRef, useState } from 'react'
import { Maximize, MousePointer2, Minus, Plus } from 'lucide-react'
import { Button } from '../../components/ui/button.jsx'
import { ViewportFullscreenButton } from '../../components/ViewportFrame.jsx'
import { LegendDeviceGlyph } from '../detection-review/LegendDeviceGlyph.jsx'
import { fetchSymbolLegends } from '../../api/symbolLegends.js'
import { deviceFamily } from '../detection-review/devicePresentation.js'
import { routeAppearance } from '../routing/routeProjection.js'
import {buildWallTopology} from '../../geometry/wallTopology.js'
import {WALL_APPEARANCE} from '../detection-review/wallAppearance.js'
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
  const mode = 'select'
  const panGesture = useRef(null)
  const [viewport, setViewport] = useState({ zoom: 1, x: 0, y: 0 })
  const coordinateSystem = geometry.coordinate_system
  const [legends, setLegends] = useState([])
  useEffect(() => {
    const request = new AbortController()
    fetchSymbolLegends({ signal: request.signal }).then(setLegends).catch(() => {})
    return () => request.abort()
  }, [])

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
  const wallTopology=useMemo(()=>buildWallTopology(geometry.walls.filter(w=>w.thickness_meters>0)
    .map(w=>({...w,thickness:w.thickness_meters}))),[geometry.walls])

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
      <ViewportFullscreenButton />
      <div className="studio-canvas-toolbar" role="toolbar" aria-label="2D viewport tools">
        <span className="studio-canvas-mode"><MousePointer2 size={14} aria-hidden="true" />Select &amp; move</span>
        <span className="studio-toolbar-divider" />
        <Button variant="ghost" size="icon" aria-label="Zoom out" disabled={viewport.zoom <= 1} onClick={() => zoomAt(1 / 1.25)}><Minus aria-hidden="true" /></Button>
        <output className="mono" aria-label="Viewport zoom">{Math.round(viewport.zoom * 100)}%</output>
        <Button variant="ghost" size="icon" aria-label="Zoom in" disabled={viewport.zoom >= 6} onClick={() => zoomAt(1.25)}><Plus aria-hidden="true" /></Button>
        <Button variant="ghost" size="sm" onClick={() => setViewport({ zoom: 1, x: 0, y: 0 })}><Maximize aria-hidden="true" />Fit plan</Button>
      </div>
      <div ref={containerRef} className="layout-canvas-wrap" data-testid="layout-canvas-container"
        onContextMenu={event => event.preventDefault()}
        onPointerDownCapture={event => {
          if (event.button !== 2) return
          event.preventDefault(); event.stopPropagation()
          event.currentTarget.setPointerCapture(event.pointerId)
          panGesture.current = {x:event.clientX,y:event.clientY,viewport}
        }}
        onPointerMoveCapture={event => {
          const pan = panGesture.current
          if (!pan) return
          event.preventDefault(); event.stopPropagation()
          setViewport({...pan.viewport,x:pan.viewport.x+event.clientX-pan.x,y:pan.viewport.y+event.clientY-pan.y})
        }}
        onPointerUpCapture={event => {
          if (!panGesture.current) return
          event.preventDefault(); event.stopPropagation()
          panGesture.current = null
          event.currentTarget.releasePointerCapture(event.pointerId)
        }}
        onPointerCancel={() => { panGesture.current = null }}>
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
            {visibility.wallFootprints && wallTopology.walls.map(wall=><Group key={`footprint-${wall.id}`}>
              {wall.footprints.map((poly,i)=><Line key={`body-${i}`} closed
                points={metricPointsToPixels(poly,coordinateSystem)} fill={WALL_APPEARANCE.normal} strokeWidth={0} />)}
              {wall.boundary.map((edge,i)=><Line key={`edge-${i}`} points={metricPointsToPixels(edge,coordinateSystem)}
                stroke={WALL_APPEARANCE.edge} strokeWidth={1/stage.scale} />)}
            </Group>)}
            {geometry.walls.map((wall) => (
              <Line
                key={wall.id}
                points={metricPointsToPixels([wall.start, wall.end], coordinateSystem)}
                stroke={WALL_APPEARANCE.normal}
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
                  <LegendDeviceGlyph legendId={legends.find(legend => legend.class_id === symbol.class.id)?.id} family={deviceFamily(symbol.class.name)} label={symbol.class.name} color="#c94e28" scale={stage.scale * viewport.zoom} />
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
              name={routeAppearance(segment.kind).label}
              points={metricPointsToPixels([segment.start, segment.end], coordinateSystem)}
              stroke={routeAppearance(segment.kind).color} strokeWidth={Math.max(3 / stage.scale, 1)}
              dash={routeAppearance(segment.kind).dashed ? [5 / stage.scale, 3 / stage.scale] : undefined} />)}
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
      <p className="studio-canvas-status mono">Right-drag to pan · wheel to zoom · {canEdit ? 'changes require saving' : 'inspection only'}</p>
    </section>
  )
}
