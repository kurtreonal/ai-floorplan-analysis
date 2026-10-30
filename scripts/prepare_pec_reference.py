"""Extract the owner's requested reference entries, not real-page detections.

The supplied scan lacks an edition/title/copyright page. Its PEC attribution
is user-supplied, not independently certified. Generic reference glyphs never
silently replace rated, mounted or drawing-specific model classes.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random

import numpy as np

from PIL import Image, ImageDraw
from prepare_pdf_training_source import prepare

SOURCE_SHA256 = '8fa0851445cbe840c59af1b59042369aec4dc78eef8401f10e18ca22736f3af3'
PREVIEW_SCALE = 1.6
PREPARED_SHA256 = '3cdbe5e0a9453cc7fe3ff213d8a9bc7c3d98ac4e0098895c8e5061c4fab2e5f7'
CLEANED_SHA256 = '44d16ab12d86bf12b0900b33caff5a6021483456b807fa0090a68336cbc50240'
PARENT_DATASET_SHA256 = '11ef819e20b120ea1bb44e08a64822f820f2f575c7c76212d5043f2b6249f527'
PARENT_CHECKPOINT_SHA256 = '867c7fb399104bf91caff1d6aad859504cc923443cb3e02fcb2b00255b2affa2'


def digest(path):
    with Path(path).open('rb') as stream:
        import hashlib
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def clean_glyph(image, *, variant='as_shown', wiring=False):
    """Crop known table separators, not glyph strokes; keep source coordinates.

    Ceiling/wall columns in this pinned scan have a middle table divider. Only
    edge-spanning separators are removed. Wiring reference lines are never
    cleaned this way: their long strokes are the intended reference content.
    """
    if max(image.size) > 512 or min(image.size) < 4:
        raise ValueError('Reference glyph allocation differs')
    if wiring:
        return image.copy(), [0,0,image.width,image.height]
    left, top, right, bottom = 0, 0, image.width, image.height
    ink = np.asarray(image.convert('L')) < 180
    table_ink = np.asarray(image.convert('L')) < 240
    if not wiring:
        if variant in {'ceiling', 'wall'}:
            middle = range(round(image.width*.4), round(image.width*.6))
            divider = [x for x in middle if ink[:, x].mean() >= .85]
            if not divider:
                raise ValueError('Expected ceiling/wall table divider')
            if variant == 'ceiling': right = min(divider)-2
            else: left = max(divider)+3
        # Only edge rules of this pinned table are eligible for cleanup. The
        # lighter threshold catches their gray antialias fringe; glyph strokes
        # and the wall-mount stub inside a variant are not edited.
        edge_rows = [y for y in range(image.height)
                     if table_ink[y].mean() >= .4 and (y < 3 or y >= image.height*.85)]
        if edge_rows:
            lower = [y for y in edge_rows if y >= image.height*.85]
            upper = [y for y in edge_rows if y < 3]
            if lower:
                bottom = min(lower)
                # Include the adjacent antialiased fringe of the same rule.
                while bottom > image.height*.85 and table_ink[bottom-1].mean() >= .25:
                    bottom -= 1
            if upper: top = max(upper)+1
        edge_columns = [x for x in range(image.width)
                        if table_ink[:, x].mean() >= .8 and (x < 3 or x >= image.width-3)]
        for x in edge_columns:
            if x < 3: left = max(left, x+1)
            else: right = min(right, x)
    if right-left < 4 or bottom-top < 4:
        raise ValueError('Table cleanup consumed the glyph')
    kept = ink[top:bottom, left:right]
    if not kept.any():
        raise ValueError('Empty reference glyph')
    # Crop whitespace, retain a padding ring, never resize/rotate source glyphs.
    ys, xs = np.where(kept)
    box = [max(left, left+int(xs.min())-2), max(top, top+int(ys.min())-2),
           min(right, left+int(xs.max())+3), min(bottom, top+int(ys.max())+3)]
    return image.crop(box), box


def existing_class_mapping(reference_id, classes):
    """Only five evidence-supported meanings; no subtype/rating guesses."""
    supported = {'1.23': 'Pull box', '1.26': 'Circuit home-run notation',
                 '1.27': 'Push button', '1.36.2': 'Fire alarm control panel',
                 '1.36.5': 'Smoke detector'}
    label = supported.get(reference_id)
    if label is None:
        return []
    return [row['id'] for row in classes if row['label'].casefold() == label.casefold()]


def clean_reference(prepared, parent_manifest, output):
    """Immutable, source-bound reference registry; no project catalog mutation."""
    prepared, parent_manifest, output = map(Path, (prepared, parent_manifest, output))
    if output.exists():
        raise FileExistsError('Reference cleanup revisions are immutable')
    if (digest(prepared/'manifest.json') != PREPARED_SHA256
            or digest(prepared/'original.pdf') != SOURCE_SHA256):
        raise ValueError('Expected the pinned supplied-reference preparation')
    source = json.loads((prepared/'manifest.json').read_text())
    authorization = json.loads((prepared/'source-authorization.json').read_text())
    if (source['source_sha256'] != SOURCE_SHA256
            or digest(prepared/'source-authorization.json') != source['authorization_sha256']
            or authorization.get('source_sha256') != SOURCE_SHA256
            or authorization.get('scope') != 'local_development_only'
            or authorization.get('allowed_purposes') != ['reference_grounding','training']
            or authorization.get('human_review_claim') is not False
            or authorization.get('production_approval') is not False):
        raise ValueError('Exact reference development permission required')
    if parent_manifest.stat().st_size > 5_000_000:
        raise ValueError('Parent class manifest exceeds bound')
    parent = json.loads(parent_manifest.read_text())
    classes = parent['classes']
    if ({r['id'] for r in classes} != set(range(len(classes)))
            or any(type(r['id']) is not int for r in classes)):
        raise ValueError('Parent numeric classes differ')
    expected = {row['reference_id']:row for row in entries()}
    if len(source['regions']) != 66 or {r['reference_id'] for r in source['regions']} != set(expected):
        raise ValueError('Requested reference coverage differs')
    pages = {p['page_number']:p for p in source['pages']}
    for page in pages.values():
        if (page['pdf_page_rotation_degrees'] != 0
                or page['coordinate_frame'] != 'rendered_page_top_left_points'
                or Path(page['filename']).name != page['filename']
                or digest(prepared/page['filename']) != page['image_sha256']):
            raise ValueError('Prepared source page changed')
    glyphs = []
    try:
        # Validate and process every region before creating any output revision.
        for row in source['regions']:
            if (any(row[k] != value for k,value in expected[row['reference_id']].items())
                    or Path(row['filename']).name != row['filename']
                    or digest(prepared/row['filename']) != row['crop_sha256']
                    or row['source_image_sha256'] != pages[row['page_number']]['image_sha256']
                    or row['source_page_id'] != f"{SOURCE_SHA256}:page:{row['page_number']}"):
                raise ValueError('Prepared reference identity or glyph changed')
            variants = row.get('authored_variants', ['as_shown'])
            # Drop cord has only an authored ceiling glyph, not an invented wall variant.
            if row['reference_id'] == '1.20.3': variants = ['ceiling']
            with Image.open(prepared/row['filename']) as raw:
                if raw.size != (row['bbox_source_pixels'][2]-row['bbox_source_pixels'][0],
                                row['bbox_source_pixels'][3]-row['bbox_source_pixels'][1]):
                    raise ValueError('Reference crop dimensions differ')
                for variant in variants:
                    clean, local = clean_glyph(raw, variant=variant,
                                              wiring=row['annotation_layer']=='wiring')
                    glyph_id = row['region_id']+'-'+variant
                    x,y = row['bbox_source_pixels'][:2]
                    aliases = existing_class_mapping(row['reference_id'],classes)
                    glyphs.append((clean, {'glyph_id':glyph_id, 'filename':glyph_id+'.png',
                        'reference_id':row['reference_id'], 'proposed_label':row['proposed_label'],
                        'variant':variant, 'annotation_layer':row['annotation_layer'],
                        'source_sha256':SOURCE_SHA256, 'source_page_id':row['source_page_id'],
                        'source_image_sha256':row['source_image_sha256'],
                        'parent_crop_sha256':row['crop_sha256'], 'bbox_parent_crop_pixels':local,
                        'bbox_source_pixels':[x+local[0],y+local[1],x+local[2],y+local[3]],
                        'mapped_model_class_ids':aliases,
                        'mapping_state':'assistant_semantic_match_existing_class' if aliases else 'unresolved_reference_only',
                        'human_review_claim':False, 'production_approval':False,
                        'independent_real_examples':0, 'real_layout_targets':0,
                        'training_eligible':False}))
        output.mkdir(parents=True)
        canvas = Image.new('RGB',(1100,((len(glyphs)+5)//6)*125),'white')
        pen = ImageDraw.Draw(canvas)
        for index,(image,row) in enumerate(glyphs):
            image.save(output/row['filename'])
            row['glyph_sha256'] = digest(output/row['filename'])
            thumb=image.copy(); thumb.thumbnail((170,88))
            x,y=(index%6)*183,(index//6)*125
            canvas.paste(thumb,(x,y+25)); thumb.close()
            pen.text((x+5,y+5),row['reference_id']+' '+row['variant'],fill='black')
        canvas.save(output/'contact.png'); canvas.close()
        result={'schema':'ved-cleaned-reference-registry-v1','source_sha256':SOURCE_SHA256,
            'prepared_manifest_sha256':PREPARED_SHA256, 'prepared_directory':str(prepared.resolve()),
            'parent_classes_manifest_sha256':digest(parent_manifest), 'references':[r for _,r in glyphs],
            'user_authorization_kind':'user_attested_source_permission',
            'scope':'local_reference_preparation_not_project_catalog_or_live_detector',
            'human_review_claim':False,'production_approval':False,'model_changed':False,
            'unmapped_point_reference_entries':sorted({r['reference_id'] for _,r in glyphs
                if r['annotation_layer']=='symbols' and not r['mapped_model_class_ids']}),
            'warnings':['Edition/compliance attribution not independently verified.',
                'Reference table crops are not independent floor-plan detection examples.',
                'All 12 wiring patterns retained separately, never point-device boxes.',
                'Generic lamps/outlets/switches do not imply rated or mounted drawing-specific classes.']}
        (output/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return {'glyph_variants':len(glyphs),'point_variants':sum(r['annotation_layer']=='symbols' for _,r in glyphs),
                'mapped_reference_entries':len({r['reference_id'] for _,r in glyphs if r['mapped_model_class_ids']}),
                'unmapped_point_reference_entries':len(result['unmapped_point_reference_entries']),
                'model_changed':False, 'manifest_sha256':digest(output/'manifest.json')}
    finally:
        for image,_ in glyphs: image.close()


def prepare_learning_check(cleaned, parent_manifest, checkpoint, output, *, examples=12):
    """Five matched references, unchanged 80-class head, never a release dataset."""
    from prepare_authored_legend_extension import synthetic_tile
    from probe_symbol_detector_dev import validate_model_classes
    from ultralytics import YOLO
    import unicodedata

    cleaned, parent_manifest, checkpoint, output = map(Path,(cleaned,parent_manifest,checkpoint,output))
    if output.exists():
        raise FileExistsError('Reference learning-check revisions are immutable')
    if type(examples) is not int or not 4 <= examples <= 16:
        raise ValueError('Reference diagnostic exceeds bounded sampling')
    if (digest(cleaned/'manifest.json') != CLEANED_SHA256
            or digest(parent_manifest) != PARENT_DATASET_SHA256
            or digest(checkpoint) != PARENT_CHECKPOINT_SHA256):
        raise ValueError('Reference registry, parent dataset or checkpoint changed')
    registry = json.loads((cleaned/'manifest.json').read_text())
    parent = json.loads(parent_manifest.read_text())
    prepared = Path(registry['prepared_directory'])
    if (digest(prepared/'manifest.json') != PREPARED_SHA256
            or digest(prepared/'original.pdf') != SOURCE_SHA256):
        raise ValueError('Reference source preparation changed')
    selected = [r for r in registry['references'] if r['mapped_model_class_ids']]
    if len(selected) != 5 or any(r['annotation_layer'] != 'symbols' for r in selected):
        raise ValueError('Expected five exact existing-class reference matches')
    for row in selected:
        if (Path(row['filename']).name != row['filename']
                or digest(cleaned/row['filename']) != row['glyph_sha256']
                or row['mapped_model_class_ids'] != existing_class_mapping(row['reference_id'],parent['classes'])
                or row['human_review_claim'] is not False or row['production_approval'] is not False):
            raise ValueError('Matched reference glyph or class identity changed')
    validate_model_classes(YOLO(str(checkpoint)),parent['classes'])
    # The parent's full numeric head stays intact. Identical-meaning aliases are
    # traceable, but not duplicated as contradictory boxes at the same location.
    output.mkdir(parents=True)
    (output/'images/train').mkdir(parents=True); (output/'labels/train').mkdir(parents=True)
    permission = json.loads((prepared/'source-authorization.json').read_text())
    authority={'schema':'ved-user-authorized-development-label-preparation-v1',
        'source_sha256':SOURCE_SHA256,'prepared_manifest_sha256':PREPARED_SHA256,
        'local_development_training':True,'delegated_assistant_annotation':True,
        'human_review_claim':False,'production_approval':False,
        'user_statement':permission['user_statement'], 'scope':'reference_derived_synthetic_diagnostic_only',
        'missing_annotation_policy':'ignore_unreviewed_not_empty_background',
        'project_group_id':permission['project_group_id'], 'targets':[],
        'rights_evidence':permission['rights_evidence']}
    (output/'reference-development-authorization.json').write_text(json.dumps(authority,indent=2),encoding='utf-8')
    data={'kind':'positive_only_masked_symbol_detection_diagnostic_v1',
        'diagnostic_only':True,'all_eligible_entries':False,'classes':deepcopy(parent['classes']),
        'class_agnostic':False,'base_model_sha256':digest(checkpoint),'parent_dataset_sha256':digest(parent_manifest),
        'required_loss':'synthetic_complete_known_composite_only', 'synthetic_complete_background':True,
        'reviewed_targets':[],'images':[],'reviewed_background_images':[],
        'authored_legend_synthetic_images':[], 'reference_registry_sha256':CLEANED_SHA256,
        'additional_training_authorizations':[{'filename':'reference-development-authorization.json',
            'sha256':digest(output/'reference-development-authorization.json'),
            'source_sha256':SOURCE_SHA256,'prepared_manifest_sha256':PREPARED_SHA256}],
        'reference_mappings':selected, 'production_approval':False,
        'unmapped_point_reference_entries':registry['unmapped_point_reference_entries'],
        'wiring_references_excluded_from_point_targets':12,
        'new_real_world_independent_examples':0,'new_real_page_reviewed_targets':0,
        'warnings':['Five-class internal pipeline check; not the requested universal detector deliverable.',
            'No held-out validation: val points to train for resubstitution diagnostics only.',
            'No current model/profile activation; full 80-class numeric head retained.']}
    randomizer=random.Random(20261005)
    for row in selected:
        class_id=min(row['mapped_model_class_ids'])
        with Image.open(cleaned/row['filename']) as raw:
            for index in range(examples):
                # Existing compositing seam, native orientation for text-bearing
                # glyphs; only isotropic scaling and known placements vary.
                image,box=synthetic_tile(raw,index%4,randomizer)
                name=f'authored-legend-pec-{class_id}-{index:03d}'
                image_path=output/'images/train'/f'{name}.png'; label_path=output/'labels/train'/f'{name}.txt'
                image.save(image_path);image.close()
                x1,y1,x2,y2=box
                label_path.write_text(f'{class_id} {(x1+x2)/512:.8f} {(y1+y2)/512:.8f} {(x2-x1)/256:.8f} {(y2-y1)/256:.8f}\n')
                data['authored_legend_synthetic_images'].append({'image_id':name,'class_id':class_id,
                    'legend_entry':f"reference-{SOURCE_SHA256[:12]}:{row['reference_id']}:{row['variant']}",
                    'reference_id':row['reference_id'],'glyph_sha256':row['glyph_sha256'],'box':box,
                    'image_sha256':digest(image_path),'label_sha256':digest(label_path),
                    'label_origin':'known_synthetic_composite_geometry','human_review_claim':False,
                    'source_sha256':SOURCE_SHA256,'source_reference_examples':1,'split':'train',
                    'augmentation':'native_orientation_isotropic_scale_known_composite_placement',
                    'independent_example':False})
    for row in data['classes']:
        row['samples']=sum(r['class_id']==row['id'] for r in data['authored_legend_synthetic_images'])
    (output/'manifest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            label=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    return {'synthetic_images':len(data['authored_legend_synthetic_images']),
            'diagnostic_classes':len(selected),'numeric_head_classes':len(data['classes']),
            'independent_examples':0,'manifest_sha256':digest(output/'manifest.json')}


def entries():
    rows = []
    def add(identity, label, page, box, layer='symbols'):
        rows.append({'reference_id': identity, 'region_id': 'R' + identity.replace('.', '_'),
                     'proposed_label': label, 'page_number': page,
                     'bbox_pdf_top_left_points': [v / PREVIEW_SCALE for v in box],
                     'annotation_layer': layer, 'example_kind': 'reference_table_not_real_layout',
                     'model_class_id': None, 'mapping_state': 'unresolved_do_not_auto_merge',
                     'human_review_claim': False, 'production_approval': False})
    for i, label, top, bottom in [(14,'Main Distribution Panelboard',1033,1079),
                                  (15,'Power Panelboard',1087,1123),
                                  (16,'Lighting Panelboard',1130,1171)]:
        add(f'1.{i}', label, 1, (419,top,538,bottom))
    labels = ['Incandescent Lamp','Vapor Discharge Lamp','Drop Cord Lamp','Exit Lamp',
              'Fluorescent Lamp','Lamp Outlet with Pull Switch','Outlet with Blank Cover',
              'Fan','Clock','Single Convenience','Duplex Convenience','Weatherproof Convenience',
              'Cooking Range','Convenience with Switch','Special Purpose (ACU, WH, D, R, etc.)',
              'Floor (P,T,I)','Antenna','Microphone','Telephone','Intercom']
    bounds = [(1380,1445),(189,230),(239,280),(289,331),(340,389),(399,444),
              (453,492),(501,539),(549,587),(597,632),(642,678),(688,725),
              (735,778),(788,829),(839,887),(898,949),(960,993),(1004,1038),
              (1049,1084),(1094,1129)]
    for i,(label,(top,bottom)) in enumerate(zip(labels,bounds),1):
        # The first nine authored rows have explicit ceiling/wall variants.
        box=(415,top,540,bottom) if i==1 else (965,top,1090,bottom)
        add(f'1.20.{i}', label, 1, box)
        rows[-1]['authored_variants'] = ['ceiling','wall'] if i<=9 and i!=3 else ['as_shown']
    labels = ['Single Pole','Duplex (2 single pole switches on one switch pole)',
              'Triplex (3 single pole switches on one switch pole)','Double Pole',
              'Three Pole','Three-Way','Four-Way','Automatic Door','Key Operated',
              'Master Selector','Remote Control']
    bounds=[(1167,1190),(1196,1239),(1245,1288),(1294,1316),(1322,1345),
            (1351,1374),(1380,1402),(1408,1428),(1434,1459),(149,174),(179,203)]
    for i,(label,(top,bottom)) in enumerate(zip(labels,bounds),1):
        add(f'1.21.{i}', label, 1 if i<=9 else 2,
            (985,top,1078,bottom) if i<=9 else (470,top,578,bottom))
    labels=['Junction Box','Pull Box','Riser Up','Riser Down',
            'Circuit Homerun (Number Indicates Circuit No.)','Push Button',
            'Buzzer (Indicate Voltage)','Bell (Indicate Voltage)','Horn','Amplifier',
            'Annunciator','Loudspeaker','Telephone Exchange','Telephone Terminal Cabinet']
    bounds=[(209,247),(257,296),(306,348),(358,399),(409,449),(459,512),
            (522,557),(567,617),(627,665),(675,710),(720,754),(764,812),
            (822,862),(872,913)]
    for i,(label,(top,bottom)) in enumerate(zip(labels,bounds),22):
        add(f'1.{i}',label,2,(475,top,585,bottom))
    labels=['Manual','Control Panel','Heat Detector','Flame Detector','Smoke Detector','Ionization Detector']
    bounds=[(950,995),(1001,1038),(1044,1090),(1096,1147),(1153,1203),(1209,1258)]
    for i,(label,(top,bottom)) in enumerate(zip(labels,bounds),1):
        add(f'1.36.{i}',label,2,(478,top,582,bottom))
    labels=['Conduit','Open Wiring','Underground','Emergency','Fire Alarm','Telephone',
            'Intercom','Bell System','TV Antenna','Closed Circuit Television','Music','Clock']
    bounds=[(1292,1309),(1319,1336),(1346,1363),(1374,1391),(1401,1418),(1428,1445),
            (169,188),(199,219),(228,245),(256,274),(283,304),(314,330)]
    for i,(label,(top,bottom)) in enumerate(zip(labels,bounds),1):
        add(f'1.37.{i}',label,2,(484,top,582,bottom) if i<=6 else (980,top,1126,bottom), 'wiring')
    if len(rows)!=66 or len({r['reference_id'] for r in rows})!=66:
        raise ValueError('Requested reference coverage differs')
    return rows


def build(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError('Reference revisions are immutable')
    if source.stat().st_size>25*1024*1024:
        raise ValueError('Supplied reference exceeds byte bound')
    if sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Supplied reference source changed')
    # Metadata sits beside the prepared child; neither prior sources nor flags
    # are changed. The owner requested use, not independent compliance approval.
    output.mkdir(parents=True)
    permission={'source_sha256':SOURCE_SHA256,
                'authorization_kind':'user_attested_source_permission',
                'user_statement':'2026-10-05: use this PEC dataset and take the specified legends as training dataset',
                'allowed_purposes':['reference_grounding','training'],
                'project_group_id':'reference-8fa0851445cb',
                'scope':'local_development_only', 'rights_evidence':'user_request_not_independent_license_verification',
                'production_approval':False, 'human_review_claim':False}
    for filename,value in [('permission.json',permission),('regions.json',entries())]:
        with (output/filename).open('x',encoding='utf-8') as stream:
            json.dump(value,stream,indent=2)
    result=prepare(source,output/'prepared',output/'permission.json',[1,2],dpi=200,
                   regions_path=output/'regions.json')
    # Contact sheet contains every extracted glyph for visible QA.
    canvas=Image.new('RGB',(1100,((66+5)//6)*125),'white')
    draw=ImageDraw.Draw(canvas)
    for i,row in enumerate(result['regions']):
        with Image.open(output/'prepared'/row['filename']) as raw:
            image=raw.convert('RGB'); image.thumbnail((170,88))
            x,y=(i%6)*183,(i//6)*125
            canvas.paste(image,(x,y+25))
            draw.text((x+5,y+5),row['reference_id'],fill='black')
            image.close()
    canvas.save(output/'reference-contact.png'); canvas.close()
    return {'entries':66,'point_reference_entries':54,'wiring_reference_entries':12,
            'real_layout_targets':0,'trained_model_changed':False,
            'prepared_manifest_sha256':sha256((output/'prepared/manifest.json').read_bytes()).hexdigest()}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('extract','clean','learning-check'),default='extract')
    parser.add_argument('--source',type=Path)
    parser.add_argument('--prepared',type=Path,help='Prepared source for clean; cleaned registry for learning-check')
    parser.add_argument('--parent-manifest',type=Path)
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--examples',type=int,default=12)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='extract':
        if args.source is None: parser.error('--source required for extract')
        result=build(args.source,args.output)
    else:
        if args.prepared is None or args.parent_manifest is None:
            parser.error('--prepared and --parent-manifest required')
        if args.mode=='clean': result=clean_reference(args.prepared,args.parent_manifest,args.output)
        else:
            if args.checkpoint is None: parser.error('--checkpoint required for learning-check')
            result=prepare_learning_check(args.prepared,args.parent_manifest,args.checkpoint,args.output,examples=args.examples)
    print(json.dumps(result))
