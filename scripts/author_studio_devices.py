"""Build original VED representative device meshes with Blender (no downloaded meshes).

Run: blender --background --python scripts/author_studio_devices.py
Construction coordinates: X right, Y front, Z up. Wall products rotate before
export so glTF uses Y up and +Z front.
Nominal dimensions are illustrative, not manufacturer-verified specifications.
"""
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'frontend/public/studio-devices/v1'
SOURCE = ROOT / 'outputs/studio-assets'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)


def material(name, color, roughness, metallic=0):
    value = bpy.data.materials.new(name)
    value.diffuse_color = (*color, 1)
    value.use_nodes = True
    shader = value.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Metallic'].default_value = metallic
    return value


plastic = material('Ivory polymer', (.91, .90, .86), .32)
dark = material('Graphite recess', (.028, .038, .045), .39)
steel = material('Satin metal', (.54, .59, .61), .3, .65)


def box(name, size, position, mat=plastic, bevel=.001):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Soft manufactured edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def cylinder(name, radius, depth, position, mat=plastic, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=depth, location=position, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    return obj


def plate(kind, count):
    box('Complete faceplate', (.12, .012, .075), (0, .002, 0), bevel=.004)
    box('Back housing', (.106, .018, .063), (0, -.01, 0), dark, .002)
    for index in range(count):
        x = (index-(count-1)/2) * (.086/count)
        if kind == 'switch':
            width = .076/count
            box('Rocker reveal', (width+.002, .002, .053), (x, .009, 0), dark)
            box('Rocker paddle', (width, .006, .05), (x, .012, 0), bevel=.002)
            box('Paddle seam', (width*.8, .0008, .0008), (x, .0155, 0), steel, 0)
        elif kind == 'data':
            box('Keystone', (.029, .003, .033), (x, .009, 0))
            box('RJ45 opening', (.015, .001, .014), (x, .011, 0), dark, .0003)
            for contact in range(8):
                box('Contact', (.0005, .001, .004), (x+(contact-3.5)*.0014, .012, .004), steel, 0)
        else:
            box('Socket insert', (.031, .003, .044), (x, .009, 0), bevel=.002)
            for slot in [-1, 1]:
                box('Socket opening', (.0025, .001, .009), (x+slot*.006, .011, .006), dark, .0003)
            cylinder('Earth opening', .0025, .001, (x, .011, -.011), dark, (math.pi/2, 0, 0))


def luminaire(count):
    box('Folded metal housing', (.16, 1.2, .045), (0, 0, .015), steel, .003)
    for index in range(count):
        x = (index-(count-1)/2)*.075
        cylinder('Tube diffuser', .016, 1.14, (x, 0, -.018), plastic, (math.pi/2, 0, 0))
        for y in [-.58, .58]:
            box('End holder', (.044, .025, .045), (x, y, -.012), plastic, .003)


def camera(kind):
    if kind == 'dome':
        cylinder('Dome mounting base', .06, .023, (0, 0, .025))
        bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=.05, location=(0, 0, -.008))
        bpy.context.object.name = 'Opaque dome housing'
        bpy.context.object.data.materials.append(dark)
        cylinder('Lens', .016, .005, (0, .045, -.012), steel, (math.pi/2, 0, 0))
    else:
        box('Camera body', (.065, .13, .06), (0, .025, 0), bevel=.007)
        cylinder('Lens bezel', .026, .006, (0, .094, 0), dark, (math.pi/2, 0, 0))
        cylinder('Lens glass', .015, .007, (0, .098, 0), steel, (math.pi/2, 0, 0))
        cylinder('Mount', .03, .012, (0, -.07, 0), plastic, (math.pi/2, 0, 0))
        box('Mount arm', (.018, .04, .018), (0, -.047, 0), steel)


variants = [('outlet-1','outlet',1),('outlet-2','outlet',2),
    ('switch-1','switch',1),('switch-2','switch',2),('switch-3','switch',3),
    ('data-1','data',1),('data-2','data',2),('linear-1','linear',1),('linear-2','linear',2),
    ('cctv-dome','dome',1),('cctv-bullet','bullet',1),('panel','panel',1)]
manifest = {'revision':1, 'license':'CC0-1.0 — original VED generated geometry',
    'coordinateConvention':'metres; glTF X right, Y up, +Z wall front; luminaires face -Y',
    'assets':{}}
for key, kind, count in variants:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    if kind in ('outlet','switch','data'):
        plate(kind, count)
    elif kind == 'linear':
        luminaire(count)
    elif kind in ('dome','bullet'):
        camera(kind)
    else:
        box('Steel enclosure', (.4, .14, .6), (0, 0, 0), steel, .005)
        box('Recessed door', (.37, .008, .56), (0, .075, 0), plastic, .003)
        box('Latch', (.012, .01, .05), (.145, .083, 0), dark)
    if kind != 'linear':
        rotation = Matrix.Rotation(math.pi, 4, 'Z')
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                obj.matrix_world = rotation @ obj.matrix_world
    bpy.context.view_layer.update()
    corners = [obj.matrix_world @ Vector(corner)
        for obj in bpy.context.scene.objects if obj.type == 'MESH'
        for corner in obj.bound_box]
    dimensions = [max(p[i] for p in corners)-min(p[i] for p in corners) for i in range(3)]
    # Merge by material: three draw calls at most, shared original geometry.
    for mat in (plastic, dark, steel):
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
        matching = [o for o in meshes if o.data.materials[0] == mat]
        if not matching:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for obj in matching:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = matching[0]
        bpy.ops.object.join()
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / f'{key}.blend'))
    bpy.ops.export_scene.gltf(filepath=str(OUT / f'{key}.glb'), export_format='GLB', export_yup=True,
        export_cameras=False, export_lights=False, export_extras=True)
    size = (OUT / f'{key}.glb').stat().st_size
    if size > 250_000:
        raise ValueError(f'{key} exceeds asset budget: {size}')
    manifest['assets'][key] = {'url':f'/studio-devices/v1/{key}.glb','status':'representative',
        'nominalDimensionsMetres':{'x':round(dimensions[0],6),'y':round(dimensions[2],6),'z':round(dimensions[1],6)},
        'dimensions':'Illustrative only; renderer fits the existing device envelope',
        'referenceSources':[],
        'connectionAnchorPolicy':'Use canonical devicePlacement terminals, never infer terminals from the mesh',
        'anchor':'Existing devicePlacement anchor; no geometry or terminal mutation',
        'bytes':size,'materialSlots':3,'textures':0,'source':'Original Blender construction: scripts/author_studio_devices.py',
        'referenceStatus':'Family representation only; not an exact manufacturer-certified model'}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('VED_ASSETS_COMPLETE', len(manifest['assets']))
