import { Circle, Group, Line, Rect } from 'react-konva'

// Schematic review glyphs; the original blueprint remains visible beneath them.
export function DeviceGlyph({ family, color, scale }) {
  const s = 1 / scale
  const stroke = { stroke: color, strokeWidth: 1.5, listening: false }
  return <Group scaleX={s} scaleY={s} listening={false}>
    {['troffer', 'linear-light'].includes(family) ? <>
      <Rect x={-7} y={-12} width={14} height={24} fill="#fdfcf8d9" {...stroke} />
      <Line points={[-3, -10, -3, 10]} {...stroke} /><Line points={[3, -10, 3, 10]} {...stroke} />
    </> : ['switch', 'outlet', 'panel', 'pull-station'].includes(family) ? <>
      <Rect x={-10} y={-10} width={20} height={20} fill="#fdfcf8d9" {...stroke} />
      {family === 'outlet' ? <><Line points={[-3, -4, -3, 3]} {...stroke} /><Line points={[3, -4, 3, 3]} {...stroke} /></>
        : <Line points={family === 'switch' ? [-4, 5, 4, -5] : [-5, -4, 5, -4, 5, 4, -5, 4, -5, -4]} {...stroke} />}
    </> : family === 'annotation' ? <Line points={[-10, 6, 10, -6, 2, -6, 10, -6, 7, 2]} {...stroke} />
      : family === 'unknown' ? <Line points={[0, -10, 10, 0, 0, 10, -10, 0, 0, -10]} fill="#fdfcf8d9" {...stroke} />
        : <><Circle radius={10} fill="#fdfcf8d9" {...stroke} /><Line points={[-5, -5, 5, 5, 0, 0, -5, 5, 5, -5]} {...stroke} /></>}
  </Group>
}
