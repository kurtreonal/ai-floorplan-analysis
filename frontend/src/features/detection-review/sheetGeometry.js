const paperMm={A0:[841,1189],A1:[594,841],A2:[420,594],A3:[297,420],A4:[210,297],A5:[148,210]}

export function sheetGeometry(width,height,context={},settings={}) {
  const nativeWidth=context.source_width_mm,nativeHeight=context.source_height_mm
  const physical=nativeWidth>0 && nativeHeight>0
  const size=settings.display_paper_size || 'ORIGINAL'
  let dimensions=size==='CUSTOM' ? [Number(settings.display_width_mm),Number(settings.display_height_mm)] : paperMm[size]
  if(size==='ORIGINAL' || !dimensions?.every(v=>Number.isFinite(v)&&v>0))dimensions=physical ? [nativeWidth,nativeHeight]:[width,height]
  const orientation=settings.display_orientation || (width>=height ? 'landscape':'portrait')
  const [short,long]=[...dimensions].sort((a,b)=>a-b)
  const [paperWidth,paperHeight]=orientation==='landscape' ? [long,short]:[short,long]
  // Fill the selected sheet by uniform containment. Image coordinates remain source pixels.
  const unitsPerMm=Math.max(width/paperWidth,height/paperHeight)
  const sheetWidth=Math.max(width,paperWidth*unitsPerMm),sheetHeight=Math.max(height,paperHeight*unitsPerMm)
  const label=size==='ORIGINAL' ? physical ? `Original page · ${Number(nativeWidth.toFixed(1))} × ${Number(nativeHeight.toFixed(1))} mm`:'Original image'
    : `${size==='CUSTOM' ? 'Custom':size} · ${Number(paperWidth.toFixed(1))} × ${Number(paperHeight.toFixed(1))} mm`
  return {x:(width-sheetWidth)/2,y:(height-sheetHeight)/2,width:sheetWidth,height:sheetHeight,label}
}
