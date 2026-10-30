import {useEffect,useState} from 'react'

export function ProjectAge({createdAt}) {
  const [now,setNow]=useState(()=>Date.now())
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),3600000);return()=>clearInterval(timer)},[])
  const value=createdAt && new Date(/[zZ]|[+-]\d\d:\d\d$/.test(createdAt)?createdAt:`${createdAt}Z`)
  if(!value || Number.isNaN(value.getTime()))return null
  const days=Math.max(0,Math.floor((now-value.getTime())/86400000))
  if(days>30)return null
  return <span className="project-age" title={`Created ${value.toLocaleString()}`}>{days===0?'New':`${days} ${days===1?'day':'days'} ago`}</span>
}
