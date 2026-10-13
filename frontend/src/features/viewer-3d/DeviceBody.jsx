import { useMemo } from 'react'
import { Shape } from 'three'

const porcelain = '#faf8f2', graphite = '#26343c', metal = '#a5b0b4'

function Box({ size, position = [0, 0, 0], color = porcelain, name, lens = false, selected = false }) {
  return <mesh name={name} position={position}><boxGeometry args={size} />
    <meshStandardMaterial color={color} roughness={lens ? .28 : .42} metalness={color === metal ? .5 : .05}
      emissive={selected ? '#ffb94f' : lens ? '#fff1d5' : '#000000'} emissiveIntensity={selected ? .85 : lens ? .12 : 0} /></mesh>
}

function RoundedPlate({ width = 1, height = 1, depth = .7, position = [0, 0, 0], color = porcelain, name, selected = false }) {
  const shape = useMemo(() => {
    const s = new Shape(), x = -width / 2, y = -height / 2, r = Math.min(width, height) * .12
    s.moveTo(x + r, y); s.lineTo(x + width - r, y); s.quadraticCurveTo(x + width, y, x + width, y + r)
    s.lineTo(x + width, y + height - r); s.quadraticCurveTo(x + width, y + height, x + width - r, y + height)
    s.lineTo(x + r, y + height); s.quadraticCurveTo(x, y + height, x, y + height - r)
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y)
    return s
  }, [width, height])
  return <mesh name={name} position={[position[0], position[1], position[2] - depth / 2]}>
    <extrudeGeometry args={[shape, { depth, bevelEnabled: false, curveSegments: 5 }]} />
    <meshStandardMaterial color={color} roughness={.36} metalness={.04}
      emissive={selected ? '#ffb94f' : '#000000'} emissiveIntensity={selected ? .85 : 0} />
  </mesh>
}

function Disc({ radius, height, position = [0, 0, 0], color = porcelain, front = false, name, lens = false, selected = false }) {
  return <mesh name={name} position={position} rotation={front ? [Math.PI / 2, 0, 0] : [0, 0, 0]}>
    <cylinderGeometry args={[radius, radius, height, 20]} />
    <meshStandardMaterial color={color} roughness={.36} metalness={color === metal ? .5 : .02}
      emissive={selected ? '#ffb94f' : lens ? '#fff1d5' : '#000000'} emissiveIntensity={selected ? .85 : lens ? .12 : 0} />
  </mesh>
}

// Generic illustrative fittings, not branded products or engineering specifications.
// Local +Z faces the room for wall devices; local -Y faces down for luminaires.
export function DeviceBody({ family, label = '', selected = false }) {
  if (family === 'outlet') {
    const data = /data|connection port|rj.?45|telephone/i.test(label)
    return <group name="horizontal-outlet-body">
      <RoundedPlate name="outlet-backbox" width={.92} height={.84} depth={.55} position={[0, 0, -.2]} color={graphite} selected={selected} />
      <RoundedPlate name="horizontal-outlet-plate" depth={.38} position={[0, 0, .31]} selected={selected} />
      {[-.23, .23].map(x => <group key={x} name={data ? 'data-socket' : 'grounded-socket'} position={[x, 0, .51]}>
        <RoundedPlate width={.38} height={.66} depth={.05} color="#e8e8e2" />
        {data ? <Box name="keystone-opening" size={[.22, .25, .018]} position={[0, 0, .033]} color={graphite} /> : <>
          {[-.08, .08].map(slot => <Box key={slot} name="socket-contact" size={[.038, .18, .018]} position={[slot, .08, .033]} color={graphite} />)}
          <Disc name="ground-contact" radius={.038} height={.02} position={[0, -.16, .034]} color={graphite} front />
        </>}
      </group>)}
      {[-.43, .43].map(x => <group key={x} position={[x, 0, .51]}>
        <Disc radius={.025} height={.012} color={metal} front />
        <Box size={[.03, .008, .015]} position={[0, 0, .01]} color={graphite} />
      </group>)}
    </group>
  }
  if (family === 'switch' || family === 'pull-station') return <group name="wall-control-body">
    <RoundedPlate color={family === 'pull-station' ? '#b64a35' : porcelain} selected={selected} />
    <RoundedPlate name="rocker-reveal" width={.6} height={.76} depth={.06} position={[0, 0, .37]} color={graphite} />
    <RoundedPlate name="switch-paddle" width={.54} height={.7} depth={.13} position={[0, 0, .45]} selected={selected} />
    <Box name="paddle-divider" size={[.48, .012, .01]} position={[0, 0, .52]} color="#bdc3c2" />
  </group>
  if (family === 'linear-light') {
    const count = /\b1\s*[x×]\s*40\b|single/i.test(label) ? 1 : 2
    return <group name={`linear-fixture-${count}-tube`}>
      <Box name="luminaire-spine" size={[.94, .65, 1]} position={[0, .15, 0]} color={metal} selected={selected} />
      {(count === 1 ? [0] : [-.24, .24]).map(x => <group key={x} position={[x, -.25, 0]}>
        <mesh name="fluorescent-tube" rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[count === 1 ? .18 : .13, count === 1 ? .18 : .13, .94, 12]} />
          <meshStandardMaterial color="#fff8e9" roughness={.24} emissive={selected ? '#ffb94f' : '#fff1d5'} emissiveIntensity={selected ? .85 : .12} />
        </mesh>
        {[-.48, .48].map(z => <Box key={z} name="lamp-holder" size={[.38, .55, .035]} position={[0, 0, z]} />)}
      </group>)}
    </group>
  }
  if (family === 'troffer') return <group name="recessed-troffer">
    <Box name="fixture-housing" size={[.98, .8, .98]} position={[0, .1, 0]} color={metal} selected={selected} />
    <Box name="ceiling-trim" size={[1, .12, 1]} position={[0, -.38, 0]} selected={selected} />
    <Box name="diffuser" size={[.91, .06, .94]} position={[0, -.46, 0]} color="#fff8e9" lens selected={selected} />
    {[-.3, 0, .3].map(z => <Box key={z} size={[.92, .025, .012]} position={[0, -.5, z]} color="#c8cfcd" />)}
  </group>
  if (family === 'panel') return <group name="panel-enclosure">
    <Box name="panel-housing" size={[1, 1, 1]} color={graphite} selected={selected} />
    <RoundedPlate name="panel-door" width={.92} height={.94} depth={.045} position={[0, 0, .51]} color={metal} selected={selected} />
    <Box name="panel-latch" size={[.035, .15, .045]} position={[.32, 0, .55]} color={graphite} />
    <Box name="directory-window" size={[.35, .12, .012]} position={[0, .3, .54]} color="#dde2e1" />
  </group>
  if (['round-light', 'detector', 'alarm'].includes(family)) return <group rotation={family === 'alarm' ? [Math.PI / 2, 0, 0] : [0, 0, 0]}>
    <Disc radius={.5} height={.6} color={family === 'alarm' ? '#b64a35' : porcelain} selected={selected} />
    <Disc radius={.44} height={.08} position={[0, -.34, 0]} color={family === 'detector' ? '#d2d7d5' : graphite} />
    <Disc radius={.36} height={.055} position={[0, -.4, 0]} color="#fff8e9" lens={family === 'round-light'} selected={selected} />
  </group>
  return family === 'annotation' ? <mesh rotation={[-Math.PI / 2, 0, 0]}><coneGeometry args={[.5, 1, 3]} /><meshStandardMaterial color="#c94e28" /></mesh>
    : <mesh><octahedronGeometry args={[.5]} /><meshStandardMaterial color="#c94e28" wireframe
      emissive={selected ? '#ffb94f' : '#000000'} emissiveIntensity={selected ? .85 : 0} /></mesh>
}
