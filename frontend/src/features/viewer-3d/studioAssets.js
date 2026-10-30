// Explicit identity mappings. No prices and no fuzzy product-name matching.
const products = {
  'VED-ASSEMBLY-SIMPLEX-PANA':'outlet-1', 'VED-ASSEMBLY-DUPLEX10-PANA':'outlet-2',
  'VED-ASSEMBLY-DUPLEX16-PANA':'outlet-2','VED-ASSEMBLY-SWITCH1-PANA':'switch-1',
  'VED-ASSEMBLY-SWITCH2-PANA':'switch-2','VED-ASSEMBLY-SWITCH3-PANA':'switch-3',
  'VED-ASSEMBLY-SWITCH3WAY-PANA':'switch-1','VED-ASSEMBLY-DATA1-PANA':'data-1',
  'VED-ASSEMBLY-DATA2-PANA':'data-2','VED-ASSEMBLY-DATA1-BELDEN-CAT5E':'data-1',
  'VED-ASSEMBLY-DATA2-BELDEN-CAT5E':'data-2','VED-ASSEMBLY-CCTV-HIK-IP':'cctv-dome',
  'VED-ASSEMBLY-CCTV-HIK-ANALOG':'cctv-bullet',
}
const deviceTypes={simplex_outlet:'outlet-1',duplex_outlet:'outlet-2',switch_1gang:'switch-1',
  switch_2gang:'switch-2',switch_3gang:'switch-3',switch_3way:'switch-1',data_simplex:'data-1',data_duplex:'data-2'}
const labels={
  '1 x 40 watts fluorescent lamp':'linear-1','2 x 40 watts fluorescent lamp':'linear-2',
  'One gang device switch':'switch-1','Two gang device switch':'switch-2','Three gang device switch':'switch-3',
  'One gang switch':'switch-1','Two gang switch':'switch-2','Three gang switch':'switch-3',
  'Simplex outlet':'outlet-1','Duplex outlet':'outlet-2','Single data outlet':'data-1','Duplex data outlet':'data-2',
}
export function studioAsset(symbol,product) {
  const identity=product?.product_identity
  const label=symbol?.presentation?.label || symbol?.classification?.name
  if (symbol?.presentation?.family==='troffer' || label==='Troffer lights') {
    return {key:'troffer',url:'/studio-devices/premade-v1/troffer.glb',status:'Representative model · Kenney / Blender',revision:1}
  }
  const key=products[identity?.code] || deviceTypes[identity?.device_type] || labels[label]
    || (symbol?.presentation?.family==='panel' ? 'panel' : null)
  return key ? {key,url:`/studio-devices/v1/${key}.glb`,status:'Representative model',revision:1} : null
}
export function studioProductRows(bom) {
  const rows={}
  for(const row of bom?.planning?.items || []) {
    if(row.kind!=='device')continue
    for(const id of row.symbol_ids || [])rows[id]=row
  }
  return rows
}
