"""Bounded all-class replay; unchanged real labels, construction-known references.

This is a development experiment, not a release or an independent evaluation.
Public agency source pixels are not admitted by this preparation.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import shutil
import unicodedata

from PIL import Image, ImageDraw, ImageFont
from prepare_pec_reference import digest, PARENT_DATASET_SHA256, PARENT_CHECKPOINT_SHA256
from prepare_authorized_pdf_detection import validate_training_sources
from reconcile_pec_reference_catalog import read_json

REFERENCE_DATASET_SHA256='efbf156f928ed5d3c9a80fe629b65edb10f751edd3d8f5ca77a34214f1c96881'
SCOPE='all_class_reference_replay_development_not_release'


def recover_byte_evidence(parent,recovery_manifest,source_root,output):
    """Verify historical crops against original pixels and original source labels.

    Records only technical reconstruction; never manufactures human approval.
    The running replay dataset is not changed by this audit.
    """
    parent,recovery_manifest,source_root,output=map(Path,(parent,recovery_manifest,source_root,output))
    if output.exists():raise FileExistsError('Recovered byte audits are immutable')
    if digest(parent/'manifest.json')!=PARENT_DATASET_SHA256:raise ValueError('Exact authorized parent required')
    data=read_json(parent/'manifest.json')
    if digest(recovery_manifest)!=data['recovery_manifest_sha256']:raise ValueError('Original recovery history changed')
    recovery=read_json(recovery_manifest);records={r['id']:r for r in recovery['records']}
    if len(records)!=len(recovery['records']):raise ValueError('Duplicate recovery identity')
    classes={r['legend_entry']:r['id'] for r in data['classes']}
    verified=[]
    for row in data['images']:
        if row.get('image_sha256') and row.get('label_sha256'):continue
        name=row['record_id']
        if not name.startswith('recovered-') or row.get('recovered_placement') is not True:
            raise ValueError('Unknown unhashed inherited record')
        target=records[name.removeprefix('recovered-')];sheet=row['sheet_id'];box=row['source_crop']
        if (Path(sheet).name!=sheet or sheet in ('sheet-51','sheet-52') or target.get('split')!='train'
                or not 1<=int(target.get('group',0))<=22 or row['source_box']!=target['bbox']
                or row['source_sha256']!=target['source_sha256'] or sheet!=target['sheet_id']
                or row['legend_entry']!=target['legend_entry'] or row['class_id']!=classes[row['legend_entry']]
                or len(box)!=4 or any(type(v) is not int for v in box)
                or box[2]-box[0]!=256 or box[3]-box[1]!=256):
            raise ValueError('Recovery source, split or geometry differs')
        original=source_root/f'{sheet}.jpg'
        if (original.is_symlink() or original.stat().st_size>25_000_000
                or digest(original)!=row['source_sha256']):raise ValueError('Original recovered source changed')
        with Image.open(original) as opened:
            if (opened.width*opened.height>60_000_000 or max(opened.size)>10000
                    or not 0<=box[0]<box[2]<=opened.width or not 0<=box[1]<box[3]<=opened.height):
                raise ValueError('Recovered crop exceeds original bounds')
            pixels=opened.convert('RGB').crop(box)
        ip=parent/'images/train'/f'{name}.png';lp=parent/'labels/train'/f'{name}.txt'
        with Image.open(ip) as stored:
            if stored.size!=pixels.size or stored.convert('RGB').tobytes()!=pixels.tobytes():
                raise ValueError('Stored crop differs from exact original pixels')
        pixels.close();x,y,_,_=box
        expected=[]
        for neighbor in recovery['records']:
            if (neighbor['source_sha256']==row['source_sha256'] and neighbor['legend_entry'] in classes
                    and x<=neighbor['bbox'][0]<neighbor['bbox'][2]<=x+256
                    and y<=neighbor['bbox'][1]<neighbor['bbox'][3]<=y+256):
                a,b,c,d=neighbor['bbox']
                expected.append([classes[neighbor['legend_entry']],(a+c-2*x)/512,(b+d-2*y)/512,(c-a)/256,(d-b)/256])
        actual=[[float(v) for v in line.split()] for line in lp.read_text().splitlines() if line.strip()]
        if len(actual)!=len(expected) or any(len(a)!=5 or any(abs(v-e)>1e-8 for v,e in zip(a,b)) for a,b in zip(actual,expected)):
            raise ValueError('Stored labels differ from exact historical source records')
        label_classes(lp,80)
        verified.append({'image_id':name,'image_sha256':digest(ip),'label_sha256':digest(lp),
                         'source_sha256':row['source_sha256'],'source_crop':box,
                         'original_metadata':deepcopy(row),'verification':'exact_original_RGB_pixels_and_historical_source_labels'})
    report={'kind':'historical_recovery_byte_reconstruction_audit','parent_manifest_sha256':PARENT_DATASET_SHA256,
            'recovery_manifest_sha256':digest(recovery_manifest),'verified_records':verified,
            'human_review_claim':False,'production_approval':False,'originals_modified':False}
    with output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    return {'verified_historical_windows':len(verified),'audit_sha256':digest(output),'originals_modified':False}


def label_classes(path,count):
    result=set()
    for line in path.read_text().splitlines():
        values=line.split()
        if len(values)!=5:raise ValueError('Malformed inherited label')
        cls=int(values[0]);box=[float(v) for v in values[1:]]
        if (str(cls)!=values[0] or not 0<=cls<count or any(not math.isfinite(v) for v in box)
                or not 0<box[2]<=1 or not 0<box[3]<=1
                or not 0<=box[0]-box[2]/2<=box[0]+box[2]/2<=1.00000001
                or not 0<=box[1]-box[3]/2<=box[1]+box[3]/2<=1.00000001):
            raise ValueError('Invalid inherited class or normalized box')
        result.add(cls)
    return result


def inventory(parent,data,*,missing_hash_exclusions=None,class_count=80):
    if type(class_count) is not int or class_count not in (80,129):
        raise ValueError('Unsupported frozen replay namespace')
    rows={}
    for kind,key in (('real','images'),('pdf','authorized_pdf_training_images'),
                     ('synthetic','authored_legend_synthetic_images'),('background','reviewed_background_images')):
        for row in data.get(key,[]):
            name=row.get('image_id',row.get('record_id'))
            if not isinstance(name,str) or Path(name).name!=name or name in rows:
                raise ValueError('Duplicate or unsafe inherited training identity')
            ip=parent/'images/train'/f'{name}.png';lp=parent/'labels/train'/f'{name}.txt'
            expected=row.get('image_sha256',row.get('sha256'))
            if expected is None or kind!='background' and not row.get('label_sha256'):
                if missing_hash_exclusions is None:
                    raise ValueError('Inherited record lacks image/label byte evidence')
                missing_hash_exclusions.append({'image_id':name,'reason':'historical_record_missing_byte_hashes',
                                                'original_metadata':deepcopy(row)})
                continue
            if digest(ip)!=expected or row.get('label_sha256') and digest(lp)!=row['label_sha256']:
                raise ValueError('Inherited image/label bytes changed')
            classes=label_classes(lp,class_count)
            if (kind=='background')!= (not classes):
                raise ValueError('Background and positive supervision conflict')
            rows[name]={'kind':kind,'metadata':row,'classes':classes,
                        'image_sha256':expected,'label_sha256':digest(lp)}
    return rows


def select_replay(rows,*,real_per_class=8,synthetic_per_class=4,background_count=32):
    if (type(real_per_class) is not int or not 4<=real_per_class<=16
            or synthetic_per_class!=4 or not 0<=background_count<=64):
        raise ValueError('Replay sampling exceeds local experiment bound')
    chosen=set()
    for cls in range(80):
        for kinds,limit in (({'real','pdf'},real_per_class),({'synthetic'},synthetic_per_class)):
            pool=[name for name,row in rows.items() if row['kind'] in kinds and cls in row['classes']]
            # Stable hash-order spans phases/projects, not only first filenames.
            pool.sort(key=lambda n:rows[n]['image_sha256'])
            chosen.update(pool[:limit])
    negatives=sorted((n for n,r in rows.items() if r['kind']=='background'),key=lambda n:rows[n]['image_sha256'])
    chosen.update(negatives[:background_count])
    covered=set().union(*(rows[n]['classes'] for n in chosen))
    if covered!=set(range(80)):raise ValueError('Every original class requires retained supervision')
    if sum(rows[n]['kind']=='synthetic' for n in chosen)+248>512:
        raise ValueError('Known composite count exceeds unchanged training bound')
    return chosen


def reference_context(image,box,index):
    """Add authored text/table distractors without touching the labeled glyph."""
    if image.size!=(256,256) or len(box)!=4 or not 0<=box[0]<box[2]<=256 or not 0<=box[1]<box[3]<=256:
        raise ValueError('Invalid construction-known composite')
    result=image.convert('RGB');pen=ImageDraw.Draw(result);font=ImageFont.load_default()
    texts=['APPENDIX A','DESCRIPTION','ELECTRICAL SYMBOLS','Circuit No.','LIGHTING LAYOUT']
    rng=random.Random(20261006+index)
    for y in (8,42,78,116,156,196,230):
        text=texts[rng.randrange(len(texts))];x=rng.randrange(4,90)
        bounds=pen.textbbox((x,y),text,font=font)
        if bounds[2]<box[0]-4 or bounds[0]>box[2]+4 or bounds[3]<box[1]-4 or bounds[1]>box[3]+4:
            pen.text((x,y),text,font=font,fill='black')
    for y in (32,96,164,224):
        if y<box[1]-4 or y>box[3]+4:pen.line((4,y,252,y),fill='black',width=1)
    return result


def prepare(parent,references,checkpoint,output,*,real_per_class=8):
    parent,references,checkpoint,output=map(Path,(parent,references,checkpoint,output))
    if output.exists():raise FileExistsError('Replay revisions are immutable')
    if (digest(parent/'manifest.json')!=PARENT_DATASET_SHA256
            or digest(references/'manifest.json')!=REFERENCE_DATASET_SHA256
            or digest(checkpoint)!=PARENT_CHECKPOINT_SHA256):
        raise ValueError('Exact unchanged parent/reference revisions required')
    old=read_json(parent/'manifest.json');ref=read_json(references/'manifest.json')
    if (old.get('required_loss')!='positive_boxes_and_explicit_reviewed_background'
            or not old.get('all_eligible_entries') or old.get('diagnostic_only')
            or len(old['classes'])!=80 or len(ref['classes'])!=129
            or [(r['id'],r['label']) for r in old['classes']]!=[(r['id'],r['label']) for r in ref['classes'][:80]]
            or len(ref['reference_specification']['point_mappings'])!=54):
        raise ValueError('Keep every original and requested class identity')
    validate_training_sources(parent,old);validate_training_sources(references,ref)
    excluded=[]
    rows=inventory(parent,old,missing_hash_exclusions=excluded);chosen=select_replay(rows,real_per_class=real_per_class)
    new_rows=ref['authored_legend_synthetic_images']
    if len(new_rows)!=248:raise ValueError('All requested reference variants required')
    for row in new_rows:
        name=row['image_id'];ip=references/'images/train'/f'{name}.png';lp=references/'labels/train'/f'{name}.txt'
        if (Path(name).name!=name or name in rows or digest(ip)!=row['image_sha256']
                or digest(lp)!=row['label_sha256'] or label_classes(lp,129)!={row['class_id']}):
            raise ValueError('Reference label or source identity changed')
    head=references/'initialized-head.pt'
    if digest(head)!=ref['base_model_sha256']:raise ValueError('Unchanged expanded parent initialization required')
    # All selected inherited bytes verified before materializing a new revision.
    output.mkdir(parents=True);(output/'images/train').mkdir(parents=True);(output/'labels/train').mkdir(parents=True)
    shutil.copy2(head,output/'initialized-head.pt')
    for name in sorted(chosen):
        for folder,suffix in (('images/train','png'),('labels/train','txt')):
            shutil.copy2(parent/folder/f'{name}.{suffix}',output/folder/f'{name}.{suffix}')
    data=deepcopy(old)
    for key in ('images','authorized_pdf_training_images','authored_legend_synthetic_images',
                'reviewed_background_images','assistant_reviewed_background_regions'):
        data[key]=[r for r in old.get(key,[]) if r.get('image_id',r.get('record_id')) in chosen]
    data.pop('restorative_replay_sampling',None)
    data['classes']=deepcopy(ref['classes'])
    data['reference_specification']=deepcopy(ref['reference_specification'])
    data['reference_registry_sha256']=ref['reference_registry_sha256']
    data['additional_training_authorizations']=deepcopy(old['additional_training_authorizations'])+deepcopy(ref['additional_training_authorizations'])
    for source,source_data in ((parent,old),(references,ref)):
        for authority in source_data['additional_training_authorizations']:
            target=output/authority['filename']
            if target.exists() and digest(target)!=authority['sha256']:raise ValueError('Conflicting source authorization')
            shutil.copy2(source/authority['filename'],target)
    for index,row in enumerate(new_rows):
        revised=deepcopy(row);prior=row['image_id'];name=prior.replace('authored-legend-pec-','authored-legend-pec-context-')
        ip=output/'images/train'/f'{name}.png';lp=output/'labels/train'/f'{name}.txt'
        with Image.open(references/'images/train'/f'{prior}.png') as opened:context=reference_context(opened,row['box'],index)
        context.save(ip);context.close();shutil.copy2(references/'labels/train'/f'{prior}.txt',lp)
        revised.update(image_id=name,image_sha256=digest(ip),label_sha256=digest(lp),
                       parent_image_id=prior,parent_image_sha256=row['image_sha256'],
                       augmentation='unchanged glyph/box plus construction-known text and table context')
        data['authored_legend_synthetic_images'].append(revised)
    counts=Counter()
    for path in (output/'labels/train').glob('*.txt'):counts.update(label_classes(path,129))
    if set(counts)!=set(range(129)):raise ValueError('Replay omitted a class')
    for row in data['classes']:row['samples']=counts[row['id']]
    data.update(scope=SCOPE,diagnostic_only=True,all_eligible_entries=True,
                base_model_sha256=digest(output/'initialized-head.pt'),
                parent_dataset_sha256=PARENT_DATASET_SHA256,parent_checkpoint_sha256=PARENT_CHECKPOINT_SHA256,
                reference_parent_dataset_sha256=REFERENCE_DATASET_SHA256,
                synthetic_complete_background=True,production_approval=False,
                replay_sampling={'real_windows_per_class_limit':real_per_class,'synthetic_windows_per_old_class_limit':4,
                    'selected_original_windows':len(chosen),'reference_context_windows':248,
                    'selection':'deterministic image SHA256 order; all 80 old identities and all 54 references',
                    'independent_examples_added':0,'original_labels_changed':False,
                    'excluded_inherited_records':excluded})
    data['warnings'].append('Bounded 129-class replay, not a release: 49 added source-reference meanings lack real-layout positives. Complete synthetic context is authored; real unreviewed regions remain ignored. Training resubstitution is not independent evaluation.')
    payload=json.dumps(data,indent=2)
    if len(payload.encode())>5_000_000:raise ValueError('Replay manifest exceeds unchanged artifact bound')
    (output/'manifest.json').write_text(payload,encoding='utf-8')
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            name=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(name)}\n")
    validate_training_sources(output,data)
    return {'head_classes':129,'original_classes_retained':80,'requested_reference_meanings':54,
            'train_windows':len(list((output/'images/train').glob('*.png'))),
            'synthetic_windows':len(data['authored_legend_synthetic_images']),
            'historical_windows_excluded_for_missing_hashes':len(excluded),
            'supervised_class_ids':len(counts),'manifest_sha256':digest(output/'manifest.json')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('parent','references','checkpoint','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--real-per-class',type=int,default=8)
    args=parser.parse_args()
    print(json.dumps(prepare(args.parent,args.references,args.checkpoint,args.output,real_per_class=args.real_per_class)))
