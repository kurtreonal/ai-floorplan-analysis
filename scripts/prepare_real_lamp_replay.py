"""Append inspected real-layout lamps to the complete existing development head.

No template inference, new architecture, dropped classes, or unlabeled negatives.
All scaled/jittered views remain dependent training examples from one project.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
import yaml

from prepare_authored_legend_extension import digest
from prepare_authorized_pdf_detection import source_boxes, validate_training_sources


def transformed_labels(targets, scale, left, top):
    labels, ids = [], []
    for target in targets:
        a, b, c, d = [v * scale for v in target['source_box']]
        if left <= a < c <= left + 256 and top <= b < d <= top + 256:
            labels.append(f"{target['class_id']} {(a+c-2*left)/512:.8f} {(b+d-2*top)/512:.8f} {(c-a)/256:.8f} {(d-b)/256:.8f}")
            ids.append(target['record_id'])
    return labels, ids


def replay_plan(parent, class_ids, minimum):
    """Oversampling exact train windows, never new independent observations."""
    if not 1 <= minimum <= 200 or not class_ids or len(class_ids)>8:
        raise ValueError('Replay sampling exceeds experiment bounds')
    pools={i:[] for i in class_ids}
    for label in sorted((parent/'labels/train').glob('*.txt')):
        values={int(row.split()[0]) for row in label.read_text().splitlines() if row.strip()}
        for class_id in class_ids:
            if class_id in values:pools[class_id].append(label.stem)
    plan=[]
    for class_id,names in pools.items():
        if not names:raise ValueError('Replay cannot invent missing class examples')
        for index in range(max(0,minimum-len(names))):
            plan.append({'image_id':f'restored-replay-{class_id}-{index:03d}',
                         'sampling_parent':names[index%len(names)],'class_id':class_id,
                         'independent_example':False,'split':'train'})
    return plan


def balance_replay(parent, checkpoint, output, *, class_ids=(21,51,62,71), minimum=200):
    parent,checkpoint,output=map(Path,(parent,checkpoint,output))
    if output.exists():raise FileExistsError('Dataset revisions are immutable')
    data=json.loads((parent/'manifest.json').read_text())
    validate_training_sources(parent,data)
    if len(data['classes'])!=80 or data.get('diagnostic_only'):
        raise ValueError('Restorative replay preserves the full eighty-class experiment')
    plan=replay_plan(parent,class_ids,minimum)
    shutil.copytree(parent,output,ignore=shutil.ignore_patterns('*.cache'))
    for row in plan:
        for folder,suffix,key in (('images/train','png','image_sha256'),('labels/train','txt','label_sha256')):
            original=parent/folder/f"{row['sampling_parent']}.{suffix}"
            destination=output/folder/f"{row['image_id']}.{suffix}"
            if destination.exists():raise ValueError('Replay identity already exists')
            shutil.copy2(original,destination)
            row[key]=digest(destination)
            if digest(original)!=row[key]:raise ValueError('Replay copy differs')
    data['restorative_replay_sampling']={'parent_manifest_sha256':digest(parent/'manifest.json'),
        'class_ids':list(class_ids),'minimum_train_windows':minimum,'replicas':plan,
        'independent_examples_added':0,'reason':'Restore observed same-source rare-class regressions; not new annotations'}
    data['base_model_sha256']=digest(checkpoint)
    data['warnings'].append('Restorative train-window sampling retains original labels and project splits; copies do not supply independent evidence.')
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    config=yaml.safe_load((parent/'data.yaml').read_text());config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    validate_training_sources(output,data)
    return {'replicas':len(plan),'classes':80,'manifest_sha256':digest(output/'manifest.json')}


def prepare(parent, prepared, inspection, checkpoint, output):
    parent, prepared, inspection, checkpoint, output = map(Path, (parent, prepared, inspection, checkpoint, output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    if inspection.stat().st_size > 1_048_576:
        raise ValueError('Inspection exceeds bound')
    inspected = json.loads(inspection.read_text())
    source = json.loads((prepared / 'manifest.json').read_text())
    original = json.loads((parent / 'manifest.json').read_text())
    validate_training_sources(parent, original)
    if (inspected['schema'] != 'ved-delegated-layout-lamp-boxes-v1'
            or inspected['source_sha256'] != source['source_sha256']
            or inspected['prepared_manifest_sha256'] != digest(prepared/'manifest.json')
            or inspected['human_review_claim'] is not False or inspected['production_approval'] is not False
            or inspected['missing_annotation_policy'] != 'ignore_unreviewed_not_empty_background'
            or not inspected['user_statement'] or len(inspected['targets']) != 20
            or len(original['classes']) != 80 or original.get('diagnostic_only')
            or original.get('all_eligible_entries') is not True):
        raise ValueError('Exact authorized inspection and full parent head required')
    if digest(prepared/'original.pdf') != source['source_sha256']:
        raise ValueError('Original changed')
    permission_path = prepared/'source-authorization.json'
    permission = json.loads(permission_path.read_text())
    if (digest(permission_path) != source['authorization_sha256']
            or permission.get('source_sha256') != source['source_sha256']
            or 'training' not in permission.get('allowed_purposes', [])
            or inspected['project_group_id'] != source['project_group_id']):
        raise ValueError('Training permission or project grouping differs')
    region = next(r for r in source['regions'] if r['region_id'] == inspected['layout_region_id'])
    page = next(p for p in source['pages'] if p['page_number'] == inspected['page_number'])
    if digest(prepared/page['filename']) != page['image_sha256'] or digest(prepared/region['filename']) != region['crop_sha256']:
        raise ValueError('Source pixels changed')
    scale = page['pdf_points_to_image'][0]
    authorization = {**inspected, 'schema':'ved-user-authorized-development-label-preparation-v1',
        'local_development_training':True, 'delegated_assistant_annotation':True, 'targets':[]}
    for target in inspected['targets']:
        box = target['bbox_layout_pixels']
        x, y, right, bottom = region['bbox_source_pixels']
        if (len(box) != 4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                or not 0 <= box[0] < box[2] <= right-x or not 0 <= box[1] < box[3] <= bottom-y):
            raise ValueError('Target outside inspected layout')
        authorization['targets'].append({'id':target['id'], 'region_id':target['region_id'],
            'page_number':inspected['page_number'],
            'bbox_pdf_top_left_points':[(box[0]+x)/scale, (box[1]+y)/scale,
                                       (box[2]+x)/scale, (box[3]+y)/scale]})
    mapping = {}
    for class_id, identity in ((56,'L02'), (57,'L07')):
        row = original['classes'][class_id]
        expected = f"pdf-{source['source_sha256'][:12]}:p{page['page_number']}:{identity}"
        if row['id'] != class_id or row['legend_entry'] != expected:
            raise ValueError('Lamp class identity changed')
        mapping[identity] = {'class_id':class_id, 'legend_entry':expected}
    definitions = {r['region_id']:r for r in source['regions'] if r['region_id'] in mapping}
    targets = source_boxes(authorization, {page['page_number']:page}, definitions, mapping)
    if {class_id:sum(t['class_id']==class_id for t in targets) for class_id in (56,57)} != {56:16,57:4}:
        raise ValueError('Expected inspected coverage of both lamp subtypes')
    if {t['record_id'] for t in targets} & {t['record_id'] for t in original['authorized_pdf_targets']}:
        raise ValueError('Duplicate source records')
    output.mkdir(parents=True)
    for folder in ('images','labels'):
        shutil.copytree(parent/folder, output/folder)
    for record in original['additional_training_authorizations']:
        shutil.copy2(parent/record['filename'], output/record['filename'])
    authorization_name = 'deped-real-lamp-authorization.json'
    (output/authorization_name).write_text(json.dumps(authorization,indent=2))
    shutil.copy2(inspection, output/'deped-lamp-inspection.json')
    result = deepcopy(original)
    result.update({'base_model_sha256':digest(checkpoint), 'parent_dataset_sha256':digest(parent/'manifest.json'),
        'lamp_source_targets':targets, 'lamp_view_augmentation':{
            'scales':[.4,.6,.8,1.0], 'source_jitter_pixels':[-24,24],
            'rotation':'none; preserve authored subtype digits', 'independent_examples':False}})
    result['additional_training_authorizations'].append({'filename':authorization_name,
        'sha256':digest(output/authorization_name), 'source_sha256':source['source_sha256'],
        'prepared_manifest_sha256':digest(prepared/'manifest.json')})
    result['authorized_pdf_targets'].extend(targets)
    generated = []
    with Image.open(prepared/page['filename']) as opened:
        if opened.size != (page['width'],page['height']) or opened.width*opened.height > 60_000_000:
            raise ValueError('Source allocation exceeds bounds')
        image = opened.convert('RGB')
    pen = ImageDraw.Draw(image)
    # Inspect exact boxes/crops before training. Never alter stored source pixels.
    montage = Image.new('RGB',(5*170,4*140),'white')
    for index,target in enumerate(targets):
        a,b,c,d = target['source_box']
        crop = image.crop((max(0,a-18),max(0,b-18),c+18,d+18))
        crop.thumbnail((150,105))
        x,y = (index%5)*170,(index//5)*140
        montage.paste(crop,(x,y)); crop.close()
        ImageDraw.Draw(montage).text((x,y+110),f"{target['record_id']} class {target['class_id']}",fill='black')
    montage.save(output/'target-contact.png'); montage.close()
    for view_scale in result['lamp_view_augmentation']['scales']:
        view = image.resize((round(image.width*view_scale),round(image.height*view_scale)),Image.Resampling.LANCZOS)
        for target in targets:
            a,b,c,d = target['source_box']
            for offset,jitter in enumerate((-24,24)):
                left,top = round(((a+c)/2+jitter)*view_scale-128),round((b+d)/2*view_scale-128)
                if not 0 <= left < left+256 <= view.width or not 0 <= top < top+256 <= view.height:
                    raise ValueError('Training crop outside source')
                labels,ids = transformed_labels(targets,view_scale,left,top)
                if target['record_id'] not in ids:
                    raise ValueError('Training crop clips intended symbol')
                name = f"pdfdev-{target['record_id']}-s{round(view_scale*100):03d}-j{offset}"
                ip,lp = output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
                tile = view.crop((left,top,left+256,top+256)); tile.save(ip); tile.close()
                lp.write_text('\n'.join(labels)+'\n')
                record = {'image_id':name,'source_sha256':source['source_sha256'],
                    'source_image_sha256':page['image_sha256'],'tile_origin':[left,top],
                    'isotropic_view_scale':view_scale,'image_sha256':digest(ip),'label_sha256':digest(lp),
                    'annotation_origin':target['annotation_origin'],'human_review_claim':False,
                    'supervised_record_ids':ids,'primary_class_id':target['class_id'],'independent_example':False}
                generated.append(record); result['authorized_pdf_training_images'].append(record)
        view.close()
    for target in targets:
        pen.rectangle(target['source_box'],outline='green',width=3)
    image.save(output/'target-overlay.png'); image.close()
    # Balance scarce single-lamp views without pretending copies are new sources.
    single = [r for r in generated if r['primary_class_id'] == 57]
    for i in range(80-len(single)):
        parent_row = single[i%len(single)]; name = parent_row['image_id']+f'-repeat-{i:02d}'
        for folder,suffix in (('images/train','png'),('labels/train','txt')):
            shutil.copy2(output/folder/f"{parent_row['image_id']}.{suffix}",output/folder/f'{name}.{suffix}')
        result['authorized_pdf_training_images'].append({**parent_row,'image_id':name,'sampling_parent':parent_row['image_id']})
        result['sampling_replicas'].append({'image_id':name,'class_id':57,'independent_example':False})
    for class_id in (56,57):
        result['classes'][class_id]['samples'] += sum(t['class_id']==class_id for t in targets)
    result['warnings'].append('20 assistant-inspected real DepED lamps, 160 dependent scaled/context views and 48 scarce single-lamp replicas. These are not independent projects, full annotation completeness, or calibrated accuracy.')
    (output/'manifest.json').write_text(json.dumps(result,indent=2))
    config = yaml.safe_load((parent/'data.yaml').read_text()); config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    validate_training_sources(output,result)
    return {'classes':80,'real_lamp_targets':len(targets),'dependent_augmented_views':len(generated),
        'scarce_class_replicas':48,'manifest_sha256':digest(output/'manifest.json')}


def inspected_upload_targets(evidence, data, width, height):
    targets=[]
    for row in evidence['targets']:
        box=row['box']; cls=row['class_id']; name=row['id']
        if (type(cls) is not int or cls not in (56,57) or len(box)!=4
                or any(type(v) is not int for v in box)
                or not isinstance(name,str) or not name.replace('-','').isalnum()
                or not 0<=box[0]<box[2]<=width or not 0<=box[1]<box[3]<=height):
            raise ValueError('Invalid uploaded lamp label, identity or box')
        targets.append({'record_id':name,'class_id':cls,'source_box':box,
            'source_sha256':evidence['source_sha256'],'parent_pdf_sha256':evidence['parent_source_sha256'],
            'legend_entry':data['classes'][cls]['legend_entry'],'project_group_id':evidence['project_group_id'],
            'human_review_claim':False,'annotation_origin':evidence['annotation_origin'],'split':'train'})
    if (len({t['record_id'] for t in targets})!=20
            or {i:sum(t['class_id']==i for t in targets) for i in (56,57)}!={56:16,57:4}):
        raise ValueError('Duplicate targets or subtype coverage mismatch')
    return targets


def append_upload(parent, source, inspection, checkpoint, output):
    parent,source,inspection,checkpoint,output=map(Path,(parent,source,inspection,checkpoint,output))
    if output.exists():
        raise FileExistsError('Dataset revisions are immutable')
    if source.stat().st_size > 25*1024*1024 or inspection.stat().st_size > 1_048_576:
        raise ValueError('Upload or inspection exceeds bounds')
    evidence=json.loads(inspection.read_text()); data=json.loads((parent/'manifest.json').read_text())
    validate_training_sources(parent,data)
    if (evidence['schema']!='ved-delegated-derivative-lamp-boxes-v1'
            or digest(source)!=evidence['source_sha256'] or len(evidence['targets'])!=20
            or evidence['parent_source_sha256']!=data['authored_source_sha256']
            or evidence['project_group_id']!=data['lamp_source_targets'][0]['project_group_id']
            or evidence['human_review_claim'] is not False or evidence['production_approval'] is not False
            or evidence['missing_annotation_policy']!='ignore_unreviewed_not_empty_background'
            or not evidence['user_statement'] or len(data['classes'])!=80 or data.get('diagnostic_only')
            or data.get('lamp_upload_targets')):
        raise ValueError('Exact source, related-project identity and delegated permission required')
    with Image.open(source) as opened:
        if max(opened.size)>10_000 or opened.width*opened.height>60_000_000:
            raise ValueError('Upload allocation exceeds bounds')
        image=opened.convert('RGB')
    targets=inspected_upload_targets(evidence,data,image.width,image.height)
    output.mkdir(parents=True)
    for folder in ('images','labels'): shutil.copytree(parent/folder,output/folder)
    for row in data['additional_training_authorizations']:shutil.copy2(parent/row['filename'],output/row['filename'])
    preparation={'schema':'ved-authorized-image-preparation-v1','source_sha256':evidence['source_sha256'],
        'image_size':list(image.size),'annotation_revision_sha256':digest(inspection),
        'project_group_id':evidence['project_group_id'],'parent_pdf_sha256':evidence['parent_source_sha256']}
    (output/'upload-preparation.json').write_text(json.dumps(preparation,indent=2))
    shutil.copy2(inspection,output/'upload-inspection.json');shutil.copy2(source,output/'original-upload.png')
    authorization={**evidence,'schema':'ved-user-authorized-development-label-preparation-v1',
        'prepared_manifest_sha256':digest(output/'upload-preparation.json'),
        'local_development_training':True,'delegated_assistant_annotation':True}
    filename='deped-upload-source-authorization.json'
    (output/filename).write_text(json.dumps(authorization,indent=2))
    data['additional_training_authorizations'].append({'filename':filename,'sha256':digest(output/filename),
        'source_sha256':evidence['source_sha256'],'prepared_manifest_sha256':digest(output/'upload-preparation.json')})
    data.update({'base_model_sha256':digest(checkpoint),'parent_dataset_sha256':digest(parent/'manifest.json'),
                 'lamp_upload_targets':targets,'upload_sampling_policy':{'56':128,'57':256,'independent_examples':False}})
    montage=Image.new('RGB',(5*150,4*100),'white')
    for index,t in enumerate(targets):
        a,b,c,d=t['source_box'];crop=image.crop((max(0,a-8),max(0,b-8),min(image.width,c+8),min(image.height,d+8)))
        crop=crop.resize((crop.width*2,crop.height*2),Image.Resampling.NEAREST)
        x,y=(index%5)*150,(index//5)*100;montage.paste(crop,(x,y));crop.close()
        ImageDraw.Draw(montage).text((x,y+85),f"{t['record_id']} {t['class_id']}",fill='black')
    montage.save(output/'upload-target-contact.png');montage.close()
    for cls,count in ((56,128),(57,256)):
        members=[t for t in targets if t['class_id']==cls]
        for index in range(count):
            target=members[index%len(members)];a,b,c,d=target['source_box']
            jitter=(-24,0,24)[(index//len(members))%3]
            left=max(0,min(image.width-256,round((a+c)/2-128+jitter)))
            top=max(0,min(image.height-256,round((b+d)/2-128)))
            labels,ids=transformed_labels(targets,1,left,top)
            if target['record_id'] not in ids:raise ValueError('Intended uploaded symbol clipped')
            name=f"pdfdev-{target['record_id']}-view-{index:03d}"
            ip,lp=output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
            tile=image.crop((left,top,left+256,top+256));tile.save(ip);tile.close();lp.write_text('\n'.join(labels)+'\n')
            data['authorized_pdf_training_images'].append({'image_id':name,'source_sha256':evidence['source_sha256'],
                'source_image_sha256':evidence['source_sha256'],'tile_origin':[left,top],
                'image_sha256':digest(ip),'label_sha256':digest(lp),'supervised_record_ids':ids,
                'human_review_claim':False,'annotation_origin':target['annotation_origin'],'independent_example':False})
            data['sampling_replicas'].append({'image_id':name,'class_id':cls,'independent_example':False})
    image.close()
    for cls in (56,57):data['classes'][cls]['samples']+=sum(t['class_id']==cls for t in targets)
    data['warnings'].append('Exact low-resolution upload: 20 dependent derivative targets; 128/256 repeated context views. Same project as PDF; unknown regions remain ignored; no independent accuracy.')
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    config=yaml.safe_load((parent/'data.yaml').read_text());config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    validate_training_sources(output,data)
    return {'classes':80,'derivative_targets':20,'context_sampling_views':384,
            'manifest_sha256':digest(output/'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent','prepared','inspection','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.parent,args.prepared,args.inspection,args.checkpoint,args.output)))
