import { Circle, Group, Line, Rect } from 'react-konva'

// Schematic review glyphs; the original blueprint remains visible beneath them.
export function DeviceGlyph({ family, color, scale, label = '' }) {
  const s = 1 / scale
  const stroke = { stroke: color, strokeWidth: 1.5, listening: false }
  return <Group scaleX={s} scaleY={s} listening={false}>
    {['troffer', 'linear-light'].includes(family) ? <>
      <Rect x={-7} y={-12} width={14} height={24} cornerRadius={2} fill="#fffaf0f2" {...stroke} />
      {(family === 'linear-light' && /\b1\s*[x×]\s*40\b|single/i.test(label) ? [0] : [-3,3]).map(x =>
        <Line key={x} points={[x, -9, x, 9]} {...stroke} />)}
    </> : family === 'outlet' ? <>
      <Rect name="horizontal-outlet-plate" x={-13} y={-8} width={26} height={16} cornerRadius={3} fill="#faf8f2f2" {...stroke} />
      {[-6,6].map(x => <Group key={x} x={x} listening={false}>
        <Rect x={-4.5} y={-5.5} width={9} height={11} cornerRadius={2} stroke="#d2d8d6" strokeWidth={.7} />
        <Line points={[-2,-3,-2,1]} {...stroke} /><Line points={[2,-3,2,1]} {...stroke} />
        <Circle y={3.5} radius={1} fill={color} listening={false} />
      </Group>)}
    </> : ['switch', 'panel', 'pull-station'].includes(family) ? <>
      <Rect x={-8} y={-10} width={16} height={20} cornerRadius={2} fill="#fdfcf8f2" {...stroke} />
      <Rect x={-4.5} y={-6} width={9} height={12} cornerRadius={1} {...stroke} />
      {family === 'switch' && <Line points={[-4,0,4,0]} {...stroke} />}
    </> : family === 'annotation' ? <Line points={[-10, 6, 10, -6, 2, -6, 10, -6, 7, 2]} {...stroke} />
      : family === 'unknown' ? <Line points={[0, -10, 10, 0, 0, 10, -10, 0, 0, -10]} fill="#fdfcf8d9" {...stroke} />
        : <><Circle radius={10} fill="#fdfcf8d9" {...stroke} /><Line points={[-5, -5, 5, 5, 0, 0, -5, 5, 5, -5]} {...stroke} /></>}
  </Group>
}
