"""Add hash-bound real switch views to the existing complete development head.

Unknown drawing areas remain masked by the existing partial-label trainer.
Source legend aliases are retained; context/scale copies are not new projects.
"""
import argparse
import json
from pathlib import Path
import shutil

from PIL import Image
import yaml
from prepare_authored_legend_extension import digest
from prepare_authorized_pdf_detection import validate_training_sources
from prepare_real_lamp_replay import transformed_labels


SWITCH_LABELS = {62:'One gang device switch',63:'Two gang device switch',64:'Three gang device switch'}
ORIGIN = 'assistant_visual_under_user_development_authorization'


def checked_targets(evidence, classes, width, height):
    if (evidence.get('human_review_claim') is not False or evidence.get('production_approval') is not False
            or evidence.get('missing_annotation_policy') != 'ignore_unreviewed_not_empty_background'
            or evidence.get('annotation_origin') != ORIGIN or not evidence.get('user_statement')
            or not 1 <= len(evidence.get('targets',[])) <= 50):
        raise ValueError('Delegated development evidence required')
    targets=[];seen=set()
    for row in evidence['targets']:
        name,cls,box=row['id'],row['class_id'],row['box']
        if (not isinstance(name,str) or not name.replace('-','').isalnum() or name in seen
                or type(cls) is not int or cls not in SWITCH_LABELS
                or classes[cls]['id'] != cls or classes[cls]['label'] != SWITCH_LABELS[cls]
                or row.get('label') != SWITCH_LABELS[cls]
                or len(box)!=4 or any(type(v) is not int for v in box)
                or not 0<=box[0]<box[2]<=width or not 0<=box[1]<box[3]<=height
                or max(box[2]-box[0],box[3]-box[1])>190
                or not row.get('source_legend_entry') or not row.get('meaning_evidence')):
            raise ValueError('Invalid switch box, class identity or legend evidence')
        seen.add(name)
        targets.append({'record_id':name,'class_id':cls,'label':row['label'],'source_box':box,
            'source_sha256':evidence['source_image_sha256'],'legend_entry':classes[cls]['legend_entry'],
            'source_legend_entry':row['source_legend_entry'],'meaning_evidence':row['meaning_evidence'],
            'project_group_id':evidence['project_group_id'],'split':'train',
            'annotation_origin':ORIGIN,'human_review_claim':False,
            **({'pdf_sha256':evidence['source_sha256'],'page_number':evidence['page_number']}
               if evidence.get('page_number') else {'parent_pdf_sha256':evidence['parent_pdf_sha256']})})
    return targets


def context_views(image, targets, focus, scales):
    """Vary both grid phases; centered-only memorization does not prove tiling."""
    for scale in scales:
        if scale not in (.5,.75,1,1.5,2):raise ValueError('Unsupported isotropic view scale')
        view=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
        if min(view.size)<256:raise ValueError('View smaller than detail tile')
        for target in focus:
            a,b,c,d=target['source_box']
            for dx in (-80,0,80):
                for dy in (-80,0,80):
                    left=max(0,min(view.width-256,round((a+c)/2*scale-128+dx)))
                    top=max(0,min(view.height-256,round((b+d)/2*scale-128+dy)))
                    lines,ids=transformed_labels(targets,scale,left,top)
                    if target['record_id'] not in ids:continue
                    yield view.crop((left,top,left+256,top+256)),lines,ids,scale,[left,top],target
        view.close()


def prepare(parent, inspection, checkpoint, output):
    parent,inspection,checkpoint,output=map(Path,(parent,inspection,checkpoint,output))
    if output.exists():raise FileExistsError('Dataset revisions are immutable')
    if inspection.stat().st_size>1_048_576:raise ValueError('Inspection exceeds bound')
    data=json.loads((parent/'manifest.json').read_text());validate_training_sources(parent,data)
    if (len(data['classes'])!=80 or data.get('diagnostic_only')
            or not data.get('all_eligible_entries')
            or data.get('required_loss')!='positive_boxes_and_explicit_reviewed_background'):
        raise ValueError('Preserve complete masked 80-class parent')
    evidence=json.loads(inspection.read_text())
    if evidence['parent_manifest_sha256']!=digest(parent/'manifest.json'):
        raise ValueError('Inspection belongs to another dataset revision')
    sources=[]
    for entry in evidence['sources']:
        prepared=Path(entry['prepared']);source=json.loads((prepared/'manifest.json').read_text())
        if (digest(prepared/'manifest.json')!=entry['prepared_manifest_sha256']
                or source['source_sha256']!=entry['source_sha256']
                or source['project_group_id']!=entry['project_group_id']
                or digest(prepared/'original.pdf')!=entry['source_sha256']):
            raise ValueError('Prepared PDF source or grouping differs')
        page=next(p for p in source['pages'] if p['page_number']==entry['page_number'])
        if page['image_sha256']!=entry['source_image_sha256'] or digest(prepared/page['filename'])!=entry['source_image_sha256']:
            raise ValueError('Prepared page bytes differ')
        allowed=any(a['source_sha256']==entry['source_sha256']
                    and a['prepared_manifest_sha256']==entry['prepared_manifest_sha256']
                    for a in data['additional_training_authorizations'])
        if not allowed:raise ValueError('Existing development source permission missing')
        targets=checked_targets(entry,data['classes'],page['width'],page['height'])
        # The identical authored meanings support sharing, not visual resemblance.
        for target in targets:
            region_id=target['source_legend_entry'].split(':')[-1]
            region=next(r for r in source['regions'] if r['region_id']==region_id)
            if (region['proposed_label']!=target['label']
                    or digest(prepared/region['filename'])!=region['crop_sha256']
                    or target['source_legend_entry']!=f"pdf-{source['source_sha256'][:12]}:p{region['page_number']}:{region_id}"):
                raise ValueError('Source legend does not support class equivalence')
        sources.append((entry,prepared/page['filename'],targets,(.5,.75,1)))
    entry=evidence['upload'];path=parent/'original-upload.png'
    preparation=parent/'upload-preparation.json'
    if (digest(path)!=entry['source_sha256'] or entry['source_image_sha256']!=entry['source_sha256']
            or digest(preparation)!=entry['prepared_manifest_sha256']
            or entry['parent_pdf_sha256']!=data['authored_source_sha256']
            or entry['project_group_id']!=data['lamp_source_targets'][0]['project_group_id']):
        raise ValueError('Derivative source or related project differs')
    with Image.open(path) as image:targets=checked_targets(entry,data['classes'],*image.size)
    parent_pdf=next((e for e,p,ts,sc in sources if e['source_sha256']==entry['parent_pdf_sha256']),None)
    if parent_pdf is None:raise ValueError('Derivative legend evidence missing')
    supported={(t['class_id'],t['source_legend_entry'],t['label'])
               for e,p,ts,sc in sources if e is parent_pdf for t in ts}
    if any((t['class_id'],t['source_legend_entry'],t['label']) not in supported for t in targets):
        raise ValueError('Derivative class alias lacks source legend evidence')
    sources.append((entry,path,targets,(1,1.5,2)))
    # Exact existing source records are reused; never overwritten or double-counted.
    existing={t['record_id']:t for t in data['authorized_pdf_targets']}
    all_new=[t for e,p,ts,sc in sources for t in ts if t['record_id'] not in existing]
    if len({t['record_id'] for e,p,ts,sc in sources for t in ts})!=sum(len(ts) for e,p,ts,sc in sources):
        raise ValueError('Duplicate inspection record')
    for e,p,ts,sc in sources:
        for t in ts:
            if t['record_id'] in existing and any(existing[t['record_id']].get(k)!=t.get(k)
                for k in ('class_id','source_sha256','source_box','legend_entry','project_group_id')):
                raise ValueError('Existing annotation revision must not be overwritten')
    shutil.copytree(parent,output,ignore=shutil.ignore_patterns('*.cache'))
    shutil.copy2(inspection,output/'switch-inspection.json')
    data['base_model_sha256']=digest(checkpoint)
    data['parent_dataset_sha256']=digest(parent/'manifest.json')
    data['switch_source_targets']=[t for e,p,ts,sc in sources for t in ts]
    data['switch_view_sampling']={'grid_phase_offsets':[-80,0,80],'scale':'isotropic',
        'independent_examples':False,'rotation':'none; preserve lettering and subtype',
        'new_pdf_targets':sum('pdf_sha256' in t for t in all_new),
        'new_derivative_targets':sum('parent_pdf_sha256' in t for t in all_new)}
    data['authorized_pdf_targets'].extend(t for t in all_new if 'pdf_sha256' in t)
    for e,path,focus,scales in sources:
        auth={**e,'schema':'ved-user-authorized-development-label-preparation-v1',
              'local_development_training':True,'delegated_assistant_annotation':True}
        auth.pop('prepared',None)
        filename=f"switch-authorization-{e['source_sha256'][:12]}.json"
        (output/filename).write_text(json.dumps(auth,indent=2))
        data['additional_training_authorizations'].append({'filename':filename,'sha256':digest(output/filename),
            'source_sha256':e['source_sha256'],'prepared_manifest_sha256':e['prepared_manifest_sha256']})
        neighbors=[t for t in data['authorized_pdf_targets'] if t['source_sha256']==e['source_image_sha256']]
        if not e.get('page_number'):neighbors=data['lamp_upload_targets']+focus
        with Image.open(path) as opened:
            if opened.width*opened.height>60_000_000:raise ValueError('Source allocation exceeds bound')
            image=opened.convert('RGB')
        for index,(tile,lines,ids,scale,origin,target) in enumerate(context_views(image,neighbors,focus,scales)):
            name=f"pdfdev-switch-{e['source_sha256'][:12]}-{index:03d}"
            ip,lp=output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
            if ip.exists() or lp.exists():raise ValueError('Training view identity already exists')
            tile.save(ip);tile.close();lp.write_text('\n'.join(lines)+'\n')
            data['authorized_pdf_training_images'].append({'image_id':name,'source_sha256':e['source_sha256'],
                'source_image_sha256':e['source_image_sha256'],'image_sha256':digest(ip),'label_sha256':digest(lp),
                'tile_origin':origin,'isotropic_view_scale':scale,'primary_class_id':target['class_id'],
                'supervised_record_ids':ids,'human_review_claim':False,'annotation_origin':ORIGIN,
                'independent_example':False,'split':'train'})
        image.close()
    data['warnings'].append('Switch grid-phase replay: assistant source-box inspection; identical legend meanings retain source aliases. Related PDF/upload stay one project. Ambiguous Sf subtype excluded. No independent accuracy or production approval.')
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    config=yaml.safe_load((parent/'data.yaml').read_text());config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    validate_training_sources(output,data)
    return {'classes':80,'switch_targets':len(data['switch_source_targets']),
        'new_dependent_views':len(data['authorized_pdf_training_images'])-len(json.loads((parent/'manifest.json').read_text())['authorized_pdf_training_images']),
        'manifest_sha256':digest(output/'manifest.json')}


def restore_outlet_context(parent, checkpoint, output):
    """Protect observed outlet regressions without new boxes or changed labels."""
    parent,checkpoint,output=map(Path,(parent,checkpoint,output))
    if output.exists():raise FileExistsError('Dataset revisions are immutable')
    data=json.loads((parent/'manifest.json').read_text());validate_training_sources(parent,data)
    evidence=json.loads((parent/'switch-inspection.json').read_text())
    entry=next(e for e in evidence['sources'] if e['source_sha256'].startswith('76f411c60b6d'))
    prepared=Path(entry['prepared']);source=json.loads((prepared/'manifest.json').read_text())
    if digest(prepared/'manifest.json')!=entry['prepared_manifest_sha256']:raise ValueError('Prepared source changed')
    page=next(p for p in source['pages'] if p['page_number']==entry['page_number'])
    if digest(prepared/page['filename'])!=entry['source_image_sha256']:raise ValueError('Page changed')
    neighbors=[t for t in data['authorized_pdf_targets'] if t['source_sha256']==entry['source_image_sha256']]
    focus=[t for t in neighbors if t['class_id']==58]
    if len(focus)!=6 or len(data['classes'])!=80 or data.get('diagnostic_only'):
        raise ValueError('Exact six retained outlet targets and full head required')
    shutil.copytree(parent,output,ignore=shutil.ignore_patterns('*.cache'))
    with Image.open(prepared/page['filename']) as opened:image=opened.convert('RGB')
    generated=[]
    for index,(tile,lines,ids,scale,origin,target) in enumerate(context_views(image,neighbors,focus,(.5,.75,1))):
        name=f'pdfdev-retained-outlet-phase-{index:03d}'
        ip,lp=output/'images/train'/f'{name}.png',output/'labels/train'/f'{name}.txt'
        if ip.exists() or lp.exists():raise ValueError('View identity already exists')
        tile.save(ip);tile.close();lp.write_text('\n'.join(lines)+'\n')
        generated.append({'image_id':name,'source_sha256':entry['source_sha256'],
            'source_image_sha256':entry['source_image_sha256'],'image_sha256':digest(ip),'label_sha256':digest(lp),
            'tile_origin':origin,'isotropic_view_scale':scale,'primary_class_id':58,'supervised_record_ids':ids,
            'human_review_claim':False,'annotation_origin':ORIGIN,'independent_example':False,'split':'train'})
    image.close()
    data['authorized_pdf_training_images'].extend(generated)
    data['retained_outlet_context_replay']={'source_record_ids':[t['record_id'] for t in focus],
        'dependent_view_count':len(generated),'independent_examples_added':0,
        'reason':'Six existing outlets regressed after switch replay; retain exact labels, vary grid phase.'}
    data['base_model_sha256']=digest(checkpoint);data['parent_dataset_sha256']=digest(parent/'manifest.json')
    (output/'manifest.json').write_text(json.dumps(data,indent=2))
    config=yaml.safe_load((parent/'data.yaml').read_text());config['path']=output.resolve().as_posix()
    (output/'data.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
    validate_training_sources(output,data)
    return {'new_dependent_views':len(generated),'manifest_sha256':digest(output/'manifest.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','inspection','checkpoint','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.parent,args.inspection,args.checkpoint,args.output)))
