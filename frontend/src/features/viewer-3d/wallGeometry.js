import {BufferGeometry,Float32BufferAttribute,ShapeUtils,Vector2} from 'three'

// Partitioned top/bottom surfaces plus UNION exterior sides only. No hidden
// shared end-cap faces are emitted, and every mesh retains its wall identity.
export function joinedWallGeometry(wall) {
  const positions=[]
  const push=(p,y)=>positions.push(p.x,y,p.y)
  for(const poly of wall.footprints) {
    for(const [a,b,c] of ShapeUtils.triangulateShape(poly.map(p=>new Vector2(p.x,p.y)),[])) {
      push(poly[a],0);push(poly[b],0);push(poly[c],0)
      push(poly[c],wall.height);push(poly[b],wall.height);push(poly[a],wall.height)
    }
  }
  for(const [a,b] of wall.boundary) {
    push(a,0);push(b,wall.height);push(b,0)
    push(a,0);push(a,wall.height);push(b,wall.height)
  }
  const geometry=new BufferGeometry()
  geometry.setAttribute('position',new Float32BufferAttribute(positions,3))
  geometry.computeVertexNormals();geometry.computeBoundingBox();geometry.computeBoundingSphere()
  return geometry
}
