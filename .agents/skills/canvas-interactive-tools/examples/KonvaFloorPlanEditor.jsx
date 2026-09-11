import React, { useState, useRef, useCallback } from 'react';
import { Stage, Layer, Image as KonvaImage, Line, Circle, Rect, Group, Transformer } from 'react-konva';

/**
 * KonvaFloorPlanEditor demonstrates the 7-layer architecture, pan/zoom mechanics,
 * wall snapping, and transformer selection for 2D floor plans.
 */
export function KonvaFloorPlanEditor({
  blueprintImage,
  canonicalGeometry,
  activeTool = 'select',
  selectedId = null,
  onSelectObject,
  onUpdateSymbolPosition,
  pixelsPerMeter = 100,
}) {
  const [stageScale, setStageScale] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const [snapIndicator, setSnapIndicator] = useState(null);
  const stageRef = useRef(null);
  const transformerRef = useRef(null);

  // Smooth mouse-centered zooming
  const handleWheel = useCallback((e) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    if (!stage) return;

    const scaleBy = 1.1;
    const oldScale = stage.scaleX();
    const pointer = stage.getPointerPosition();

    const mousePointTo = {
      x: (pointer.x - stage.x()) / oldScale,
      y: (pointer.y - stage.y()) / oldScale,
    };

    const newScale = e.evt.deltaY < 0 ? oldScale * scaleBy : oldScale / scaleBy;
    const clampedScale = Math.max(0.1, Math.min(newScale, 10));

    setStageScale(clampedScale);
    setStagePos({
      x: pointer.x - mousePointTo.x * clampedScale,
      y: pointer.y - mousePointTo.y * clampedScale,
    });
  }, []);

  // Symbol drag handling with magnetic snapping to nearby walls
  const handleSymbolDragMove = useCallback((symbolId, e) => {
    const stage = stageRef.current;
    if (!stage) return;

    const rawX = e.target.x();
    const rawY = e.target.y();

    // Check proximity to walls
    const walls = canonicalGeometry?.walls || [];
    let bestSnap = null;
    let minDistance = 14; // pixels

    for (const wall of walls) {
      const dx = wall.end.x - wall.start.x;
      const dy = wall.end.y - wall.start.y;
      const lenSq = dx * dx + dy * dy;
      if (lenSq === 0) continue;

      const t = Math.max(0, Math.min(1, ((rawX - wall.start.x) * dx + (rawY - wall.start.y) * dy) / lenSq));
      const projX = wall.start.x + t * dx;
      const projY = wall.start.y + t * dy;
      const dist = Math.hypot(rawX - projX, rawY - projY);

      if (dist < minDistance) {
        minDistance = dist;
        bestSnap = { x: projX, y: projY, wallId: wall.id };
      }
    }

    if (bestSnap) {
      e.target.position({ x: bestSnap.x, y: bestSnap.y });
      setSnapIndicator(bestSnap);
    } else {
      setSnapIndicator(null);
    }
  }, [canonicalGeometry]);

  const handleSymbolDragEnd = useCallback((symbolId, e) => {
    setSnapIndicator(null);
    const finalPos = e.target.position();
    if (onUpdateSymbolPosition) {
      onUpdateSymbolPosition(symbolId, {
        x: Number((finalPos.x / pixelsPerMeter).toFixed(4)),
        y: Number((finalPos.y / pixelsPerMeter).toFixed(4)),
      });
    }
  }, [onUpdateSymbolPosition, pixelsPerMeter]);

  return (
    <Stage
      ref={stageRef}
      width={window.innerWidth - 300}
      height={window.innerHeight - 80}
      scaleX={stageScale}
      scaleY={stageScale}
      x={stagePos.x}
      y={stagePos.y}
      draggable={activeTool === 'select'}
      onWheel={handleWheel}
      style={{ background: '#0b0f19', cursor: activeTool === 'select' ? 'default' : 'crosshair' }}
    >
      {/* Layer 1: Immutable uploaded blueprint raster image */}
      <Layer id="layer-blueprint" listening={false}>
        {blueprintImage && (
          <KonvaImage image={blueprintImage} opacity={0.85} />
        )}
      </Layer>

      {/* Layer 2: Wall line segments */}
      <Layer id="layer-walls">
        {canonicalGeometry?.walls?.map((wall) => (
          <Line
            key={wall.id}
            points={[wall.start.x, wall.start.y, wall.end.x, wall.end.y]}
            stroke="#94a3b8"
            strokeWidth={4}
            lineCap="round"
            lineJoin="round"
            onClick={() => onSelectObject && onSelectObject('wall', wall.id)}
          />
        ))}
      </Layer>

      {/* Layer 3: Room boundaries */}
      <Layer id="layer-rooms" listening={false}>
        {canonicalGeometry?.rooms?.map((room) => (
          <Line
            key={room.id}
            points={room.polygon?.flatMap((p) => [p.x, p.y]) || []}
            closed
            fill="rgba(59, 130, 246, 0.05)"
            stroke="rgba(59, 130, 246, 0.3)"
            strokeWidth={1}
          />
        ))}
      </Layer>

      {/* Layer 4: Electrical Symbols */}
      <Layer id="layer-symbols">
        {canonicalGeometry?.symbols?.map((sym) => {
          const isSelected = selectedId === sym.id;
          return (
            <Group
              key={sym.id}
              x={sym.x * pixelsPerMeter}
              y={sym.y * pixelsPerMeter}
              draggable={activeTool === 'select'}
              onDragMove={(e) => handleSymbolDragMove(sym.id, e)}
              onDragEnd={(e) => handleSymbolDragEnd(sym.id, e)}
              onClick={() => onSelectObject && onSelectObject('symbol', sym.id)}
            >
              {/* Outer selection ring */}
              {isSelected && (
                <Circle
                  radius={16}
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dash={[4, 4]}
                />
              )}
              {/* Device glyph */}
              <Circle
                radius={10}
                fill={sym.status === 'needs_review' ? '#f59e0b' : '#3b82f6'}
                stroke="#ffffff"
                strokeWidth={1.5}
                shadowBlur={isSelected ? 10 : 2}
                shadowColor="#3b82f6"
              />
            </Group>
          );
        })}
      </Layer>

      {/* Layer 5: Wiring Routes */}
      <Layer id="layer-wiring" listening={false}>
        {canonicalGeometry?.routes?.map((route) => (
          <Line
            key={route.id}
            points={route.points?.flatMap((p) => [p.x * pixelsPerMeter, p.y * pixelsPerMeter]) || []}
            stroke="#10b981"
            strokeWidth={2}
            dash={[6, 3]}
            lineJoin="round"
          />
        ))}
      </Layer>

      {/* Layer 6: Conduits */}
      <Layer id="layer-conduits" listening={false}>
        {canonicalGeometry?.conduits?.map((conduit) => (
          <Line
            key={conduit.id}
            points={conduit.points?.flatMap((p) => [p.x * pixelsPerMeter, p.y * pixelsPerMeter]) || []}
            stroke="#06b6d4"
            strokeWidth={3}
            lineCap="square"
          />
        ))}
      </Layer>

      {/* Layer 7: Interactive UI overlays & snapping feedback */}
      <Layer id="layer-interaction" listening={false}>
        {snapIndicator && (
          <Circle
            x={snapIndicator.x}
            y={snapIndicator.y}
            radius={8}
            fill="#10b981"
            opacity={0.8}
          />
        )}
      </Layer>
    </Stage>
  );
}
