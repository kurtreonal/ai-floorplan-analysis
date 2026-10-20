import { useEffect, useRef, useState } from 'react'
import { previewProjectPrices, applyProjectPrices, listProjectPrices, fetchProjectPrice } from '../../api/projectPricing.js'
import { fetchItemPrices, previewItemPrices, applyItemPrices } from '../../api/itemPricing.js'
import { compatibleQuote, groupBOMRows } from './bomPricingRows.js'

export function useBOMPricing({projectId,floorId,disabled,onApplied,onVersionsChange}) {
  const [state,setState] = useState({projectId,stage:'idle',busy:false,error:'',selected:[],choices:{},query:'',type:'',scope:floorId ? `floor:${floorId}`:'project'})
  const controller = useRef(null), pending = useRef(null), fileRef = useRef(null), inFlight = useRef(false)
  useEffect(()=>()=>{
    controller.current?.abort()
    controller.current=null
    pending.current=null;fileRef.current=null;inFlight.current=false
  },[projectId])
  useEffect(()=>{
    if(!onVersionsChange)return
    const request=new AbortController()
    listProjectPrices(projectId,{signal:request.signal}).then(rows=>{if(!request.signal.aborted)onVersionsChange(rows)})
      .catch(error=>{if(!request.signal.aborted)setState(s=>({...s,error:error.message}))})
    return ()=>request.abort()
  },[projectId,onVersionsChange])
  function update(values) { setState(current=>({...current,...values,preview:null,error:''})) }
  async function execute(action) {
    if(inFlight.current || disabled) return
    inFlight.current=true;const request=new AbortController();controller.current=request;const signal=request.signal
    setState(s=>({...s,busy:true,error:''}))
    try { await action(signal) }
    catch(error) {
      if(!signal.aborted){
        const uncertain=Boolean(pending.current && (!error.status || error.status>=500))
        if(!uncertain)pending.current=null
        setState(s=>({...s,error:error.message,preview:null,uncertain}))
      }
    }
    finally { if(controller.current===request){inFlight.current=false;if(!signal.aborted)setState(s=>({...s,busy:false}))} }
  }
  function uploaded(file) {
    if(!file)return
    fileRef.current=file
    execute(async signal=>{
      const proposal=await previewProjectPrices(projectId,file,null,{signal,usage:'item_selection'})
      if(!signal.aborted)setState(s=>({...s,projectId,stage:'mapping',proposal,selected:[],choices:{},preview:null,version:null,uncertain:false}))
    })
  }
  async function loadSelection(version,signal) {
    const inventory=await fetchItemPrices(projectId,{signal,priceVersionId:version.id})
    if(!signal.aborted)setState(s=>({...s,stage:'selecting',inventory,version,selected:[],choices:{},scope:floorId ? `floor:${floorId}`:'project',preview:null,uncertain:false}))
  }
  function reviewImport() {
    execute(async signal=>{
      const request={mapping:state.proposal.document.mapping,usage:'item_selection',
        choices:state.proposal.document.rows.map(row=>({row_id:row.row_id,material_id:row.material_id,units_per_purchase:row.units_per_purchase,excluded:row.excluded}))}
      const proposal=await previewProjectPrices(projectId,fileRef.current,request,{signal})
      if(!signal.aborted)setState(s=>({...s,proposal}))
    })
  }
  function acceptImport() {
    execute(async signal=>{
      const proposal=state.proposal
      const attempt=pending.current || {kind:'import',file:fileRef.current,payload:{usage:'item_selection',mapping:proposal.document.mapping,
        choices:proposal.document.rows.map(row=>({row_id:row.row_id,material_id:row.material_id,units_per_purchase:row.units_per_purchase,excluded:row.excluded})),
        request_id:crypto.randomUUID(),confirmed:true,file_sha256:proposal.file_sha256,preview_token:proposal.preview_token,expected_version:proposal.expected_version}}
      pending.current=attempt
      const saved=await applyProjectPrices(projectId,attempt.file,attempt.payload,{signal})
      pending.current=null
      const version=await fetchProjectPrice(projectId,saved.id,{signal})
      onVersionsChange?.(await listProjectPrices(projectId,{signal}))
      await loadSelection(version,signal)
    })
  }
  function existing() {
    execute(async signal=>{
      const versions=await listProjectPrices(projectId,{signal})
      if(!signal.aborted)setState(s=>({...s,projectId,stage:'versions',versions}))
    })
  }
  function chooseVersion(id) { execute(async signal=>loadSelection(await fetchProjectPrice(projectId,Number(id),{signal}),signal)) }
  const entries=state.version?.document.rows.filter(row=>!row.excluded) || []
  const scopeFloor=state.scope?.startsWith('floor:') ? Number(state.scope.slice(6)):null
  const rows=state.inventory?.items.filter(row=>!scopeFloor || row.floor_id===scopeFloor) || []
  const groups=groupBOMRows(rows)
  const visible=groups.filter(group=>(!state.type || group.kind===state.type) && JSON.stringify([group.name,...group.components.map(row=>[row.name,row.material_name,row.symbol_ids,row.path_id])]).toLowerCase().includes(state.query.toLowerCase()))
  const chosen=row=>Object.hasOwn(state.choices,row.item_key) ? state.choices[row.item_key] : compatibleQuote(row,entries)
  function toggle(group,checked) { update({selected:checked ? [...new Set([...state.selected,group.key])]:state.selected.filter(key=>key!==group.key)}) }
  function preview(all=false) {
    const selection={price_version_id:state.version.id,scope:scopeFloor ? 'floor':'project',floor_id:scopeFloor,
      mode:all ? 'all_wiring':'selected',bindings:groups.filter(g=>all ? g.kind==='path' : state.selected.includes(g.key)).flatMap(g=>g.components.map(row=>({item_key:row.item_key,price_row_id:chosen(row)||null,material_id:entries.find(q=>q.row_id===chosen(row))?.material_id || null})))}
    execute(async signal=>{
      const value=await previewItemPrices(projectId,selection,{signal})
      if(!signal.aborted)setState(s=>({...s,preview:value,selection}))
    })
  }
  function apply() { execute(async signal=>{
    const attempt=pending.current || {kind:'items',payload:{...state.selection,request_id:crypto.randomUUID(),preview_token:state.preview.preview_token}}
    pending.current=attempt
    await applyItemPrices(projectId,attempt.payload,{signal})
    pending.current=null
    await loadSelection(state.version,signal)
    onApplied?.()
    if(!signal.aborted)setState(s=>({...s,message:'Selected item prices applied. Quantities and saved estimates are unchanged.'}))
  }) }
  function changeImport(rowId,values) { setState(s=>({...s,proposal:{...s.proposal,ready:false,document:{...s.proposal.document,rows:s.proposal.document.rows.map(row=>row.row_id===rowId ? {...row,...values}:row)}}})) }
  return {...state,stage:state.projectId===projectId ? state.stage:'idle',active:state.projectId===projectId && state.stage==='selecting',entries,groups:visible,scopeFloor,uploaded,update,toggle,chosen,previewResult:state.preview,requestPreview:preview,apply,reviewImport,acceptImport,changeImport,existing,chooseVersion,
    locked:state.busy || disabled || state.uncertain,
    selectVisible:()=>update({selected:[...new Set([...state.selected,...visible.map(g=>g.key)])]}),
    clear:()=>update({selected:[]}),
    finish:()=>{if(!pending.current){controller.current?.abort();setState(s=>({...s,stage:'idle',selected:[],choices:{},preview:null,error:''}))}},
    retry:()=>pending.current?.kind==='import' ? acceptImport():apply()}
}
