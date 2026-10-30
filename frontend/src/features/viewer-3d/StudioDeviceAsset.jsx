import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useThree } from '@react-three/fiber'
import { Box3, Vector3 } from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { DeviceBody } from './DeviceBody.jsx'

const cache=new Map()
const foregroundFrames=new WeakMap()
function beginDevicePass(renderer) {
  const frame=renderer.info.render.frame
  if(foregroundFrames.get(renderer)===frame)return
  // Reveal devices through architecture without drawing their rear housings
  // over their own faceplates. Devices still depth-test against one another.
  renderer.clearDepth()
  foregroundFrames.set(renderer,frame)
}
function loadAsset(url) {
  if(!cache.has(url))cache.set(url,new GLTFLoader().loadAsync(url).then(gltf=>{
    const root=gltf.scene
    root.traverse(object=>{if(object.isMesh){object.castShadow=true;object.receiveShadow=true}})
    root.updateMatrixWorld(true)
    const bounds=new Box3().setFromObject(root),size=bounds.getSize(new Vector3()),center=bounds.getCenter(new Vector3())
    if(![size.x,size.y,size.z].every(v=>Number.isFinite(v)&&v>0))throw new Error('Invalid asset bounds')
    // Normalize only the visual housing to the existing resolved placement.
    // Authoritative mounting references and connectors remain in devicePlacement.
    root.position.sub(center)
    const wrapper=root.clone(true)
    return {root:wrapper,size}
  }))
  return cache.get(url)
}

export function StudioDeviceAsset({asset,family,label,selected}) {
  const {invalidate}=useThree()
  const [loaded,setLoaded]=useState(null)
  const visual = useRef(null)
  useLayoutEffect(() => {
    const originals = []
    visual.current?.traverse(object => {
      if (!object.isMesh) return
      const original = object.material
      const beforeRender=object.onBeforeRender,order=object.renderOrder
      const clone = material => { const result = material.clone(); result.depthTest = true; result.depthWrite = !result.transparent; return result }
      object.material = Array.isArray(original) ? original.map(clone) : clone(original)
      object.renderOrder = 20
      object.onBeforeRender=function(renderer,...args){beginDevicePass(renderer);beforeRender.call(this,renderer,...args)}
      originals.push([object, original, object.material,beforeRender,order])
    })
    invalidate()
    return () => originals.forEach(([object, original, temporary,beforeRender,order]) => {
      object.material = original
      object.onBeforeRender=beforeRender
      object.renderOrder=order
      ;(Array.isArray(temporary) ? temporary : [temporary]).forEach(material => material.dispose())
    })
  }, [loaded, family, label, selected,invalidate])
  useEffect(()=>{
    let active=true
    if(asset)loadAsset(asset.url).then(value=>{
      if(active)setLoaded({url:asset.url,root:value.root.clone(true),size:value.size})
    }).catch(()=>{/* The procedural body remains usable after an asset failure. */})
    return()=>{active=false}
  },[asset?.url]) // eslint-disable-line react-hooks/exhaustive-deps
  if(!asset || loaded?.url!==asset.url)return <group ref={visual}><DeviceBody family={family} label={label} selected={selected}/></group>
  return <group ref={visual} scale={[1/loaded.size.x,1/loaded.size.y,1/loaded.size.z]}>
    <primitive object={loaded.root} dispose={null}/>
  </group>
}
