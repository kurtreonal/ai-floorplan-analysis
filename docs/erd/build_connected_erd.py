"""One-canvas physical ERD; route direct relationships without crossings."""
import heapq
import html
import itertools
import json
import math
import random
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
sys.path.append(str(OUT.parents[1] / 'backend/.venv/Lib/site-packages'))
import networkx as nx

DATA = json.loads((OUT/'schema-metadata.json').read_text(encoding='utf-8'))
TABLES = {t['name']: t for t in DATA['tables']}
GRID, TW, HEAD, ROW = 8, 360, 28, 24
NAMES = [
 ['symbol_legends','roles','users','dataset_approver_assignments','materials','material_prices'],
 ['symbol_legend_history','detection_class_corrections','detection_reviews','projects','estimates','estimate_items'],
 ['manual_symbols','detected_symbols','processing_jobs','floor_plans','project_floors','estimate_sources'],
 ['walls','processing_job_attempts','processing_job_cancellations','floor_plan_sources','layout_versions','layout_save_requests'],
 ['interpretation_releases','floor_plan_interpretation_reviews','floor_plan_interpretation_runs','processing_artifacts','floor_plan_pages','generated_route_versions'],
 [None,None,'interpretation_page_outcomes',None,'page_scale_settings','floor_elevation_settings'],
]
BOXES={}
y=280
for row in NAMES:
    mh=max(HEAD+ROW*len(TABLES[n]['columns']) for n in row if n)
    for col,n in enumerate(row):
        if n:
            BOXES[n]={'x':200+col*616,'y':y,'w':TW,'h':HEAD+ROW*len(TABLES[n]['columns'])}
    y+=math.ceil((mh+240)/GRID)*GRID
W,H=3864,y+100
NX,NY=W//GRID+1,H//GRID+1
node_mask=np.zeros((NY,NX),dtype=np.bool_)
for b in BOXES.values():
    x1,y1=math.floor((b['x']-8)/GRID),math.floor((b['y']-8)/GRID)
    x2,y2=math.ceil((b['x']+b['w']+8)/GRID),math.ceil((b['y']+b['h']+8)/GRID)
    node_mask[y1:y2+1,x1:x2+1]=True
node_mask[:24,:]=True

edges=[]
for name,t in TABLES.items():
    for fk in t['foreign_keys']:
        assert len(fk['constrained_columns'])==1
        col=fk['constrained_columns'][0]
        idx=next(i for i,c in enumerate(t['columns']) if c['name']==col)
        required=not t['columns'][idx]['nullable']
        uniques=[set(t['primary_key'])]+[set(u['column_names']) for u in t['unique_constraints']]
        unique=any(u and u.issubset({col}) for u in uniques)
        edges.append({'id':f'R{len(edges)+1:02d}','child':name,'parent':fk['referred_table'],
                      'column':col,'column_index':idx,'required':required,'unique':unique,'fk_name':fk['name']})

def distance(e):
    a,b=BOXES[e['child']],BOXES[e['parent']]
    return abs(a['x']-b['x'])+abs(a['y']-b['y'])

g=nx.Graph()
g.add_nodes_from(TABLES)
for e in edges:
    g.add_edge(e['child'],e['parent'],weight=distance(e))
tree=nx.minimum_spanning_tree(g)
used_pairs=set()
tree_edges=[]
other_edges=[]
for e in sorted(edges,key=distance):
    pair=frozenset((e['child'],e['parent']))
    if tree.has_edge(e['child'],e['parent']) and pair not in used_pairs:
        tree_edges.append(e)
        used_pairs.add(pair)
    else:
        other_edges.append(e)

def cells_between(a,b):
    x1,y1=a; x2,y2=b
    assert x1==x2 or y1==y2
    if x1==x2:
        return [(x1,y) for y in range(min(y1,y2),max(y1,y2)+1)]
    return [(x,y1) for x in range(min(x1,x2),max(x1,x2)+1)]

def port_options(e,parent=False):
    b=BOXES[e['parent'] if parent else e['child']]
    x,y,w,h=b['x'],b['y'],b['w'],b['h']
    if not parent:
        cy=y+HEAD+e['column_index']*ROW+ROW/2
        yield {'point':((x-24)//GRID,int(cy)//GRID),'end':(x,cy),'side':'left','fraction':.5}
        yield {'point':((x+w+24)//GRID,int(cy)//GRID),'end':(x+w,cy),'side':'right','fraction':.5}
    if True:
        # Attach incoming references to the entity boundary, never to an unrelated attribute.
        for cx in range(x+24,x+w-16,24):
            yield {'point':(cx//GRID,(y-24)//GRID),'end':(cx,y),'side':'top','fraction':(cx-x)/w}
            by=math.ceil((y+h+24)/GRID)
            yield {'point':(cx//GRID,by),'end':(cx,y+h),'side':'bottom','fraction':(cx-x)/w}
        if parent:
            for cy in range(y+16,y+h-8,24):
                yield {'point':((x-24)//GRID,cy//GRID),'end':(x,cy),'side':'left','fraction':(cy-y)/h}
                yield {'point':((x+w+24)//GRID,cy//GRID),'end':(x+w,cy),'side':'right','fraction':(cy-y)/h}

def available_port(p,occupied):
    px,py=p['point']
    ex,ey=(round(v/GRID) for v in p['end'])
    for x,y in cells_between((px,py),(ex,ey)):
        if x<2 or y<25 or x>=NX-2 or y>=NY-2 or occupied[y,x]:
            return False
    return not node_mask[py,px]

def find_route(e,occupied):
    starts=[p for p in port_options(e) if available_port(p,occupied)]
    goals=[p for p in port_options(e,True) if available_port(p,occupied)]
    if not starts or not goals:
        return None
    goalmap={p['point']:p for p in goals}
    gx=[p['point'][0] for p in goals];gy=[p['point'][1] for p in goals]
    xlo,xhi,ylo,yhi=min(gx),max(gx),min(gy),max(gy)
    def heuristic(x,y):
        return max(xlo-x,0,x-xhi)+max(ylo-y,0,y-yhi)
    pq=[];cost={};prev={};counter=itertools.count()
    for p in starts:
        x,y=p['point'];state=(x,y,0)
        cost[state]=0;prev[state]=p
        heapq.heappush(pq,(heuristic(x,y),next(counter),state))
    dirs=((1,0,1),(-1,0,1),(0,1,2),(0,-1,2))
    max_explore=950000
    count=0
    while pq:
        priority,_,state=heapq.heappop(pq)
        x,y,lastdir=state
        value=cost[state]
        if priority>value+heuristic(x,y)+.001:
            continue
        if (x,y) in goalmap:
            path=[(x,y)];cur=state
            while isinstance(prev[cur],tuple):
                cur=prev[cur];path.append((cur[0],cur[1]))
            path.reverse()
            return {'grid':path,'source':prev[cur],'target':goalmap[(x,y)]}
        count+=1
        if count>max_explore:
            return None
        for dx,dy,d in dirs:
            xx,yy=x+dx,y+dy
            if xx<2 or yy<25 or xx>=NX-2 or yy>=NY-2 or node_mask[yy,xx] or occupied[yy,xx]:
                continue
            newcost=value+1+(3 if lastdir and lastdir!=d else 0)
            ns=(xx,yy,d)
            if newcost<cost.get(ns,float('inf')):
                cost[ns]=newcost;prev[ns]=state
                heapq.heappush(pq,(newcost+heuristic(xx,yy),next(counter),ns))
    return None

def reserve(route,occupied):
    cells=list(route['grid'])
    for key in ('source','target'):
        p=route[key]
        ex,ey=(round(v/GRID) for v in p['end'])
        cells+=cells_between(p['point'],(ex,ey))
    for x,y in cells:
        occupied[y,x]=True

def compress(points):
    out=[]
    for p in points:
        if out and p==out[-1]:continue
        if len(out)>=2 and ((out[-2][0]==out[-1][0]==p[0]) or (out[-2][1]==out[-1][1]==p[1])):
            out[-1]=p
        else:out.append(p)
    return out

occupied=np.zeros_like(node_mask)
routes={};pending=[]
for e in tree_edges+other_edges:
    route=find_route(e,occupied)
    if route:
        reserve(route,occupied)
        route['points']=compress([route['source']['end']]+[(x*GRID,y*GRID) for x,y in route['grid']]+[route['target']['end']])
        routes[e['id']]=route
    else:
        pending.append(e)
    print(f'{e["id"]} {"direct" if route else "continuation"} {e["child"]} -> {e["parent"]}',flush=True)

direct_graph=nx.Graph();direct_graph.add_nodes_from(TABLES)
direct_graph.add_edges_from((e['child'],e['parent']) for e in edges if e['id'] in routes)
print('Direct components:',[len(c) for c in nx.connected_components(direct_graph)],flush=True)
assert max(map(len,nx.connected_components(direct_graph)))==32, 'Direct lines must connect the full related schema.'

# Continuation stubs occupy real, empty corridors and use matching relation IDs.
continuations={}
for e in pending:
    ends=[]
    for isparent in (False,True):
        options=list(port_options(e,isparent))
        chosen=None
        for p in options:
            if not available_port(p,occupied):continue
            px,py=p['point']
            if occupied[py-2:py+3,px-3:px+4].any():continue
            chosen=p;break
        if not chosen:raise RuntimeError(f'No continuation space for {e["id"]} {isparent}')
        reserve({'grid':[chosen['point']],'source':chosen,'target':chosen},occupied)
        px,py=chosen['point'];occupied[py-2:py+3,px-3:px+4]=True
        ends.append(chosen)
    continuations[e['id']]=ends

out_data={'width':W,'height':H,'boxes':BOXES,'edges':edges,'routes':routes,'continuations':continuations}
(OUT/'connected-layout.json').write_text(json.dumps(out_data,indent=2),encoding='utf-8')
print(json.dumps({'tables':len(TABLES),'relationships':len(edges),'direct':len(routes),'continuations':len(continuations),'width':W,'height':H}),flush=True)
