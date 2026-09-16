import { useEffect, useMemo, useRef, useState } from 'react'
import { Circle, Group, Image as KonvaImage, Layer, Line, Stage, Text } from 'react-konva'

import { fitCanvas } from './detectionCanvasGeometry.js'
import {
  constrainPoint,
  findSnapPoint,
  formatWallDimension,
  wallMidpoint,
  wallTextRotation,
} from './wallEditorUtils.js'

function roomPoints(boundary) {
  return boundary.flatMap((point) => [point.x, point.y])
}

export function DemoInterpretationCanvas({
  image,
  width,
  height,
  draft,
  selected,
  onSelect,
  layers = { source: true, rooms: false, walls: true, symbols: false },
  tool = 'move',
  onToolChange,
  onAddWall,
  onUpdateWall,
  onDeleteWall,
  onUpdateRoom,
  scaleMeters = null,
  blueprintOpacity = 1.0,
}) {
  const containerRef = useRef(null)
  const stageRef = useRef(null)
  const [containerSize, setContainerSize] = useState({ width: 900, height: 600 })
  const defaultFit = useMemo(() => {
    if (!width || !height || !containerSize.width || !containerSize.height) {
      return { scale: 1, x: 0, y: 0 }
    }
    const fit = fitCanvas(width, height, containerSize.width, containerSize.height)
    const initialX = Math.round((containerSize.width - fit.width) / 2)
    const initialY = Math.round((containerSize.height - fit.height) / 2)
    return { scale: fit.scale, x: initialX, y: initialY }
  }, [width, height, containerSize.width, containerSize.height])

  const [userTransform, setUserTransform] = useState(null)
  const stageTransform = userTransform || defaultFit
  const [drawingStart, setDrawingStart] = useState(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [isShiftHeld, setIsShiftHeld] = useState(false)
  const [isSpaceHeld, setIsSpaceHeld] = useState(false)

  // Measure container dimensions
  useEffect(() => {
    const element = containerRef.current
    if (!element) return undefined
    const update = () => {
      const w = Math.max(320, element.clientWidth || 900)
      const h = Math.max(380, element.clientHeight || 600)
      setContainerSize({ width: w, height: h })
    }
    update()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', update)
      return () => window.removeEventListener('resize', update)
    }
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  // Keyboard handlers: Escape to cancel drawing, Delete/Backspace to delete wall, Shift constraint, Space to pan
  useEffect(() => {
    function handleKeyDown(event) {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName)) return
      if (event.key === 'Shift') setIsShiftHeld(true)
      if (event.code === 'Space') setIsSpaceHeld(true)
      if (event.key === 'Escape') {
        if (drawingStart) {
          setDrawingStart(null)
        } else if (tool !== 'move') {
          onToolChange?.('move')
        }
      } else if (event.key === 'Delete' || event.key === 'Backspace') {
        if (selected?.kind === 'wall' && onDeleteWall) {
          event.preventDefault()
          onDeleteWall(selected.id)
        }
      }
    }
    function handleKeyUp(event) {
      if (event.key === 'Shift') setIsShiftHeld(false)
      if (event.code === 'Space') setIsSpaceHeld(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
    }
  }, [drawingStart, tool, selected, onDeleteWall, onToolChange])

  // Map pointer to source-image pixels via stage inverse transform
  function getSourcePoint(stage) {
    if (!stage) return null
    const pointer = stage.getPointerPosition()
    if (!pointer) return null
    const transform = stage.getAbsoluteTransform().copy().invert()
    const p = transform.point(pointer)
    return {
      x: Math.max(0, Math.min(width, Math.round(p.x))),
      y: Math.max(0, Math.min(height, Math.round(p.y))),
    }
  }

  // Zoom with mouse wheel centered on pointer
  function handleWheel(event) {
    event.evt.preventDefault()
    const stage = stageRef.current
    if (!stage) return
    const pointer = stage.getPointerPosition()
    if (!pointer) return

    const oldScale = stageTransform.scale
    const zoomFactor = event.evt.deltaY < 0 ? 1.1 : 0.909
    const newScale = Math.min(8, Math.max(0.1, oldScale * zoomFactor))

    const newX = pointer.x - (pointer.x - stageTransform.x) * (newScale / oldScale)
    const newY = pointer.y - (pointer.y - stageTransform.y) * (newScale / oldScale)

    setUserTransform({ scale: newScale, x: newX, y: newY })
  }

  // Fit to screen helper (resets user transform back to default fit)
  const handleFit = () => {
    setUserTransform(null)
  }

  // Zoom by step helper (+ or -)
  const handleZoomStep = (factor) => {
    const center = { x: containerSize.width / 2, y: containerSize.height / 2 }
    const oldScale = stageTransform.scale
    const newScale = Math.min(8, Math.max(0.1, oldScale * factor))
    const newX = center.x - (center.x - stageTransform.x) * (newScale / oldScale)
    const newY = center.y - (center.y - stageTransform.y) * (newScale / oldScale)
    setUserTransform({ scale: newScale, x: newX, y: newY })
  }

  // Snap candidate calculation
  const snapThreshold = 14 / stageTransform.scale
  const snap = useMemo(() => {
    if (tool !== 'draw' && tool !== 'move') return { x: 0, y: 0, snapped: false }
    return findSnapPoint(mousePos, draft.walls, {
      threshold: snapThreshold,
      excludeWallId: selected?.kind === 'wall' ? selected.id : null,
    })
  }, [mousePos, draft.walls, snapThreshold, tool, selected])

  // Current effective point (with snap and shift constraint)
  const effectivePoint = useMemo(() => {
    if (snap.snapped) return { x: snap.x, y: snap.y }
    if (isShiftHeld && drawingStart) {
      return constrainPoint(drawingStart, mousePos, true)
    }
    return mousePos
  }, [snap, isShiftHeld, drawingStart, mousePos])

  // Mouse move on stage
  function handleMouseMove() {
    const stage = stageRef.current
    const point = getSourcePoint(stage)
    if (point) setMousePos(point)
  }

  // Stage click (for drawing walls or clearing selection)
  function handleStageClick(event) {
    // If user clicked directly on stage or background image
    const clickedOnEmpty = event.target === stageRef.current || event.target.name() === 'blueprint-image'

    if (tool === 'draw') {
      if (!drawingStart) {
        setDrawingStart(effectivePoint)
      } else {
        const length = Math.hypot(effectivePoint.x - drawingStart.x, effectivePoint.y - drawingStart.y)
        if (length >= 5 && onAddWall) {
          onAddWall({
            start: drawingStart,
            end: effectivePoint,
            estimated_thickness_pixels: 12,
          })
        }
        setDrawingStart(null)
      }
      return
    }

    if (clickedOnEmpty) {
      onSelect?.(null)
    }
  }

  // Cursor style based on active tool and mode
  const cursorStyle = useMemo(() => {
    if (isSpaceHeld) return 'grab'
    if (tool === 'draw') return 'crosshair'
    if (tool === 'delete') return 'pointer'
    return 'default'
  }, [isSpaceHeld, tool])

  return (
    <section className="demo-canvas-card" aria-label="Unified room wall and symbol review canvas">
      <div className="demo-canvas-viewport-controls">
        <button type="button" className="btn-canvas-mini" onClick={() => handleZoomStep(1.2)} title="Zoom In" aria-label="Zoom In">+</button>
        <button type="button" className="btn-canvas-mini" onClick={() => handleZoomStep(0.833)} title="Zoom Out" aria-label="Zoom Out">−</button>
        <button type="button" className="btn-canvas-mini" onClick={handleFit} title="Fit to screen" aria-label="Fit to screen">Fit</button>
        <span className="demo-zoom-label">{Math.round(stageTransform.scale * 100)}%</span>
      </div>

      <div
        ref={containerRef}
        className="detection-canvas-wrap demo-canvas-grid-wrap"
        style={{ cursor: cursorStyle }}
      >
        <Stage
          ref={stageRef}
          width={containerSize.width}
          height={containerSize.height}
          x={stageTransform.x}
          y={stageTransform.y}
          scaleX={stageTransform.scale}
          scaleY={stageTransform.scale}
          draggable={isSpaceHeld || tool === 'move'}
          onWheel={handleWheel}
          onMouseMove={handleMouseMove}
          onClick={handleStageClick}
          onTap={handleStageClick}
          onDragEnd={(e) => {
            if (e.target === stageRef.current) {
              setUserTransform({ scale: stageTransform.scale, x: e.target.x(), y: e.target.y() })
            }
          }}
        >
          {/* Blueprint Layer */}
          <Layer listening={false}>
            {layers.source && image && (
              <KonvaImage
                name="blueprint-image"
                image={image}
                width={width}
                height={height}
                opacity={blueprintOpacity}
              />
            )}
          </Layer>

          {/* Rooms Layer */}
          <Layer>
            {layers.rooms && draft.rooms.map((room) => (
              <Line
                key={room.id}
                points={roomPoints(room.boundary)}
                closed
                fill={room.disposition === 'accepted' ? 'rgba(109,40,217,0.12)' : 'rgba(139,47,47,0.06)'}
                stroke={selected?.kind === 'room' && selected?.id === room.id ? '#2563eb' : '#7c3aed'}
                strokeWidth={selected?.kind === 'room' && selected?.id === room.id ? 4 / stageTransform.scale : 2 / stageTransform.scale}
                dash={room.disposition === 'rejected' ? [6 / stageTransform.scale, 4 / stageTransform.scale] : undefined}
                onClick={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'room', id: room.id })
                }}
                onTap={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'room', id: room.id })
                }}
              />
            ))}
          </Layer>

          {/* Walls Layer */}
          <Layer>
            {layers.walls && draft.walls.map((wall) => {
              const isSelected = selected?.kind === 'wall' && selected?.id === wall.id
              const isRejected = wall.disposition === 'rejected'
              const thickness = wall.estimated_thickness_pixels || wall.thickness_pixels || 12
              const length = Math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
              const mid = wallMidpoint(wall.start, wall.end)
              const rot = wallTextRotation(wall.start, wall.end)
              const dimText = formatWallDimension(length, scaleMeters)

              return (
                <Group
                  key={wall.id}
                  draggable={tool === 'move' && !isSpaceHeld}
                  onDragEnd={(e) => {
                    e.cancelBubble = true
                    const dx = e.target.x()
                    const dy = e.target.y()
                    e.target.position({ x: 0, y: 0 })
                    if (onUpdateWall) {
                      onUpdateWall({
                        ...wall,
                        start: {
                          x: Math.max(0, Math.min(width, Math.round(wall.start.x + dx))),
                          y: Math.max(0, Math.min(height, Math.round(wall.start.y + dy))),
                        },
                        end: {
                          x: Math.max(0, Math.min(width, Math.round(wall.end.x + dx))),
                          y: Math.max(0, Math.min(height, Math.round(wall.end.y + dy))),
                        },
                      })
                    }
                  }}
                  onClick={(e) => {
                    e.cancelBubble = true
                    if (tool === 'delete') {
                      onDeleteWall?.(wall.id)
                    } else {
                      onSelect?.({ kind: 'wall', id: wall.id })
                    }
                  }}
                  onTap={(e) => {
                    e.cancelBubble = true
                    if (tool === 'delete') {
                      onDeleteWall?.(wall.id)
                    } else {
                      onSelect?.({ kind: 'wall', id: wall.id })
                    }
                  }}
                >
                  {/* Outer Wall Body with estimated thickness */}
                  <Line
                    points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
                    stroke={isSelected ? '#3b82f6' : isRejected ? '#ef4444' : '#334155'}
                    strokeWidth={thickness}
                    lineCap="butt"
                    lineJoin="miter"
                    opacity={isRejected ? 0.35 : 0.85}
                  />

                  {/* Wall Outline/Borders for crisp CAD look */}
                  <Line
                    points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
                    stroke={isSelected ? '#1d4ed8' : isRejected ? '#b91c1c' : '#1e293b'}
                    strokeWidth={thickness}
                    lineCap="square"
                    lineJoin="miter"
                    opacity={isRejected ? 0.4 : 0.95}
                  />

                  {/* Inner Centerline */}
                  <Line
                    points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
                    stroke={isSelected ? '#ffffff' : '#94a3b8'}
                    strokeWidth={1.5 / stageTransform.scale}
                    dash={isRejected ? [4 / stageTransform.scale, 4 / stageTransform.scale] : [6 / stageTransform.scale, 4 / stageTransform.scale]}
                  />

                  {/* Dimension Text along Wall */}
                  {!isRejected && length > 25 && (
                    <Text
                      x={mid.x}
                      y={mid.y}
                      text={dimText}
                      fontSize={Math.max(10, Math.min(13, 11 / stageTransform.scale))}
                      fontStyle="bold"
                      fontFamily="system-ui, sans-serif"
                      fill={isSelected ? '#1d4ed8' : '#0f172a'}
                      rotation={rot}
                      offsetX={dimText.length * 3}
                      offsetY={thickness / 2 + (12 / stageTransform.scale)}
                      align="center"
                      shadowColor="#ffffff"
                      shadowBlur={3}
                      shadowOpacity={0.9}
                    />
                  )}
                </Group>
              )
            })}
          </Layer>

          {/* Wall Endpoint Handles Layer (when a wall is selected in Move mode) */}
          <Layer>
            {layers.walls && selected?.kind === 'wall' && tool === 'move' && draft.walls
              .filter((wall) => wall.id === selected.id && wall.disposition !== 'rejected')
              .map((wall) => (
                <Group key={`handles-${wall.id}`}>
                  {/* Start Point Handle */}
                  <Circle
                    x={wall.start.x}
                    y={wall.start.y}
                    radius={7 / stageTransform.scale}
                    fill="#2563eb"
                    stroke="#ffffff"
                    strokeWidth={2 / stageTransform.scale}
                    draggable
                    onDragMove={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point) return
                      const snapped = findSnapPoint(point, draft.walls, {
                        threshold: snapThreshold,
                        excludeWallId: wall.id,
                      })
                      const next = snapped.snapped ? snapped : point
                      e.target.position(next)
                    }}
                    onDragEnd={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point || !onUpdateWall) return
                      const snapped = findSnapPoint(point, draft.walls, {
                        threshold: snapThreshold,
                        excludeWallId: wall.id,
                      })
                      let next = snapped.snapped ? snapped : point
                      if (isShiftHeld) {
                        next = constrainPoint(wall.end, next, true)
                      }
                      e.target.position(next)
                      onUpdateWall({ ...wall, start: next })
                    }}
                  />

                  {/* End Point Handle */}
                  <Circle
                    x={wall.end.x}
                    y={wall.end.y}
                    radius={7 / stageTransform.scale}
                    fill="#2563eb"
                    stroke="#ffffff"
                    strokeWidth={2 / stageTransform.scale}
                    draggable
                    onDragMove={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point) return
                      const snapped = findSnapPoint(point, draft.walls, {
                        threshold: snapThreshold,
                        excludeWallId: wall.id,
                      })
                      const next = snapped.snapped ? snapped : point
                      e.target.position(next)
                    }}
                    onDragEnd={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point || !onUpdateWall) return
                      const snapped = findSnapPoint(point, draft.walls, {
                        threshold: snapThreshold,
                        excludeWallId: wall.id,
                      })
                      let next = snapped.snapped ? snapped : point
                      if (isShiftHeld) {
                        next = constrainPoint(wall.start, next, true)
                      }
                      e.target.position(next)
                      onUpdateWall({ ...wall, end: next })
                    }}
                  />
                </Group>
              ))}
          </Layer>

          {/* Drawing Wall Live Preview Layer */}
          <Layer listening={false}>
            {tool === 'draw' && drawingStart && (
              <Group>
                {/* Live Wall Preview */}
                <Line
                  points={[drawingStart.x, drawingStart.y, effectivePoint.x, effectivePoint.y]}
                  stroke="#0284c7"
                  strokeWidth={12}
                  lineCap="square"
                  opacity={0.6}
                  dash={[6 / stageTransform.scale, 4 / stageTransform.scale]}
                />
                <Line
                  points={[drawingStart.x, drawingStart.y, effectivePoint.x, effectivePoint.y]}
                  stroke="#0369a1"
                  strokeWidth={1.5 / stageTransform.scale}
                />
                {/* Start Point Dot */}
                <Circle
                  x={drawingStart.x}
                  y={drawingStart.y}
                  radius={6 / stageTransform.scale}
                  fill="#0284c7"
                  stroke="#ffffff"
                  strokeWidth={2 / stageTransform.scale}
                />
                {/* Dimension label on live wall */}
                {Math.hypot(effectivePoint.x - drawingStart.x, effectivePoint.y - drawingStart.y) > 15 && (
                  <Text
                    x={(drawingStart.x + effectivePoint.x) / 2}
                    y={(drawingStart.y + effectivePoint.y) / 2}
                    text={formatWallDimension(
                      Math.hypot(effectivePoint.x - drawingStart.x, effectivePoint.y - drawingStart.y),
                      scaleMeters,
                    )}
                    fontSize={11 / stageTransform.scale}
                    fontStyle="bold"
                    fill="#0284c7"
                    rotation={wallTextRotation(drawingStart, effectivePoint)}
                    offsetY={16 / stageTransform.scale}
                    shadowColor="#ffffff"
                    shadowBlur={4}
                  />
                )}
              </Group>
            )}

            {/* Snapping Indicator Circle */}
            {(tool === 'draw' || tool === 'move') && snap.snapped && (
              <Circle
                x={snap.x}
                y={snap.y}
                radius={8 / stageTransform.scale}
                stroke="#0284c7"
                strokeWidth={2.5 / stageTransform.scale}
                fill="rgba(2, 132, 199, 0.2)"
              />
            )}
          </Layer>

          {/* Symbols Layer */}
          <Layer>
            {layers.symbols && draft.symbols.map((symbol) => (
              <Circle
                key={symbol.id}
                x={symbol.center.x}
                y={symbol.center.y}
                radius={10 / stageTransform.scale}
                fill={symbol.disposition === 'accepted' ? 'rgba(225,76,31,0.28)' : 'rgba(139,47,47,0.12)'}
                stroke={selected?.kind === 'symbol' && selected?.id === symbol.id ? '#2563eb' : '#e14c1f'}
                strokeWidth={selected?.kind === 'symbol' && selected?.id === symbol.id ? 4 / stageTransform.scale : 2 / stageTransform.scale}
                onClick={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'symbol', id: symbol.id })
                }}
                onTap={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'symbol', id: symbol.id })
                }}
              />
            ))}
          </Layer>

          {/* Room Handles (when room selected) */}
          <Layer>
            {layers.rooms && selected?.kind === 'room' && onUpdateRoom && draft.rooms
              .filter((room) => room.id === selected.id)
              .flatMap((room) => room.boundary.map((point, index) => (
                <Circle
                  key={`${room.id}-handle-${index}`}
                  x={point.x}
                  y={point.y}
                  radius={7 / stageTransform.scale}
                  fill="#ffffff"
                  stroke="#7c3aed"
                  strokeWidth={2 / stageTransform.scale}
                  draggable
                  onDragEnd={(event) => {
                    const next = {
                      x: Math.max(0, Math.min(width, Math.round(event.target.x()))),
                      y: Math.max(0, Math.min(height, Math.round(event.target.y()))),
                    }
                    event.target.position(next)
                    onUpdateRoom({
                      ...room,
                      boundary: room.boundary.map((item, i) => i === index ? next : item),
                    })
                  }}
                />
              )))}
          </Layer>
        </Stage>

        {/* Floating pill for drawing mode: "Press the 'Esc' key to stop drawing walls" */}
        {tool === 'draw' && (
          <div className="demo-esc-pill" role="status">
            Press the &quot;Esc&quot; key to stop drawing walls
          </div>
        )}

        {/* Floating Help icon button */}
        <button
          type="button"
          className="demo-help-button"
          title="Wall editor shortcuts: Click to start/finish drawing, Esc cancels, Del deletes, Shift locks 90°"
          aria-label="Editor help"
        >
          ?
        </button>
      </div>
      <p className="detection-canvas-note">
        Walls are rendered as centerlines with estimated thickness. Select a wall to drag its endpoints or body. Hold Shift for 90° constraint.
      </p>
    </section>
  )
}
