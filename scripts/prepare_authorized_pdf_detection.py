"""Append delegated development annotations without claiming independent review."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import shutil
import unicodedata

from PIL import Image
from prepare_authored_legend_extension import digest, extend_head, synthetic_tile
from probe_symbol_detector_dev import validate_model_classes


def validate_authorization(path, source_hash, preparation_hash):
    if Path(path).stat().st_size > 1_048_576:
        raise ValueError('Authorization exceeds bound')
    auth = json.loads(Path(path).read_text(encoding='utf-8'))
    if (auth.get('schema') != 'ved-user-authorized-development-label-preparation-v1'
            or auth.get('source_sha256') != source_hash
            or auth.get('prepared_manifest_sha256') != preparation_hash
            or auth.get('local_development_training') is not True
            or auth.get('delegated_assistant_annotation') is not True
            or auth.get('human_review_claim') is not False
            or auth.get('production_approval') is not False
            or not auth.get('user_statement')
            or auth.get('missing_annotation_policy') != 'ignore_unreviewed_not_empty_background'):
        raise ValueError('Exact development authorization required')
    return auth


def validate_training_sources(dataset, data):
    """Extra sources require hash-bound copied authorization; old runs unchanged."""
    allowed = {data.get('authored_source_sha256')}
    for record in data.get('additional_training_authorizations', []):
        name = record['filename']
        if Path(name).name != name or digest(dataset/name) != record['sha256']:
            raise ValueError('Additional source authorization changed')
        validate_authorization(dataset/name, record['source_sha256'], record['prepared_manifest_sha256'])
        allowed.add(record['source_sha256'])
    for row in data.get('authorized_pdf_training_images', []):
        name = row['image_id']
        if (Path(name).name != name or not name.startswith('pdfdev-')
                or row.get('human_review_claim') is not False
                or row.get('annotation_origin') != 'assistant_visual_under_user_development_authorization'
                or row['source_sha256'] not in allowed
                or digest(dataset/'images/train'/f'{name}.png') != row['image_sha256']
                or digest(dataset/'labels/train'/f'{name}.txt') != row['label_sha256']):
            raise ValueError('Delegated real-page training artifact changed')
    for row in data.get('assistant_reviewed_background_regions', []):
        name=row['image_id']
        if (Path(name).name!=name or not name.startswith('reviewed-negative-pdfdev-')
                or row.get('human_review_claim') is not False
                or row.get('annotation_origin')!='assistant_visual_under_user_development_authorization'
                or row.get('source_sha256') not in allowed
                or digest(dataset/'images/train'/f'{name}.png')!=row['sha256']
                or (dataset/'labels/train'/f'{name}.txt').read_text().strip()
                or row not in data['reviewed_background_images']):
            raise ValueError('Delegated background evidence changed')
    return allowed


def source_boxes(auth, pages, regions, mapping):
    targets, identities = [], set()
    if not 1 <= len(auth['targets']) <= 200:
        raise ValueError('Real-target bound exceeded')
    for row in auth['targets']:
        name, number, box = row['id'], row['page_number'], row['bbox_pdf_top_left_points']
        if (not isinstance(name, str) or not name.replace('-', '').isalnum()
                or name in identities or type(number) is not int or number not in pages
                or row['region_id'] not in mapping or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)):
            raise ValueError('Invalid source target identity')
        page = pages[number]
        scale = page['pdf_points_to_image'][0]
        if page['pdf_points_to_image'] != [scale,0,0,0,scale,0] or scale <= 0:
            raise ValueError('Unsupported preparation transform')
        pixels = [math.floor(box[0]*scale), math.floor(box[1]*scale),
                  math.ceil(box[2]*scale), math.ceil(box[3]*scale)]
        if not 0 <= pixels[0] < pixels[2] <= page['width'] or not 0 <= pixels[1] < pixels[3] <= page['height']:
            raise ValueError('Target outside source page')
        if max(pixels[2]-pixels[0],pixels[3]-pixels[1]) > 190:
            raise ValueError('Target exceeds detail-window bound')
        identities.add(name)
        region = regions[row['region_id']]
        targets.append({'record_id':name,'sheet_id':f"pdf-{auth['source_sha256'][:12]}-p{number}",
            'page_number':number,'source_sha256':page['image_sha256'],
            'pdf_sha256':auth['source_sha256'],'legend_entry':mapping[row['region_id']]['legend_entry'],
            'class_id':mapping[row['region_id']]['class_id'],'source_box':pixels,
            'label':region['proposed_label'],'annotation_origin':'assistant_visual_under_user_development_authorization',
            'human_review_claim':False,'split':'train','project_group_id':auth['project_group_id']})
    return targets


def build(parent, prepared, authorization, checkpoint, output):
    parent, prepared, checkpoint, output = map(Path,(parent,prepared,checkpoint,output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    data = json.loads((parent/'manifest.json').read_text())
    source = json.loads((prepared/'manifest.json').read_text())
    auth = validate_authorization(authorization,source['source_sha256'],digest(prepared/'manifest.json'))
    if (digest(prepared/'original.pdf') != source['source_sha256']
            or not data.get('all_eligible_entries') or len(data['classes']) != 60
            or data.get('required_loss') != 'positive_boxes_and_explicit_reviewed_background'):
        raise ValueError('Expected authorized source and full 60-class parent replay')
    pages = {p['page_number']:p for p in source['pages']}
    regions = {r['region_id']:r for r in source['regions'] if r['region_id'].startswith('L')}
    if len(regions) != 24 or any(digest(prepared/r['filename']) != r['crop_sha256'] for r in regions.values()):
        raise ValueError('Expected intact 24-entry source legend')
    if any(digest(prepared/p['filename']) != p['image_sha256'] for p in pages.values()):
        raise ValueError('Prepared source page changed')
    # Only exact authored meaning supports sharing: preserve separate source IDs.
    equivalents = {'L02':56,'L14':58}
    additions, mapping = [], {}
    for name, region in sorted(regions.items()):
        if region.get('annotation_layer') == 'wiring':
            continue
        identity = f"pdf-{source['source_sha256'][:12]}:p{region['page_number']}:{name}"
        if name in equivalents:
            class_id = equivalents[name]
            if region['proposed_label'] != data['classes'][class_id]['label']:
                raise ValueError('Proposed equivalent meaning differs')
        else:
            class_id = 60+len(additions)
            seed = 4 if name=='L12' else 35 if name=='L17' else 0
            additions.append({'label':region['proposed_label'],'seed_parent_class_id':seed})
        mapping[name] = {'class_id':class_id,'legend_entry':identity,'source_reference_examples':1,
                         'reviewed_real_examples':0,'assistant_real_examples':0,'synthetic_examples':8}
    targets = source_boxes(auth,pages,regions,mapping)
    from ultralytics import YOLO
    model = YOLO(str(checkpoint))
    validate_model_classes(model,data['classes'])
    extend_head(model.model,additions)
    model.ckpt['ema'] = None
    model.ckpt['optimizer'] = None
    output.mkdir(parents=True)
    shutil.copytree(parent/'images',output/'images')
    shutil.copytree(parent/'labels',output/'labels')
    model.save(output/'initialized-head.pt')
    shutil.copy2(authorization,output/'development-source-authorization.json')
    result = deepcopy(data)
    result.update({'class_scope':'parent60_plus_twenty_pdf_source_definitions',
        'parent_dataset_sha256':digest(parent/'manifest.json'),'parent_checkpoint_sha256':digest(checkpoint),
        'base_model_sha256':digest(output/'initialized-head.pt'),'production_approval':False,
        'additional_training_authorizations':[{'filename':'development-source-authorization.json',
            'sha256':digest(authorization),'source_sha256':source['source_sha256'],
            'prepared_manifest_sha256':digest(prepared/'manifest.json')}],
        'authorized_pdf_training_images':[],'authorized_pdf_targets':targets,
        'pdf_source_legend_mappings':mapping,'pdf_wiring_entries_excluded_from_devices':['L10','L11']})
    for i,row in enumerate(additions):
        identity = next(m['legend_entry'] for m in mapping.values() if m['class_id']==60+i)
        result['classes'].append({'id':60+i,'label':row['label'],'legend_entry':identity,
                                 'samples':8,'source_reference_examples':1,'real_page_reviewed_targets':0})
    rng = random.Random(20261004)
    for name,row in mapping.items():
        with Image.open(prepared/regions[name]['filename']) as opened:
            glyph = opened.convert('RGB')
        for index in range(8):
            # Keep letter glyphs upright; isotropic scale/context only, no flip.
            image,box = synthetic_tile(glyph,index%4,rng)
            stem = f"authored-legend-pdf76-{row['class_id']}-{index:02d}"
            ip,lp = output/'images/train'/f'{stem}.png',output/'labels/train'/f'{stem}.txt'
            image.save(ip); image.close()
            x1,y1,x2,y2 = box
            lp.write_text(f"{row['class_id']} {(x1+x2)/512:.8f} {(y1+y2)/512:.8f} {(x2-x1)/256:.8f} {(y2-y1)/256:.8f}\n")
            result['authored_legend_synthetic_images'].append({'image_id':stem,'class_id':row['class_id'],
                'legend_entry':row['legend_entry'],'box':box,'image_sha256':digest(ip),'label_sha256':digest(lp),
                'label_origin':'known_synthetic_composite_geometry','human_review_claim':False,
                'source_sha256':source['source_sha256'],'split':'train'})
        glyph.close()
    # Full context, positive-only supervision: unknown areas remain loss-masked.
    for number,page in pages.items():
        members = [t for t in targets if t['page_number']==number]
        if not members:
            continue
        with Image.open(prepared/page['filename']) as opened:
            image = opened.convert('RGB')
        for target in members:
            x1,y1,x2,y2 = target['source_box']
            left,top = round((x1+x2)/2-128),round((y1+y2)/2-128)
            neighbors = [t for t in members if left<=t['source_box'][0]<t['source_box'][2]<=left+256
                         and top<=t['source_box'][1]<t['source_box'][3]<=top+256]
            stem = 'pdfdev-'+target['record_id']
            ip,lp = output/'images/train'/f'{stem}.png',output/'labels/train'/f'{stem}.txt'
            tile=image.crop((left,top,left+256,top+256)); tile.save(ip); tile.close()
            lines=[]
            for n in neighbors:
                a,b,c,d=n['source_box']
                lines.append(f"{n['class_id']} {(a+c-2*left)/512:.8f} {(b+d-2*top)/512:.8f} {(c-a)/256:.8f} {(d-b)/256:.8f}")
            lp.write_text('\n'.join(lines)+'\n')
            result['authorized_pdf_training_images'].append({'image_id':stem,'source_sha256':source['source_sha256'],
                'source_image_sha256':page['image_sha256'],'tile_origin':[left,top],
                'image_sha256':digest(ip),'label_sha256':digest(lp),'human_review_claim':False,
                'annotation_origin':target['annotation_origin'],'supervised_record_ids':[n['record_id'] for n in neighbors]})
        image.close()
    for name,row in mapping.items():
        row['assistant_real_examples']=sum(t['legend_entry']==row['legend_entry'] for t in targets)
    result['warnings'].append('Additional real labels are assistant-prepared under explicit development authorization; no independent human box review or generalization claim. Reference-only classes are not demonstrated real detections.')
    (output/'manifest.json').write_text(json.dumps(result,indent=2))
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in result['classes']:
            label=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    validate_training_sources(output,result)
    return {'model_classes':len(result['classes']),'real_targets':len(targets),
        'new_synthetic_targets':176,'legend_mappings':len(mapping),'production_approval':False,
        'manifest_sha256':digest(output/'manifest.json')}


def learning_check(dataset, checkpoint, output):
    """Small real-positive memorization check; keep the complete numeric head."""
    dataset,checkpoint,output=map(Path,(dataset,checkpoint,output))
    if output.exists():raise FileExistsError('Learning checks are immutable')
    data=json.loads((dataset/'manifest.json').read_text())
    validate_training_sources(dataset,data)
    if len(data.get('authorized_pdf_training_images',[]))!=35:
        raise ValueError('Expected bounded inspected real-positive subset')
    output.mkdir(parents=True)
    for folder in ('images/train','labels/train'):(output/folder).mkdir(parents=True)
    for row in data['authorized_pdf_training_images']:
        for folder,suffix in (('images/train','png'),('labels/train','txt')):
            name=f"{row['image_id']}.{suffix}"
            shutil.copy2(dataset/folder/name,output/folder/name)
    for row in data['additional_training_authorizations']:
        shutil.copy2(dataset/row['filename'],output/row['filename'])
    data.update({'diagnostic_only':True,'all_eligible_entries':False,
        'base_model_sha256':digest(checkpoint),'authored_legend_synthetic_images':[],
        'reviewed_background_images':[],'reviewed_targets':[],'images':[],
        'scope':'35 delegated real targets; memorization only; never activate',
        'parent_dataset_sha256':digest(dataset/'manifest.json')})
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    import yaml
    config=yaml.safe_load((dataset/'data.yaml').read_text())
    config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    return {'diagnostic_only':True,'images':35,'numeric_head_classes':len(data['classes'])}


def replay_after_check(dataset, prepared, checkpoint, output):
    """Full replay with explicit scarce-class sampling and inspected negatives."""
    dataset,prepared,checkpoint,output=map(Path,(dataset,prepared,checkpoint,output))
    if output.exists():raise FileExistsError('Replay revisions are immutable')
    data=json.loads((dataset/'manifest.json').read_text())
    validate_training_sources(dataset,data)
    source=json.loads((prepared/'manifest.json').read_text())
    if (data.get('diagnostic_only') or len(data['classes'])!=80
            or digest(prepared/'manifest.json')!=data['additional_training_authorizations'][0]['prepared_manifest_sha256']):
        raise ValueError('Expected complete authorized 80-class source replay')
    output.mkdir(parents=True)
    for folder in ('images','labels'):shutil.copytree(dataset/folder,output/folder)
    for row in data['additional_training_authorizations']:shutil.copy2(dataset/row['filename'],output/row['filename'])
    data.update({'base_model_sha256':digest(checkpoint),'parent_dataset_sha256':digest(dataset/'manifest.json'),
                 'sampling_replicas':[],'assistant_reviewed_background_regions':[]})
    original=list(data['authorized_pdf_training_images'])
    by_id={r['record_id']:r for r in data['authorized_pdf_targets']}
    for cls in sorted({r['class_id'] for r in by_id.values()}):
        rows=[r for r in original if by_id[r['image_id'][7:]]['class_id']==cls]
        for index in range(max(0,24-len(rows))):
            parent=rows[index%len(rows)];name=f"{parent['image_id']}-repeat-{index:02d}"
            for folder,suffix in (('images/train','png'),('labels/train','txt')):
                shutil.copy2(dataset/folder/f"{parent['image_id']}.{suffix}",output/folder/f'{name}.{suffix}')
            data['authorized_pdf_training_images'].append({**parent,'image_id':name,'sampling_parent':parent['image_id']})
            data['sampling_replicas'].append({'image_id':name,'class_id':cls,'independent_example':False})
    page=next(p for p in source['pages'] if p['page_number']==3)
    scale=page['pdf_points_to_image'][0]
    path=prepared/page['filename']
    if digest(path)!=page['image_sha256']:raise ValueError('Background source changed')
    centers=[(x,172,'grid-number') for x in [661,788,916,1043,1171,1299,1426,1554,1682]]
    centers += [(x,234,'architectural-column') for x in [661,788,916,1043,1171,1299,1426,1554,1682]]
    # These are source-inspected regions, not wholesale negatives from empty sheets.
    with Image.open(path) as opened:image=opened.convert('RGB')
    for index,(x,y,meaning) in enumerate(centers):
        left,top=round(x*scale-128),round(y*scale-128)
        box=[left,top,left+256,top+256]
        if not 0<=left<left+256<=image.width or not 0<=top<top+256<=image.height:
            raise ValueError('Negative allocation outside source')
        if any(max(box[0],t['source_box'][0])<min(box[2],t['source_box'][2])
               and max(box[1],t['source_box'][1])<min(box[3],t['source_box'][3])
               for t in data['authorized_pdf_targets']):
            raise ValueError('Negative region intersects a known symbol')
        name=f'reviewed-negative-pdfdev-{index:02d}'
        ip,lp=output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
        crop=image.crop(box);crop.save(ip);crop.close();lp.write_text('')
        record={'image_id':name,'sha256':digest(ip),'source_sha256':source['source_sha256'],
            'source_image_sha256':page['image_sha256'],'source_box':box,'page_number':3,
            'annotation_origin':'assistant_visual_under_user_development_authorization','human_review_claim':False,
            'evidence':meaning+'; visually inspected in original page and diagnostic overlay',
            'independent_example':False,'split':'train'}
        data['reviewed_background_images'].append(record)
        data['assistant_reviewed_background_regions'].append(record)
    image.close()
    data['warnings'].append('Sampling replicas and assistant-inspected background regions are delegated development evidence, not independent human approval or additional projects.')
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    import yaml
    config=yaml.safe_load((dataset/'data.yaml').read_text());config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    return {'replicas':len(data['sampling_replicas']),'assistant_negative_regions':len(centers),'model_classes':80}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','prepared','authorization','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.parent,args.prepared,args.authorization,args.checkpoint,args.output)))
