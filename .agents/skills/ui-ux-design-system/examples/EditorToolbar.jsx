import React from 'react';

/**
 * Floating glassmorphic HUD toolbar for the 2D/3D electrical layout workspace.
 */
export function EditorToolbar({
  activeTool,
  setActiveTool,
  viewMode,
  setViewMode,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
}) {
  const tools = [
    { id: 'select', label: 'Select (V)', icon: '↖' },
    { id: 'wall', label: 'Draw Wall (W)', icon: '━' },
    { id: 'symbol', label: 'Place Symbol (S)', icon: '⨁' },
    { id: 'route', label: 'Route Conduit (R)', icon: '⤹' },
    { id: 'measure', label: 'Measure (M)', icon: '⤢' },
  ];

  return (
    <div className="ved-toolbar" style={{ position: 'absolute', top: '1rem', left: '1rem', zIndex: 30 }}>
      {/* Tool Selection Group */}
      <div style={{ display: 'flex', gap: '0.25rem' }}>
        {tools.map((t) => (
          <button
            key={t.id}
            type="button"
            title={t.label}
            className={`ved-btn-tool ${activeTool === t.id ? 'active' : ''}`}
            onClick={() => setActiveTool(t.id)}
          >
            <span style={{ fontSize: '1.1rem', marginRight: '0.25rem' }}>{t.icon}</span>
            <span style={{ fontSize: '0.85rem' }}>{t.id.toUpperCase()}</span>
          </button>
        ))}
      </div>

      <div style={{ width: '1px', height: '1.5rem', background: 'var(--ved-border-color)' }} />

      {/* 2D / 3D / Split View Toggle */}
      <div style={{ display: 'flex', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '2px' }}>
        {['2D', '3D', 'Split'].map((mode) => (
          <button
            key={mode}
            type="button"
            className={`ved-btn-tool ${viewMode === mode.toLowerCase() ? 'active' : ''}`}
            style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
            onClick={() => setViewMode(mode.toLowerCase())}
          >
            {mode}
          </button>
        ))}
      </div>

      <div style={{ width: '1px', height: '1.5rem', background: 'var(--ved-border-color)' }} />

      {/* Undo / Redo */}
      <div style={{ display: 'flex', gap: '0.25rem' }}>
        <button
          type="button"
          title="Undo (Ctrl+Z)"
          className="ved-btn-tool"
          disabled={!canUndo}
          onClick={onUndo}
        >
          ↶
        </button>
        <button
          type="button"
          title="Redo (Ctrl+Shift+Z)"
          className="ved-btn-tool"
          disabled={!canRedo}
          onClick={onRedo}
        >
          ↷
        </button>
      </div>
    </div>
  );
}
