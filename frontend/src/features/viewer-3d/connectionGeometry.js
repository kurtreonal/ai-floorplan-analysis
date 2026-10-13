// A rendering derivative of an explicit connection. Never an electrical
// inference, persisted offset, conduit diameter or BOM measurement input.
export function connectionLead(service, connector) {
  const top=[connector[0],service[1],connector[2]], corner=[top[0],service[1],service[2]]
  return [[service,corner],[corner,top],[top,connector]]
    .filter(([a,b]) => Math.hypot(...b.map((v,i) => v-a[i]))>1e-8)
    .map(([start,end]) => ({start,end,vertical:start[1]!==end[1]}))
}
