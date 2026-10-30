"""Adapt Kenney CC0 ceiling housing in Blender; export representative fixtures.

Input: creator-published Furniture Pack 1.0 from OpenGameArt (see credits).
Only imports OBJ data; never runs downloaded scripts. No official prices.
"""
import json
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'outputs/studio-assets/kenney-oga/Models/lampSquareCeiling.obj'
OUT = ROOT / 'frontend/public/studio-devices/premade-v1'
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath=str(SOURCE), forward_axis='NEGATIVE_Z', up_axis='Y')
for obj in list(bpy.context.scene.objects):
    if obj.type != 'MESH':
        continue
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    mesh = bmesh.new()
    mesh.from_mesh(obj.data)
    # Retain the premade lamp housing, removing the decorative suspension stem.
    bmesh.ops.delete(mesh, geom=[v for v in mesh.verts if v.co.z > 1.501], context='VERTS')
    mesh.to_mesh(obj.data)
    mesh.free()
    coords = [v.co for v in obj.data.vertices]
    lo = Vector([min(v[i] for v in coords) for i in range(3)])
    hi = Vector([max(v[i] for v in coords) for i in range(3)])
    center = (lo + hi) / 2
    size = hi - lo
    for v in obj.data.vertices:
        v.co = Vector([(v.co[i] - center[i]) / size[i] * [.6, 1.2, .09][i] for i in range(3)])
    for mat in obj.data.materials:
        mat.use_nodes = True
        shader = mat.node_tree.nodes.get('Principled BSDF')
        lens = mat.name.startswith('lamp')
        shader.inputs['Base Color'].default_value = (0.94, .95, .95, 1) if lens else (.65, .7, .73, 1)
        shader.inputs['Metallic'].default_value = 0 if lens else .65
        shader.inputs['Roughness'].default_value = .35 if lens else .28
        if lens:
            shader.inputs['Emission Color'].default_value = (1, .95, .85, 1)
            shader.inputs['Emission Strength'].default_value = .18
    bevel = obj.modifiers.new('Housing edge highlights', 'BEVEL')
    bevel.width = .0015
    bevel.segments = 2
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -.042))
diffuser = bpy.context.object
diffuser.name = 'VED inset diffuser'
diffuser.dimensions = (.39, .785, .004)
mat = bpy.data.materials.new('Diffuser')
mat.use_nodes = True
shader = mat.node_tree.nodes.get('Principled BSDF')
shader.inputs['Base Color'].default_value = (.96, .97, .98, 1)
shader.inputs['Roughness'].default_value = .4
shader.inputs['Emission Color'].default_value = (1, .96, .87, 1)
shader.inputs['Emission Strength'].default_value = .15
diffuser.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'outputs/studio-assets/kenney-troffer.blend'))
bpy.ops.export_scene.gltf(filepath=str(OUT / 'troffer.glb'), export_format='GLB', export_yup=True)
size = (OUT / 'troffer.glb').stat().st_size
assert size < 250_000
(OUT / 'manifest.json').write_text(json.dumps({
    'revision': 1, 'author': 'Kenney; VED Blender adaptation', 'license': 'CC0-1.0',
    'source': 'https://opengameart.org/content/furniture-kit',
    'originalObject': 'lampSquareCeiling.obj', 'status': 'representative',
    'changes': 'Suspension removed; housing fitted to illustrative troffer envelope; inset diffuser, PBR materials and bevels',
    'nominalDimensionsMetres': {'x': .6, 'y': .09, 'z': 1.2}, 'bytes': size,
    'anchors': 'Existing canonical devicePlacement; mesh does not define connectivity',
}, indent=2), encoding='utf-8')
print('PREMADE_COMPLETE', size)
