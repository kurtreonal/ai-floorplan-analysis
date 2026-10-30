// Local manual verification harness. No project data, network API or persistence.
import {createRoot} from 'react-dom/client'
import {useMemo,useRef,useState} from 'react'
import {Viewer3DCanvas} from './Viewer3DCanvas.jsx'
import {PreferencesContext} from '../settings/useUserPreferences.js'
import {DEFAULT_PREFERENCES} from '../settings/userPreferences.js'
import './viewer3d.css'

export function Benchmark() {
  const controls=useRef(null)
  const [preferences,setPreferences]=useState(DEFAULT_PREFERENCES)
  const [result,setResult]=useState('500 devices · 200 routes · synthetic, no project writes')
  const scene=useMemo(()=>({width:30,depth:25,elevation:0,target:[15,1.5,12.5],extent:30,
    rooms:[{id:'room',boundary:[{x:0,y:0},{x:30,y:0},{x:30,y:25},{x:0,y:25}]}],
    walls:[{id:'back',position:[15,1.5,0],size:[30,3,.15],rotation:[0,0,0]},
      {id:'side',position:[0,1.5,12.5],size:[25,3,.15],rotation:[0,Math.PI/2,0]}],
    symbols:Array.from({length:500},(_,i)=>({id:`device-${i}`,position:[.6+(i%25)*1.15,0,.6+Math.floor(i/25)*1.15],
      presentation:i%10===0 ? {family:'troffer',label:'Troffer lights'} : {family:'linear-light',label:i%2 ? '1 x 40 watts fluorescent lamp' : '2 x 40 watts fluorescent lamp'},
      classification:{name:'Lighting fixture'},installation:{height_above_floor_meters:3,mounting_reference:'connection_point'}})),
    routeSegments:Array.from({length:200},(_,i)=>({routeId:`route-${i}`,segmentIndex:0,provenance:'observed',
      installationMethod:'concealed_in_ceiling',elevationState:'stored',start:[.6+(i%20),3,1+Math.floor(i/20)*2],end:[1.4+(i%20),3,1+Math.floor(i/20)*2]}))
  }),[])
  function run() {
    setResult('Measuring 12 seconds of camera transitions…')
    let start=null,last=null,frames=0,seconds=0
    function frame(time) {
      if(start==null)start=time
      if(last!=null){frames++;seconds+=(time-last)/1000}
      last=time
      if(time-start<12000){controls.current?.benchmarkOrbit((time-start)/12000*Math.PI*2);requestAnimationFrame(frame)}
      else setResult(`${(frames/seconds).toFixed(1)} animation FPS · ${window.innerWidth} × ${window.innerHeight} viewport · ${navigator.userAgent}`)
    }
    requestAnimationFrame(frame)
  }
  return <PreferencesContext.Provider value={{preferences,updatePreferences:p=>setPreferences(v=>({...v,...p}))}}>
    <header><button onClick={run}>Run 12-second orbit benchmark</button><output>{result}</output></header>
    <Viewer3DCanvas scene={scene} controlsRef={controls} projectLabel="VED synthetic verification" estimated />
  </PreferencesContext.Provider>
}
if(import.meta.env.DEV)createRoot(document.getElementById('root')).render(<Benchmark/> )
