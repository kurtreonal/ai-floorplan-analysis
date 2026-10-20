import { useEffect, useMemo, useRef, useState } from 'react'
import { useUserPreferences } from '../settings/useUserPreferences.js'
import { Circle, Group, Image as KonvaImage, Layer, Line, Rect, Stage, Text } from 'react-konva'

import { fitCanvas } from './detectionCanvasGeometry.js'
import { DeviceGlyph } from './DeviceGlyph.jsx'
import { wiringAppearance } from './wiringAppearance.js'
import { snapWiringPoint } from './wireDrawing.js'
import { findDeviceWireSnap } from './deviceConnections.js'
import { findWireEndpointSnap, findWireEndpointTargets } from './wirePathSnap.js'
import { WiringTargetChooser } from './WiringTargetChooser.jsx'
import { wiringTargetLabel } from './wiringTargetLabel.js'
import { appendDrawingVertex } from './connectedWiring.js'
import { connectedWireIds } from './wireJunctions.js'
import { clampDevicePoint } from './devicePresentation.js'
import { drawingRegionFromPoints } from './drawingRegion.js'
import {buildWallTopology} from '../../geometry/wallTopology.js'
import { wallPointerTarget } from './wallDrawing.js'
import { WALL_APPEARANCE as wallStyle } from './wallAppearance.js'
import { wallMeasurements, formatWallMeasure } from './wallMeasurements.js'
import {
  constrainPoint,
  findSnapPoint,
  wallMidpoint,
} from './wallEditorUtils.js'

function roomPoints(boundary) {
  return boundary.flatMap((point) => [point.x, point.y])
}

export function DemoInterpretationCanvas({
  active = true,
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
  onAddWire,
  onDrawingPendingChange,
  drawingWireMethod = 'concealed_in_ceiling',
  onMoveWirePoint,
  editingSession = 0,
  onUpdateWall,
  onDeleteWall,
  onUpdateRoom,
  onUpdateSymbol,
  onPlaceDevice,
  placementPresentation = null,
  onDeleteSymbol,
  presentations = {},
  scaleMeters = null,
  wallUnit = 'm',
  blueprintOpacity = 1.0,
  analysisRegion = null,
  onAnalysisRegionChange,
  regionSession = 0,
}) {
  const containerRef = useRef(null)
  const { preferences } = useUserPreferences()
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
  const wallFootprints=useMemo(()=>new Map(buildWallTopology(draft.walls.map(w=>({...w,
    thickness:scaleMeters>0&&w.thickness_meters ? w.thickness_meters*scaleMeters : w.estimated_thickness_pixels||w.thickness_pixels||12}))).walls.map(w=>[w.id,w])),[draft.walls,scaleMeters])
  const [drawingAnchor, setDrawingAnchor] = useState(null)
  const [wireSession,setWireSession] = useState(null)
  function setWireDrawingSession(next) {
    setWireSession(next)
    onDrawingPendingChange?.(Boolean(next?.vertices?.length))
  }
  const wireVertices = useMemo(()=>wireSession?.session === editingSession ? wireSession.vertices : [],[wireSession,editingSession])
  const selectedNetwork = useMemo(()=>selected?.kind==='wiring' ? connectedWireIds(draft,selected.id) : new Set(),[draft,selected])
  const [hoveredWall, setHoveredWall] = useState(null)
  const wallLabels=useMemo(()=>wallMeasurements(draft.walls,w=>scaleMeters>0&&w.thickness_meters ? w.thickness_meters*scaleMeters : w.estimated_thickness_pixels??12),[draft.walls,scaleMeters])
  const drawingStart = tool==='wire' ? wireVertices.at(-1)?.point : drawingAnchor?.tool === tool && drawingAnchor.session === editingSession ? drawingAnchor.point : null
  const [regionStart, setRegionStart] = useState(null)
  const regionAnchor = regionStart?.session === regionSession ? regionStart.point : null
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [isShiftHeld, setIsShiftHeld] = useState(false)
  const [isSpaceHeld, setIsSpaceHeld] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [placementPointer, setPlacementPointer] = useState(null)
  const [deviceSnap, setDeviceSnap] = useState(null)
  const [wireDeviceSnap, setWireDeviceSnap] = useState(null)
  const [pendingWireTarget, setPendingWireTarget] = useState(null)
  const activeWireTarget = pendingWireTarget?.draft === draft && pendingWireTarget.session === editingSession
    && pendingWireTarget.tool === tool && pendingWireTarget.selectionId === selected?.id ? pendingWireTarget : null
  const wireSnapPreview = activeWireTarget?.highlighted || wireDeviceSnap
  const wireDrag = useRef(null)
  const drawingGesture=useRef(null)

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
    if (!active) return
    function handleKeyDown(event) {
      if (event.key === 'Escape' && activeWireTarget) {
        event.preventDefault()
        setPendingWireTarget(null)
        return
      }
      if (tool==='wire' && ['Enter','Escape','Backspace'].includes(event.key)) {
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName) || event.target?.isContentEditable) return
        event.preventDefault()
        if (event.key==='Backspace') {setWireSession({session:editingSession,vertices:wireVertices.slice(0,-1)});onDrawingPendingChange?.(wireVertices.length>1)}
        else {
          if (wireVertices.length>=2 && onAddWire?.(wireVertices.map(v=>v.point),wireVertices)===false) return
          setWireSession(null)
          onDrawingPendingChange?.(false)
          if(event.key==='Escape')onToolChange?.('select')
        }
        return
      }
      if(event.key==='Escape'&&tool==='draw') {
        setDrawingAnchor(null);onToolChange?.('move');return
      }
      if (event.key === 'Escape' && tool === 'place-device') {
        setPlacementPointer(null)
        onToolChange?.('select')
        return
      }
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target?.tagName)) return
      if (event.key === 'Shift') setIsShiftHeld(true)
      if (event.code === 'Space') { event.preventDefault(); setIsSpaceHeld(true) }
      if (event.key === 'Escape') {
        if (wireDrag.current) {
          const drag = wireDrag.current
          drag.cancelled = true
          drag.target.stopDrag?.()
          drag.target.position(drag.point)
          setWireDeviceSnap(null)
          return
        }
        if (regionAnchor) {
          setRegionStart(null)
        } else if (drawingStart) {
          setDrawingAnchor(null)
          if (tool === 'draw') onToolChange?.('move')
        } else if (tool !== 'move') {
          setPlacementPointer(null)
          setDeviceSnap(null)
          onToolChange?.('move')
        }
      } else if (event.key === 'Delete' || event.key === 'Backspace') {
        if (tool === 'region') return
        if (selected?.kind === 'wall' && onDeleteWall) {
          event.preventDefault()
          onDeleteWall(selected.id)
        } else if (selected?.kind === 'symbol' && onDeleteSymbol) {
          event.preventDefault()
          onDeleteSymbol(selected.id)
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
  }, [active,drawingStart, regionAnchor, tool, selected, onDeleteWall, onDeleteSymbol, onToolChange, wireVertices, editingSession,onAddWire,onDrawingPendingChange,activeWireTarget])

  // Map pointer to source-image pixels via stage inverse transform
  function getSourcePoint(stage) {
    if (!stage) return null
    const pointer = stage.getPointerPosition()
    if (!pointer) return null
    const transform = stage.getAbsoluteTransform().copy().invert()
    const p = transform.point(pointer)
    if (['place-device','draw','wire'].includes(tool) && (p.x < 0 || p.y < 0 || p.x > width || p.y > height)) return null
    return {
      x: Math.max(0, Math.min(width, p.x)),
      y: Math.max(0, Math.min(height, p.y)),
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
    if (!preferences.snapping) return { x: mousePos.x, y: mousePos.y, snapped: false }
    if (tool === 'wire') return snapWiringPoint(isShiftHeld && drawingStart
      ? constrainPoint(drawingStart,mousePos,true) : mousePos,draft,presentations,snapThreshold)
    if (tool !== 'draw' && tool !== 'move') return { x: 0, y: 0, snapped: false }
    if(tool==='move')return findSnapPoint(mousePos,draft.walls,{threshold:10/stageTransform.scale,
      excludeWallId:selected?.kind==='wall'?selected.id:null})
    const target=wallPointerTarget(mousePos,draft.walls,{scale:stageTransform.scale,anchor:drawingStart,
      excludeWallId:tool==='move'&&selected?.kind==='wall'?selected.id:null,shift:isShiftHeld})
    return {...target.point,snapped:target.snapped,guides:target.guides}
  }, [mousePos, draft, presentations, snapThreshold, tool, selected, isShiftHeld, drawingStart,stageTransform.scale,preferences.snapping])

  // Current effective point (with snap and shift constraint)
  const effectivePoint = useMemo(() => {
    if (snap.snapped) return { x: snap.x, y: snap.y }
    if (isShiftHeld && drawingStart) {
      return constrainPoint(drawingStart, mousePos, true)
    }
    return mousePos
  }, [snap, isShiftHeld, drawingStart, mousePos])

  // Mouse move on stage
  function handleMouseMove(event) {
    const stage = event?.target?.getStage?.() ?? stageRef.current
    const pointer=stage?.getPointerPosition()
    if(pointer&&drawingGesture.current?.down&&Math.hypot(pointer.x-drawingGesture.current.start.x,pointer.y-drawingGesture.current.start.y)>3) drawingGesture.current.moved=true
    const point = getSourcePoint(stage)
    if (point) setMousePos(point)
    if (tool === 'place-device') setPlacementPointer(point)
  }

  // Stage click (for drawing walls or clearing selection)
  function handleStageClick(event) {
    if(event.evt?.button!=null&&event.evt.button!==0)return
    if(['draw','wire'].includes(tool)&&drawingGesture.current?.moved){drawingGesture.current=null;return}
    if (tool === 'place-device') {
      if (isSpaceHeld || !placementPresentation) return
      const point = getSourcePoint(event.target.getStage())
      if (point) { onPlaceDevice?.(point); setPlacementPointer(null) }
      return
    }
    if (tool === 'region') {
      if (isSpaceHeld) return
      const point = getSourcePoint(event.target.getStage())
      if (!point) return
      if (!regionAnchor) setRegionStart({ point, session: regionSession })
      else {
        const region = drawingRegionFromPoints(regionAnchor, point, width, height)
        if (region) onAnalysisRegionChange?.(region)
        setRegionStart(null)
      }
      return
    }
    if (tool === 'draw' || tool === 'wire') {
      if (isSpaceHeld) return
      const clicked = getSourcePoint(event.target.getStage())
      if (!clicked) return
      const target=tool==='draw'&&preferences.snapping?wallPointerTarget(clicked,draft.walls,{scale:stageTransform.scale,anchor:drawingStart,shift:isShiftHeld}):null
      const clickedSnap = !preferences.snapping ? null : target ? {...target.point,snapped:target.snapped} : snapWiringPoint(isShiftHeld && drawingStart ? constrainPoint(drawingStart,clicked,true) : clicked,
        draft,presentations,snapThreshold)
      const endpoint = clickedSnap?.snapped ? { x: clickedSnap.x, y: clickedSnap.y }
        : isShiftHeld && drawingStart ? constrainPoint(drawingStart, clicked, true) : clicked
      if (tool==='wire') {
        setWireDrawingSession({session:editingSession,vertices:appendDrawingVertex(wireVertices,endpoint,clickedSnap)})
        return
      }
      if (!drawingStart) {
        setDrawingAnchor({ tool, session: editingSession, point: endpoint })
      } else {
        const length = Math.hypot(endpoint.x - drawingStart.x, endpoint.y - drawingStart.y)
        if (length >= 5 && tool === 'wire') {
          onAddWire?.([drawingStart, endpoint])
        } else if (length >= 2/stageTransform.scale && onAddWall) {
          const committed=onAddWall({
            start: drawingStart,
            end: endpoint,
            // Reference's 10 cm is a configurable manual-design default, not
            // inferred scale. Uncalibrated pages retain source-pixel thickness.
            estimated_thickness_pixels: scaleMeters>0 ? .1*scaleMeters : 12,
            ...(scaleMeters>0 ? {thickness_meters:.1} : {}),
          })
          if(committed===false)return
          const joined=findSnapPoint(endpoint,draft.walls,{threshold:1e-6}).snapped
          if(joined){setDrawingAnchor(null);onToolChange?.('move');return}
        }
        if (length >= (tool==='draw'?2/stageTransform.scale:5)) setDrawingAnchor(tool === 'draw' ? { tool, session: editingSession, point: endpoint } : null)
      }
      return
    }

    if (event.target === stageRef.current || event.target.name() === 'blueprint-image') {
      onSelect?.(null)
    }
  }

  // Cursor style based on active tool and mode
  const cursorStyle = useMemo(() => {
    if (isSpaceHeld || tool === 'pan') return 'grab'
    if (tool === 'draw' || tool === 'wire' || tool === 'region') return 'crosshair'
    if (tool === 'delete') return 'pointer'
    return 'default'
  }, [isSpaceHeld, tool])

  return (
    <section className="demo-canvas-card" aria-label="Unified room wall and symbol review canvas">
      {tool==='wire' && wireVertices.length>0 && <button type="button" className="btn-canvas-mini" style={{position:'absolute',top:64,left:80,zIndex:20}}
        onClick={()=>{if(wireVertices.length>=2 && onAddWire?.(wireVertices.map(v=>v.point),wireVertices)===false)return;setWireDrawingSession(null)}}>Done</button>}
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
          draggable={isSpaceHeld || tool === 'pan'}
          onWheel={handleWheel}
          onMouseMove={handleMouseMove}
          onMouseDown={event=>{const p=event.target.getStage().getPointerPosition();drawingGesture.current=p?{start:p,down:true,moved:false}:null}}
          onMouseUp={()=>{if(drawingGesture.current)drawingGesture.current.down=false}}
          onTouchMove={handleMouseMove}
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
            {layers.walls && draft.walls.filter(wall => wall.disposition !== 'rejected').map((wall) => {
              const isSelected = selected?.kind === 'wall' && selected?.id === wall.id
              const isRejected = wall.disposition === 'rejected'
              const length = Math.hypot(wall.end.x - wall.start.x, wall.end.y - wall.start.y)
              const label=wallLabels.get(wall.id)
              const mid = label?.center || wallMidpoint(wall.start, wall.end)
              const dimText = `${formatWallMeasure(label?.length??length,scaleMeters,wallUnit)}${label?.basis==='interior'?'':' · centerline'}`
              const highlighted=isSelected||hoveredWall===wall.id

              return (
                <Group
                  key={wall.id}
                  draggable={tool === 'move' && !isSpaceHeld}
                  onMouseEnter={()=>setHoveredWall(wall.id)}
                  onMouseLeave={()=>setHoveredWall(null)}
                  onDragEnd={(e) => {
                    e.cancelBubble = true
                    let dx = e.target.x()
                    let dy = e.target.y()
                    if(preferences.snapping&&!e.evt?.altKey) {
                      const raw={x:wall.start.x+dx,y:wall.start.y+dy}
                      const target=wallPointerTarget(raw,draft.walls,{scale:stageTransform.scale,excludeWallId:wall.id})
                      if(target.snapped){dx=target.point.x-wall.start.x;dy=target.point.y-wall.start.y}
                    }
                    e.target.position({ x: 0, y: 0 })
                    if (onUpdateWall) {
                      onUpdateWall({
                        ...wall,
                        start: {
                          x: wall.start.x + dx,
                          y: wall.start.y + dy,
                        },
                        end: {
                          x: wall.end.x + dx,
                          y: wall.end.y + dy,
                        },
                      },{detach:Boolean(e.evt?.altKey)})
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
                  {!isRejected && layers.wallFootprints && <>
                    {(wallFootprints.get(wall.id)?.footprints||[]).map((poly,i)=><Line key={`body-${i}`}
                      points={roomPoints(poly)} closed fill={highlighted?wallStyle.active:wallStyle.normal}
                      strokeWidth={0} hitStrokeWidth={12/stageTransform.scale} />)}
                    {(wallFootprints.get(wall.id)?.boundary||[]).map((edge,i)=><Line key={`edge-${i}`}
                      points={roomPoints(edge)} stroke={highlighted?wallStyle.active:wallStyle.edge}
                      strokeWidth={1/stageTransform.scale} listening={false} />)}
                  </>}
                  {!isRejected && !layers.wallFootprints && ['draw','move','delete'].includes(tool) &&
                    (wallFootprints.get(wall.id)?.boundary||[]).map((edge,i)=><Line key={`outline-${i}`}
                      points={roomPoints(edge)} stroke={highlighted?wallStyle.active:wallStyle.edge}
                      strokeWidth={wallStyle.edgeWidth/stageTransform.scale} listening={false} />)}

                  {/* Inner Centerline */}
                  <Line
                    points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
                    name={`wall-centerline-${wall.id}`}
                    stroke={isRejected||highlighted&&tool==='delete' ? wallStyle.delete : highlighted ? wallStyle.active : wallStyle.normal}
                    strokeWidth={(highlighted ? wallStyle.activeWidth : wallStyle.width) / stageTransform.scale}
                    hitStrokeWidth={12 / stageTransform.scale}
                    lineCap="butt"
                    dash={isRejected ? [4 / stageTransform.scale, 4 / stageTransform.scale] : []}
                  />

                  {/* Dimension Text along Wall */}
                  {!isRejected && length > 25 && (layers.dimensions || isSelected || ['draw','move','delete'].includes(tool)) && (
                    <Text
                      x={mid.x}
                      y={mid.y}
                      text={dimText}
                      fontSize={wallStyle.fontSize / stageTransform.scale}
                      fontFamily={wallStyle.fontFamily}
                      fill="#000000"
                      rotation={0}
                      offsetX={dimText.length * 3 / stageTransform.scale}
                      offsetY={6 / stageTransform.scale}
                      align="center"
                      stroke="#ffffff"
                      strokeWidth={4/stageTransform.scale}
                      fillAfterStrokeEnabled
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
            {layers.walls && selected?.kind === 'wall' && draft.walls
              .filter((wall) => wall.id === selected.id && wall.disposition !== 'rejected')
              .map((wall) => (
                <Group key={`handles-${wall.id}`}>
                  {/* Start Point Handle */}
                  <Circle
                    x={wall.start.x}
                    y={wall.start.y}
                    radius={7 / stageTransform.scale}
                    fill={wallStyle.active}
                    stroke="#ffffff"
                    strokeWidth={2 / stageTransform.scale}
                    draggable={tool === 'move'}
                    onDragMove={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point) return
                      const next = wallPointerTarget(point,draft.walls,{scale:stageTransform.scale,anchor:wall.end,excludeWallId:wall.id,shift:isShiftHeld}).point
                      e.target.position(next)
                    }}
                    onDragEnd={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point || !onUpdateWall) return
                      let next = wallPointerTarget(point,draft.walls,{scale:stageTransform.scale,anchor:wall.end,excludeWallId:wall.id,shift:isShiftHeld}).point
                      if (isShiftHeld) {
                        next = constrainPoint(wall.end, next, true)
                      }
                      e.target.position(next)
                      onUpdateWall({ ...wall, start: next },{detach:Boolean(e.evt?.altKey)})
                    }}
                  />

                  {/* End Point Handle */}
                  <Circle
                    x={wall.end.x}
                    y={wall.end.y}
                    radius={7 / stageTransform.scale}
                    fill={wallStyle.active}
                    stroke="#ffffff"
                    strokeWidth={2 / stageTransform.scale}
                    draggable={tool === 'move'}
                    onDragMove={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point) return
                      const next = wallPointerTarget(point,draft.walls,{scale:stageTransform.scale,anchor:wall.start,excludeWallId:wall.id,shift:isShiftHeld}).point
                      e.target.position(next)
                    }}
                    onDragEnd={(e) => {
                      e.cancelBubble = true
                      const stage = stageRef.current
                      const point = getSourcePoint(stage)
                      if (!point || !onUpdateWall) return
                      let next = wallPointerTarget(point,draft.walls,{scale:stageTransform.scale,anchor:wall.start,excludeWallId:wall.id,shift:isShiftHeld}).point
                      if (isShiftHeld) {
                        next = constrainPoint(wall.start, next, true)
                      }
                      e.target.position(next)
                      onUpdateWall({ ...wall, end: next },{detach:Boolean(e.evt?.altKey)})
                    }}
                  />
                </Group>
              ))}
          </Layer>

          {/* Drawing Wall Live Preview Layer */}
          <Layer listening={false}>
            {tool==='draw' && snap.guides?.map((guide,index)=><Line key={`alignment-${index}`}
              points={roomPoints([guide.from,effectivePoint])} stroke={wallStyle.active}
              dash={[4/stageTransform.scale,4/stageTransform.scale]} strokeWidth={1/stageTransform.scale} />)}
            {tool === 'draw' && drawingStart && (
              <Group>
                {/* Live Wall Preview */}
                <Line
                  points={[drawingStart.x, drawingStart.y, effectivePoint.x, effectivePoint.y]}
                  stroke={wallStyle.active}
                  strokeWidth={wallStyle.activeWidth / stageTransform.scale}
                  lineCap="butt"
                />
                <Line
                  points={[drawingStart.x, drawingStart.y, effectivePoint.x, effectivePoint.y]}
                  stroke={wallStyle.active}
                  strokeWidth={wallStyle.activeWidth / stageTransform.scale}
                />
                {/* Start Point Dot */}
                <Circle
                  x={drawingStart.x}
                  y={drawingStart.y}
                  radius={wallStyle.cornerRadius / stageTransform.scale}
                  fill={wallStyle.active}
                  stroke="#ffffff"
                  strokeWidth={2 / stageTransform.scale}
                />
                {/* Dimension label on live wall */}
                {Math.hypot(effectivePoint.x - drawingStart.x, effectivePoint.y - drawingStart.y) > 15 && (
                  <Text
                    x={(drawingStart.x + effectivePoint.x) / 2}
                    y={(drawingStart.y + effectivePoint.y) / 2}
                    text={`${formatWallMeasure(
                      Math.hypot(effectivePoint.x - drawingStart.x, effectivePoint.y - drawingStart.y),
                      scaleMeters,
                      wallUnit,
                    )} · centerline`}
                    fontSize={wallStyle.fontSize / stageTransform.scale}
                    fontFamily={wallStyle.fontFamily}
                    fill="#000000"
                    rotation={0}
                    offsetX={35/stageTransform.scale}
                    offsetY={16 / stageTransform.scale}
                    stroke="#ffffff"
                    strokeWidth={4/stageTransform.scale}
                    fillAfterStrokeEnabled
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
                radius={wallStyle.cornerRadius / stageTransform.scale}
                stroke={wallStyle.active}
                strokeWidth={2.5 / stageTransform.scale}
                fill={wallStyle.active}
              />
            )}
          </Layer>

          {/* Symbols Layer */}
          <Layer>
            {layers.symbols && draft.symbols.filter((symbol) => symbol.disposition !== 'rejected').map((symbol) => (
              <Group
                key={symbol.id}
                name={`device-${symbol.id}`}
                x={symbol.center.x}
                y={symbol.center.y}
                draggable={Boolean(onUpdateSymbol) && tool === 'select' && !isSpaceHeld}
                onDragStart={(event) => { event.cancelBubble = true; onSelect?.({ kind: 'symbol', id: symbol.id }) }}
                onDragMove={(event) => {
                  const point = {x: event.target.x(), y: event.target.y()}
                  setDeviceSnap(preferences.snapping ? findDeviceWireSnap(point, symbol.id, draft.wirings, 12 / stageTransform.scale) : null)
                }}
                onDragEnd={(event) => {
                  event.cancelBubble = true
                  const center = clampDevicePoint({ x: event.target.x(), y: event.target.y() }, width, height)
                  const candidate = center && preferences.snapping ? findDeviceWireSnap(center, symbol.id, draft.wirings, 12 / stageTransform.scale) : null
                  event.target.position(candidate?.point || center || symbol.center)
                  if (center && onUpdateSymbol?.({ ...symbol, center }, candidate) === false) event.target.position(symbol.center)
                  setDeviceSnap(null)
                }}
                onClick={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'symbol', id: symbol.id })
                }}
                onTap={(e) => {
                  e.cancelBubble = true
                  onSelect?.({ kind: 'symbol', id: symbol.id })
                }}
              >
                <Circle radius={17 / stageTransform.scale} fill={selected?.kind === 'symbol' && selected.id === symbol.id ? '#2563eb16' : 'transparent'}
                  stroke={selected?.kind === 'symbol' && selected.id === symbol.id ? '#2563eb' : undefined}
                  strokeWidth={1.5 / stageTransform.scale} />
                <DeviceGlyph family={presentations[symbol.id]?.family || 'unknown'}
                  label={presentations[symbol.id]?.label} color={selected?.kind === 'symbol' && selected.id === symbol.id ? '#2563eb' : '#af5837'} scale={stageTransform.scale} />
                {(layers.names !== false || selected?.id === symbol.id) && <Text x={18 / stageTransform.scale} y={-6 / stageTransform.scale}
                  text={presentations[symbol.id]?.label || 'Unclassified device · proposal'} fontSize={11 / stageTransform.scale}
                  fontFamily="IBM Plex Sans, sans-serif" fill="#0f2030" shadowColor="#fdfcf8" shadowBlur={3} listening={false} />}
              </Group>
            ))}
          </Layer>

          {/* Wiring sits above room fills so its click targets remain reachable. */}
          <Layer listening={['move', 'select'].includes(tool) && !isSpaceHeld}>
            {layers.wirings && (draft.wirings || []).filter((wire) => wire.disposition !== 'rejected').map((wire) => (
              <Group key={wire.id} listening={['move', 'select'].includes(tool) && !isSpaceHeld}>
              <Line points={roomPoints(wire.points)} stroke="#fffdf8" strokeWidth={5 / stageTransform.scale} opacity={.8} listening={false} lineCap="round" lineJoin="round" />
              <Line name={`observed-wiring-${wire.id}`} points={roomPoints(wire.points)}
                stroke={wiringAppearance(wire,selectedNetwork.has(wire.id)).color} strokeWidth={1.8 / stageTransform.scale}
                hitStrokeWidth={12 / stageTransform.scale}
                lineCap="round" lineJoin="round"
                onClick={(event) => { event.cancelBubble = true; onSelect?.({ kind: 'wiring', id: wire.id }) }}
                onTap={(event) => { event.cancelBubble = true; onSelect?.({ kind: 'wiring', id: wire.id }) }}
                dash={wiringAppearance(wire).dash?.map(value => value / stageTransform.scale)} />
              </Group>
            ))}
            {layers.wirings && [...new Map((draft.wirings || []).filter(w=>w.disposition!=='rejected' && !w.suppression_reason)
              .flatMap(w=>(w.junction_attachments || []).map(a=>[a.junction_id,w.points[a.point_index]]))).entries()].map(([id,point])=>
              <Circle key={id} name={`wire-junction-${id}`} x={point.x} y={point.y} radius={3.5/stageTransform.scale}
                fill="#2563eb" stroke="white" strokeWidth={1/stageTransform.scale} listening={false} />)}
            {layers.wirings && (draft.wirings || []).filter(wire => selectedNetwork.has(wire.id)).flatMap(wire => wire.points.map((point,index) => (
              <Circle key={`${wire.id}:${index}`} name={wire.id===selected?.id ? `wiring-point-${index}` : `wiring-point-${wire.id}-${index}`} x={point.x} y={point.y} radius={5 / stageTransform.scale}
                fill="#2563eb" stroke="white" strokeWidth={1 / stageTransform.scale}
                hitStrokeWidth={6 / stageTransform.scale} draggable={Boolean(onMoveWirePoint) && ['select','move'].includes(tool) && !isSpaceHeld}
                onMouseDown={event => { event.cancelBubble = true }}
                onTouchStart={event => { event.cancelBubble = true }}
                onClick={(event) => { event.cancelBubble = true }}
                onDragStart={(event) => { event.cancelBubble = true; setPendingWireTarget(null); wireDrag.current = {target: event.target, point, cancelled: false} }}
                onDragMove={(event) => {
                  if (wireDrag.current?.cancelled) return
                  const next = {x: event.target.x(), y: event.target.y()}
                  const target = preferences.snapping ? findWireEndpointSnap(next, wire.id, index, draft, presentations, snapThreshold) : null
                  setWireDeviceSnap(target)
                  if (target) event.target.position(target.point)
                }}
                onDragEnd={(event) => {
                  const cancelled = wireDrag.current?.cancelled
                  wireDrag.current = null
                  setWireDeviceSnap(null)
                  const next = { x: event.target.x(), y: event.target.y() }
                  const choices = cancelled || !preferences.snapping ? [] : findWireEndpointTargets(next, wire.id, index, draft, presentations, snapThreshold)
                  event.target.position(point)
                  if (cancelled) return
                  if (choices.length > 1) {
                    setPendingWireTarget({draft,session:editingSession,tool,wireId:wire.id,selectionId:selected?.id,index,choices})
                    return
                  }
                  const target = choices[0]
                  if (target) onMoveWirePoint?.(wire.id,index,target.point,target)
                  else onMoveWirePoint?.(wire.id,index,next)
                }} />
            )))}
          </Layer>
          {/* Room Handles (when room selected) */}
          <Layer>
            {layers.rooms && selected?.kind === 'room' && onUpdateRoom && draft.rooms
              .filter((room) => room.id === selected.id && room.disposition !== 'rejected' && tool !== 'pan' && !isSpaceHeld)
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
          {/* Top hit surface prevents ROI selection from changing review items. */}
          <Layer listening={false}>
            {tool==='wire' && wireVertices.length>1 && <Line name="wire-committed-preview" points={roomPoints(wireVertices.map(v=>v.point))}
              stroke="#ff7a45" strokeWidth={2/stageTransform.scale} lineCap="round" lineJoin="round" />}
          </Layer>
          <Layer>
            {wireSnapPreview && <Group listening={false}>
              <Circle name="wire-device-magnet" x={wireSnapPreview.point.x} y={wireSnapPreview.point.y}
                radius={12 / stageTransform.scale} stroke="#13816c" fill="#13816c20" strokeWidth={2 / stageTransform.scale} />
              <Text name="wire-target-label" x={wireSnapPreview.point.x+16/stageTransform.scale} y={wireSnapPreview.point.y-20/stageTransform.scale}
                text={`${activeWireTarget ? 'Choose' : 'Release to connect'} · ${wiringTargetLabel(wireSnapPreview,presentations)}`} fill="#13816c" fontSize={12/stageTransform.scale} />
            </Group>}
            {tool === 'place-device' && <Rect name="device-place-hit" x={0} y={0} width={width} height={height}
              fill="rgba(0,0,0,0.001)" onMouseLeave={() => setPlacementPointer(null)} />}
            {tool === 'place-device' && placementPresentation && placementPointer && <Group name="device-placement-preview"
              x={placementPointer.x} y={placementPointer.y} opacity={.7} listening={false}>
              <DeviceGlyph family={placementPresentation.family} label={placementPresentation.name} color="#13816c" scale={stageTransform.scale} />
            </Group>}
            {tool === 'select' && deviceSnap && <Group listening={false}>
              <Circle name="device-wire-snap-preview" x={deviceSnap.point.x} y={deviceSnap.point.y}
                radius={10 / stageTransform.scale} stroke="#13816c" strokeWidth={2 / stageTransform.scale} />
              <Text x={deviceSnap.point.x+14/stageTransform.scale} y={deviceSnap.point.y-20/stageTransform.scale}
                text="Release to attach to wire endpoint" fill="#13816c" fontSize={12/stageTransform.scale} />
            </Group>}
            {tool === 'draw' && <Rect name="wall-draw-hit" x={0} y={0} width={width} height={height}
              fill="rgba(0,0,0,0.001)" />}
            {tool === 'wire' && <Rect name="wiring-draw-hit" x={0} y={0} width={width} height={height}
              fill="rgba(0,0,0,0.001)" />}
            {tool === 'wire' && drawingStart && <Line name="wiring-draw-preview"
              points={[drawingStart.x, drawingStart.y, effectivePoint.x, effectivePoint.y]}
              listening={false} stroke={wiringAppearance({ installation_method: drawingWireMethod }).color}
              strokeWidth={2 / stageTransform.scale}
              dash={drawingWireMethod === 'concealed_under_floor' ? [8 / stageTransform.scale, 5 / stageTransform.scale] : undefined} />}
            {tool === 'wire' && snap.snapped && <>
              <Circle name="wiring-magnet" x={snap.x} y={snap.y} radius={8 / stageTransform.scale}
                stroke="#13816c" fill="#13816c20" strokeWidth={2 / stageTransform.scale} listening={false} />
              <Text x={snap.x+12/stageTransform.scale} y={snap.y-18/stageTransform.scale}
                text={snap.kind === 'device' ? 'Device snap' : 'Wire snap'} fontSize={11/stageTransform.scale}
                fill="#116c5c" listening={false} />
            </>}
            {tool === 'region' && <Rect name="drawing-region-hit" x={0} y={0} width={width} height={height}
              fill="rgba(0,0,0,0.001)" />}
            {(analysisRegion || (tool === 'region' && regionAnchor)) && (() => {
              const region = tool === 'region' && regionAnchor
                ? drawingRegionFromPoints(regionAnchor, mousePos, width, height) : analysisRegion
              return region && <Rect name="drawing-region-outline" {...region} listening={false}
                stroke="#0284c7" strokeWidth={2 / stageTransform.scale}
                fill="rgba(2,132,199,0.08)" dash={[8 / stageTransform.scale, 5 / stageTransform.scale]} />
            })()}
          </Layer>
        </Stage>

        {activeWireTarget && <WiringTargetChooser choices={activeWireTarget.choices} presentations={presentations}
          onPreview={highlighted => setPendingWireTarget(current => current ? {...current,highlighted} : null)}
          onCancel={() => setPendingWireTarget(null)} onChoose={target => {
            setPendingWireTarget(null)
            onMoveWirePoint?.(activeWireTarget.wireId,activeWireTarget.index,target.point,target)
          }} />}

        {/* Floating pill for drawing mode: "Press the 'Esc' key to stop drawing walls" */}
        {tool === 'draw' && (
          <div className="demo-esc-pill" role="status">
            Press the &quot;Esc&quot; key to stop drawing walls
          </div>
        )}
        {tool === 'region' && <div className="demo-esc-pill" role="status">Click two opposite corners of the drawing. Outside stays unprocessed. Esc cancels.</div>}
        {tool === 'wire' && <div className="demo-esc-pill" role="status">Click to add points · Enter / Done finishes · Backspace removes a point</div>}

        {/* Floating Help icon button */}
        <button
          type="button"
          className="demo-help-button"
          title="Wall editor shortcuts: Click to start/finish drawing, Esc cancels, Del deletes, Shift locks 90°"
          aria-label="Editor help"
          aria-expanded={showHelp}
          onClick={() => setShowHelp((current) => !current)}
        >
          ?
        </button>
        {showHelp && <div className="studio-canvas-help" role="note">Select &amp; drag devices · Space + drag to pan · wheel to zoom · Delete removes the selection · Ctrl+Z undo · Shift locks wall angles · Esc exits drawing.</div>}
      </div>
      <p className="detection-canvas-note">
        Walls use screen-space strokes; physical thickness is unchanged. Closed-room labels measure interior faces; open walls and previews measure centerlines. Enable Wall footprints to inspect thickness. Shared junctions stay attached. Hold Shift for 90° constraint; Alt-drag moves a wall independently. Openings and uncertain gaps remain editable.
      </p>
    </section>
  )
}
