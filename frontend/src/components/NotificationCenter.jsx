import { useCallback, useEffect, useRef, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { Bell, CheckCheck, MessageSquare, RefreshCw, X } from 'lucide-react'
import { workflowRequest } from '../api/clientWorkflow.js'
import emptyIcon from '../assets/icons8/notification-off.png'
import './NotificationCenter.css'
import { AccountDialog } from '../features/settings/AccountDialog.jsx'

export function NotificationCenter() {
  const [open,setOpen]=useState(false),[kind,setKind]=useState('system'),[feed,setFeed]=useState(null),[error,setError]=useState(''),[reading,setReading]=useState(false)
  const anchor=useRef(null),sequence=useRef(0)
  const [report,setReport]=useState(null),[reportError,setReportError]=useState('')
  const reportSequence=useRef(0)
  function closeReport(){++reportSequence.current;setReport(null);setOpen(true)}
  async function openReport(item){
    const request=++reportSequence.current
    setOpen(false);setReport({title:item.title,loading:true});setReportError('');read(item.id)
    try{const result=await workflowRequest(`/notifications/${item.id}`);if(request===reportSequence.current)setReport(result)}catch(e){if(request===reportSequence.current){setReportError(e.message);setReport({title:item.title})}}
  }
  const [position,setPosition]=useState({top:70,left:16,maxHeight:520})
  const load=useCallback(async signal=>{
    const request=++sequence.current
    try {const result=await workflowRequest('/notifications',{signal});if(!signal?.aborted&&request===sequence.current){setFeed(result);setError('')}}
    catch(e){if(!signal?.aborted&&request===sequence.current)setError(e.message)}
  },[])
  useEffect(()=>{
    const controller=new AbortController()
    queueMicrotask(()=>{if(!controller.signal.aborted)load(controller.signal)})
    const refresh=()=>{if(!document.hidden)load(controller.signal)}
    const timer=window.setInterval(refresh,60000)
    window.addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh)
    return ()=>{controller.abort();window.clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh)}
  },[load])
  useEffect(()=>{
    if(!open)return
    const place=()=>{const bounds=anchor.current?.getBoundingClientRect();if(!bounds)return
      const top=Math.min(bounds.bottom+10,Math.max(12,window.innerHeight-270))
      setPosition({top,left:Math.max(12,Math.min(bounds.left,window.innerWidth-402)),maxHeight:window.innerHeight-top-12})}
    place();window.addEventListener('resize',place)
    return ()=>window.removeEventListener('resize',place)
  },[open])
  async function read(through=feed?.latest?.[kind]) {
    if(!through||reading)return
    setReading(true);const request=++sequence.current
    try{const result=await workflowRequest('/notifications/read',{method:'POST',body:{kind,through_id:through}});if(request===sequence.current){setFeed(result);setError('')}}
    catch(e){setError(e.message)}finally{setReading(false)}
  }
  const count=(feed?.unread?.system||0)+(feed?.unread?.comments||0)
  const items=feed?.items.filter(item=>item.kind===kind)||[]
  return <><Dialog.Root open={open} onOpenChange={value=>{setOpen(value);if(value)load()}} modal={false}>
    <Dialog.Trigger asChild><button ref={anchor} type="button" className="notification-trigger" aria-label={`Notifications${count?`, ${count} unread`:''}`} title="Notifications"><Bell size={19}/>{count>0&&<span className="notification-badge">{count>99?'99+':count}</span>}</button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Content className="notification-panel" style={position}>
      <div className="notification-heading"><Dialog.Title>Notifications</Dialog.Title><Dialog.Close className="notification-icon-button" aria-label="Close notifications"><X size={18}/></Dialog.Close></div>
      <Dialog.Description className="notification-sr-only">Admin updates and comments for your assigned work.</Dialog.Description>
      <div className="notification-tabs" role="tablist" aria-label="Notification type">{['system','comments'].map(value=><button type="button" key={value} role="tab" id={`notification-${value}-tab`} aria-controls={`notification-${value}-panel`} aria-selected={kind===value} tabIndex={kind===value?0:-1} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'system':event.key==='End'?'comments':value==='system'?'comments':'system';setKind(next);document.getElementById(`notification-${next}-tab`)?.focus()}}} onClick={()=>setKind(value)}>{value==='system'?<Bell size={15}/>:<MessageSquare size={15}/>} {value==='system'?'System':'Comments'}{feed?.unread[value]>0&&<span>{feed.unread[value]}</span>}</button>)}</div>
      <div className="notification-toolbar"><span>{feed?`${feed.unread[kind]} unread`:'Loading…'}</span><button type="button" disabled={reading||!feed?.unread[kind]} onClick={()=>read()}><CheckCheck size={14}/>Mark read</button></div>
      {error&&<div className="notification-error" role="alert">{error}<button type="button" onClick={()=>load()}><RefreshCw size={14}/>Retry</button></div>}
      <div className="notification-items" role="tabpanel" id={`notification-${kind}-panel`} aria-labelledby={`notification-${kind}-tab`} tabIndex={0}>
        {items.map(item=><button type="button" key={item.id} className={`notification-item${item.unread?' is-unread':''}`} onClick={()=>openReport(item)}><strong>{item.title}</strong>{item.context&&<small>{item.context}</small>}<p>{item.body}</p><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})}</time></button>)}
        {feed&&!items.length&&!error&&<div className="notification-empty"><img src={emptyIcon} width="64" height="64" alt=""/><strong>{kind==='comments'?'No comments yet':'You’re all caught up'}</strong><p>{kind==='comments'?'Approval and return comments from Admin will appear here.':'Important updates from Admin will appear here.'}</p><a href="https://icons8.com/icons/set/no-notification" target="_blank" rel="noreferrer">Icons by Icons8</a></div>}
      </div>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>{report&&<AccountDialog title={report.title} description={report.loading?'Loading report…':report.context||'System report'} onClose={closeReport}>
    {reportError&&<p role="alert">{reportError}</p>}{!report.loading&&!reportError&&<div className="notification-report"><small>{report.author} · {new Date(report.created_at).toLocaleString()}</small><p>{report.effect}</p><ul>{report.changes.map(change=><li key={change.id}><strong>{change.title}</strong>{change.item_number&&<small>{change.item_number}</small>}<p>{change.description}</p>{change.current_price&&<small>Current price: {change.current_price.currency} {Number(change.current_price.amount).toLocaleString()} / {change.current_price.unit}</small>}</li>)}</ul>{report.href&&report.kind==='comments'&&<a href={report.href} onClick={()=>setReport(null)}>Open workspace</a>}<button type="button" onClick={()=>{setReport(null);setOpen(true)}}>Back to notifications</button></div>}
  </AccountDialog>}</>
}
