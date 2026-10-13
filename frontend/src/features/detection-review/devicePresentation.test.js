import { describe, expect, it } from 'vitest'
import { autoLinkSymbols, relatedSymbolIds, updateRelatedSymbols, clampDevicePoint, describeReviewSymbol, deviceFamily, reviewGeometryPayload } from './devicePresentation.js'

describe('device presentation without class approval', () => {
  it('links the requested provisional one-gang default without overwriting raw prediction or approving it',()=>{
    const raw={id:'s1',observed_label:'Gang switch',gang_count_proposal:{count:1,basis:'user_requested_default',provisional:true}}
    const record={candidate:{payload:{symbols:{items:[raw]}}}}
    const legends=[{id:12,name:'One gang device switch',is_active:true,class_id:22}]
    const symbol={id:'s1',symbol_legend_id:null,disposition:'unresolved'}
    const presentation=describeReviewSymbol(symbol,record,legends)
    expect(presentation.name).toContain('provisional')
    expect(presentation.originalLabel).toBe('Gang switch')
    expect(presentation.suggestedLegendId).toBe(12)
    expect(autoLinkSymbols([symbol],record,legends)[0]).toEqual({...symbol,symbol_legend_id:12})
    expect(raw.observed_label).toBe('Gang switch')
    expect(describeReviewSymbol(symbol,record,[...legends,{...legends[0],id:13}]).suggestedLegendId).toBeNull()
    const corrected=updateRelatedSymbols([symbol],'s1',record,{symbol_legend_id:12,gang_count_confirmed:true})[0]
    expect(corrected.disposition).toBe('corrected')
    const body=reviewGeometryPayload({walls:[],rooms:[],symbols:[{...corrected,center:{x:5,y:6}}]})
    expect(body.symbols[0].gang_count_confirmed).toBe(true)
  })
  it('auto-links exact catalog identities without model-index mapping or approving geometry',()=>{
    const record={candidate:{provenance:{model_release_id:'development_multiclass56_yolo'},payload:{symbols:{items:[
      {id:'s1',training_legend:{name:'Lamp 40W',legend_entry:'sheet-08:L01',model_class_id:9}},
      {id:'s2',catalog_class_id:12}]}}}}
    const symbols=[{id:'s1',disposition:'unresolved',symbol_legend_id:null},{id:'s2',disposition:'unresolved',symbol_legend_id:null}]
    const legends=[{id:9,class_id:11,name:'Lamp 40W [sheet-07:L01]'},{id:10,class_id:12,name:'Lamp 40W [sheet-08:L01]'}]
    expect(autoLinkSymbols(symbols,record,legends).map(s=>s.symbol_legend_id)).toEqual([10,10])
    expect(autoLinkSymbols(symbols,record,legends).every(s=>s.disposition==='unresolved')).toBe(true)
    expect(autoLinkSymbols(symbols,record,[legends[0]]).map(s=>s.symbol_legend_id)).toEqual([null,null])
    expect(autoLinkSymbols(symbols,record,[legends[1],{...legends[1],id:11}]).map(s=>s.symbol_legend_id)).toEqual([null,null])
  })
  it('updates related classes/prices together but never copies coordinates or touches removed/unknown devices',()=>{
    const record={candidate:{payload:{symbols:{items:[]}}}}
    const symbols=[{id:'s1',symbol_legend_id:9,disposition:'unresolved',center:{x:1,y:2}},
      {id:'s2',symbol_legend_id:9,disposition:'unresolved',center:{x:3,y:4}},
      {id:'s3',symbol_legend_id:9,disposition:'rejected'}, {id:'s4',symbol_legend_id:10,disposition:'unresolved'},
      {id:'s5',symbol_legend_id:null,disposition:'unresolved'}, {id:'s6',symbol_legend_id:null,disposition:'unresolved'}]
    expect(relatedSymbolIds(symbols,'s1',record)).toEqual(['s1','s2'])
    expect(relatedSymbolIds(symbols,'s5',record)).toEqual(['s5'])
    const updated=updateRelatedSymbols(symbols,'s1',record,{symbol_legend_id:11,custom_unit_price:123,center:{x:9,y:9}})
    expect(updated.slice(0,2).map(s=>[s.symbol_legend_id,s.custom_unit_price,s.center])).toEqual([[11,123,{x:1,y:2}],[11,123,{x:3,y:4}]])
    expect(updated.slice(2)).toEqual(symbols.slice(2))
  })
  it.each([
    ['Troffer light', 'troffer'], ['Fluorescent light with reflector', 'linear-light'], ['Orientable downlight', 'round-light'],
    ['2 x 40 watts fluorescent lamp', 'linear-light'], ['1 x 40 watts fluorescent lamp', 'linear-light'],
    ['Duplex convenience outlet, grounding type', 'outlet'], ['Weatherproof type duplex convenience outlet', 'outlet'],
    ['Distribution board', 'panel'], ['Panelboard', 'panel'], ['Duplex power outlet', 'outlet'], ['Three way switch', 'switch'],
    ['One gang device switch', 'switch'], ['Two gang device switch', 'switch'], ['Three gang device switch', 'switch'],
    ['Smoke detector', 'detector'], ['Pull station', 'pull-station'], ['Alarm bell', 'alarm'], ['Circuit home-run notation', 'annotation'], ['Unclassified circular symbol', 'unknown'],
  ])('uses a schematic %s representation without changing its class', (name, family) => { expect(deviceFamily(name)).toBe(family) })

  const record = { candidate: { payload: { symbols: { items: [{ id: 'symbol-0001', observed_label: 'Troffer light' }] } } }, review: null }
  it('translates visual glyph bounds with a corrected anchor without changing source evidence', () => {
    const source = structuredClone(record)
    source.candidate.payload.symbols.items[0] = { ...source.candidate.payload.symbols.items[0],
      center: { x: 100,y: 100 }, bounds: { x: 90,y: 80,width: 20,height: 40 } }
    const before = structuredClone(source)
    const symbol = { id: 'symbol-0001',center: { x: 300,y: 400 },symbol_legend_id: null }
    expect(describeReviewSymbol(symbol,source).sourceBounds).toEqual({ x: 290,y: 380,width: 20,height: 40 })
    expect(source).toEqual(before)
    expect(reviewGeometryPayload({ walls: [],rooms: [],symbols: [symbol] }).symbols[0]).not.toHaveProperty('sourceBounds')
  })
  it('shows the original detector name as provisional until a legend is linked', () => {
    const symbol = { id: 'symbol-0001', symbol_legend_id: null, disposition: 'unresolved' }
    expect(describeReviewSymbol(symbol, record)).toEqual({ name: 'Troffer light', family: 'troffer', label: 'Troffer light', mapped: false, originalLabel: 'Troffer light' })
    expect(symbol.disposition).toBe('unresolved')
    const corrected = describeReviewSymbol({ ...symbol, symbol_legend_id: 9 }, record, [{ id: 9, class_id: 4, name: 'Power outlet' }])
    expect(corrected).toMatchObject({ name: 'Power outlet', family: 'outlet', mapped: true, originalLabel: 'Troffer light' })
  })
  it('does not reuse a saved name after unmapping or changing the legend', () => {
    const saved = { ...record, review: { symbols: [{ id: 'symbol-0001', symbol_legend_id: 9, class_name: 'Reviewed outlet' }] } }
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: 9 }, saved).name).toBe('Reviewed outlet')
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: null }, saved).mapped).toBe(false)
    expect(describeReviewSymbol({ id: 'symbol-0001', symbol_legend_id: 10 }, saved).name).toBe('Troffer light')
  })
  it.each([62,63,64])('keeps switch class %s named and unresolved until explicit review', (modelClassId) => {
    const name = ['One gang device switch','Two gang device switch','Three gang device switch'][modelClassId - 62]
    const trainingLegend = { model_class_id: modelClassId, legend_entry: `pdf-76f411c60b6d:p1:L0${modelClassId - 58}`, name, dataset_sha256: 'a'.repeat(64) }
    const source = structuredClone(record)
    source.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    source.candidate.payload.symbols.items[0].training_legend = trainingLegend
    const symbol = { id: 'symbol-0001', disposition: 'unresolved', symbol_legend_id: null }
    expect(describeReviewSymbol(symbol, source)).toMatchObject({ name, family: 'switch', mapped: false })
    expect(symbol.disposition).toBe('unresolved')
    expect(symbol.symbol_legend_id).toBeNull()
  })
  it('keeps the trained name and drawing identity separate from explicit catalog mapping', () => {
    const trainingLegend = { model_class_id: 0, legend_entry: 'sheet-08:L01', name: 'Reviewed downlight', dataset_sha256: 'a'.repeat(64) }
    const source = structuredClone(record)
    source.candidate.provenance = { model_release_id: 'development_multiclass56_yolo' }
    source.candidate.payload.symbols.items[0].training_legend = trainingLegend
    const symbol = { id: 'symbol-0001', disposition: 'unresolved', symbol_legend_id: null }
    const legends = [{ id: 91, class_id: 0, name: 'Reviewed downlight [sheet-07:L01]' },
      { id: 92, class_id: 70, name: 'Reviewed downlight [sheet-08:L01]' }]
    const display = describeReviewSymbol(symbol, source, legends)
    expect(display).toMatchObject({ name: 'Reviewed downlight', mapped: false, suggestedLegendId: 92, trainingLegend })
    expect(symbol.symbol_legend_id).toBeNull()
    expect(symbol.disposition).toBe('unresolved')
    expect(describeReviewSymbol(symbol, source, [legends[0]]).suggestedLegendId).toBeNull()
    expect(describeReviewSymbol(symbol, source, [...legends, { ...legends[1], id: 93 }]).suggestedLegendId).toBeNull()
    source.candidate.provenance.model_release_id = 'local_vlm'
    expect(describeReviewSymbol(symbol, source, legends).name).toBe('Troffer light')
    expect(describeReviewSymbol(symbol, source, legends).trainingLegend).toBeUndefined()
  })
  it('bounds coordinates, rejects non-finite values and strips display-only data from strict writes', () => {
    expect(clampDevicePoint({ x: -1, y: 300.9 }, 400, 300)).toEqual({ x: 0, y: 300 })
    expect(clampDevicePoint({ x: NaN, y: 0 }, 400, 300)).toBeNull()
    const draft = { walls: [{ id: 'wall-0001', disposition: 'accepted', start: { x: 0, y: 0 }, end: { x: 10, y: 0 }, estimated_thickness_pixels: 8 }], rooms: [],
      symbols: [{ id: 'symbol-0001', disposition: 'rejected', center: { x: 20, y: 30 }, symbol_legend_id: 9, class_name: 'Private legend', presentation: {} }] }
    const before = structuredClone(draft)
    const payload = reviewGeometryPayload(draft)
    expect(Object.keys(payload.walls[0])).toEqual(['id', 'disposition', 'start', 'end','estimated_thickness_pixels'])
    expect(payload.walls[0].estimated_thickness_pixels).toBe(8)
    expect(Object.keys(payload.symbols[0])).toEqual(['id', 'disposition', 'center', 'symbol_legend_id'])
    expect(payload.symbols[0].disposition).toBe('rejected')
    expect(draft).toEqual(before)
  })
})
