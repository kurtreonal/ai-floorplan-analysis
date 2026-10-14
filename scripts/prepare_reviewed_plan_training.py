"""Hash-bound local development positives from the latest saved review.

Unknown page areas are not negatives. Uncertain outlet subtypes carry allowed
legend identities, not invented normal/UPS labels. Geometry/legend samples and
deleted symbols remain provenance records, never installed-device targets.
"""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json,math,os,random,shutil,sys,unicodedata
from pathlib import Path

from PIL import Image

os.environ['YOLO_AUTOINSTALL']='false'
os.environ['YOLO_OFFLINE']='true'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def append_reviewed_head(model, additions):
    """Transfer initialization only; preserve every previous numeric identity."""
    import torch
    head=model.model[-1];old=len(model.names);new=old+len(additions)
    if type(head).__name__!='Detect' or getattr(head,'end2end',False):raise ValueError('Unsupported head')
    if set(model.names)!=set(range(old)):raise ValueError('Noncontiguous parent head')
    for branch in head.cv3:
        prior=branch[-1]
        if not isinstance(prior,torch.nn.Conv2d) or prior.out_channels!=old:raise ValueError('Unsupported class branch')
        layer=torch.nn.Conv2d(prior.in_channels,new,prior.kernel_size,stride=prior.stride,padding=prior.padding,
            bias=True,device=prior.weight.device,dtype=prior.weight.dtype)
        with torch.no_grad():
            layer.weight[:old].copy_(prior.weight);layer.bias[:old].copy_(prior.bias)
            for i,row in enumerate(additions):
                seed=row['seed_parent_class_id']
                if type(seed) is not int or not 0<=seed<old:raise ValueError('Unsupported transfer seed')
                layer.weight[old+i].copy_(prior.weight[seed]);layer.bias[old+i].copy_(prior.bias[seed]-2)
        branch[-1]=layer
    head.nc=new;head.no=new+head.reg_max*4;model.yaml['nc']=new
    model.names={**model.names,**{old+i:r['label'] for i,r in enumerate(additions)}}


def review_targets(session, catalog, sources, groups, classes, exclusions=(), uncertain=()):
    """Pure reconciliation: explicit scoped IDs; subtype ambiguity is retained."""
    by_identity={r['legend_entry']:r['id'] for r in classes}
    registry={r['legend_entry']:r for r in catalog}
    targets=[];decisions=[];sheets=[]
    for sheet in session['sheets']:
        if sheet.get('group') not in groups:continue
        if sheet.get('split') in ('test','sealed_test'):raise ValueError('Protected project split')
        path=sources.get(sheet['source_sha256'])
        if path is None:raise ValueError('Exact review source missing')
        with Image.open(path) as image:
            if image.size!=(sheet['width'],sheet['height']):raise ValueError('Review frame mismatch')
        project='review-group-'+str(sheet['group'])
        sheets.append(dict(sheet_id=sheet['id'],project_id=project,split='train',
            source_sha256=sheet['source_sha256'],original_source_sha256=sheet.get('original_source_sha256'),
            pdf_page=sheet.get('pdf_page'),
            source_width=sheet['width'],source_height=sheet['height'],source_path=str(path),
            coverage='reviewed_positive_records_only',geometry_training=False))
        for ann in sheet['annotations']:
            entry=ann.get('legend_entry');reason=None;allowed=[]
            if ann.get('layer')!='symbols':reason='not_installed_symbol_layer'
            elif ann.get('review_state')=='deleted':reason='deleted_preserved_not_negative'
            elif ann.get('review_state')!='user_reviewed':reason='not_user_reviewed'
            elif ann['id'] in exclusions:reason='provisional_technical_exclusion'
            elif entry in by_identity and entry in registry and ann['id'] not in uncertain:allowed=[by_identity[entry]]
            elif (ann['id'] in uncertain or ann.get('class_state')=='unmapped' and ann.get('review_state')=='user_reviewed'
                    and 'normal' in ann.get('label','').casefold() and 'ups' in ann.get('label','').casefold()):
                # Resolve the two actual drawing-scoped legend meanings. This
                # does not create a new generic electrical class or subtype.
                identities=[r['legend_entry'] for r in catalog if any(e.get('source_sheet_id')==sheet['id']
                    for e in r.get('examples',[])) and 'duplex convenience outlet' in r['label'].casefold()
                    and ('normal power' in r['label'].casefold() or 'ups power' in r['label'].casefold())]
                if len(identities)!=2 or any(i not in by_identity for i in identities):reason='unsupported_ambiguous_family'
                else:allowed=sorted(by_identity[i] for i in identities)
            else:reason='unmapped_legend_identity'
            box=ann.get('geometry',{}).get('coordinates',[])
            valid=(ann.get('geometry',{}).get('type')=='bbox' and len(box)==4
                and all(type(v) in (int,float) and math.isfinite(v) for v in box)
                and 0<=box[0]<box[2]<=sheet['width'] and 0<=box[1]<box[3]<=sheet['height'])
            if reason is None and not valid:reason='invalid_source_box'
            decisions.append(dict(sheet_id=sheet['id'],annotation_id=ann['id'],layer=ann.get('layer'),
                review_state=ann.get('review_state'),legend_entry=entry,reason=reason or 'included_reviewed_positive'))
            if reason is not None:continue
            targets.append(dict(record_id=sha256((sheet['id']+':'+ann['id']).encode()).hexdigest()[:24],
                annotation_id=ann['id'],sheet_id=sheet['id'],project_id=project,split='train',
                class_id=allowed[0],allowed_class_ids=allowed,legend_entry=entry,label=ann.get('label'),
                source_box=box,source_sha256=sheet['source_sha256'],review_state='user_reviewed',
                subtype_unresolved=len(allowed)>1,class_state=ann.get('class_state'),
                technical_subtype_uncertainty=ann['id'] in uncertain,
                human_review_claim=True,production_approval=False))
    if not targets or len(sheets)!=len(groups):raise ValueError('Missing selected reviewed project')
    return targets,decisions,sheets


def tile_rows(targets, origin, transform, size=256):
    sx,sy=transform;left,top=origin;rows=[]
    for target in targets:
        a,b,c,d=target['source_box'];box=[a*sx-left,b*sy-top,c*sx-left,d*sy-top]
        if 0<=box[0]<box[2]<=size and 0<=box[1]<box[3]<=size:
            rows.append(dict(target,local_box=box))
    return rows


def technical_decisions(technical, session, session_hash):
    """Technical proposals may not replace or silently change saved reviews."""
    if technical is None:
        return [], []
    if (technical.get('source_session_sha256')!=session_hash
            or technical.get('not_independent_approved_gold') is not True
            or technical.get('not_source_corrections') is not True):
        raise ValueError('Technical proposals must bind the exact saved review')
    annotations={a['id']:a for s in session['sheets'] for a in s['annotations']}
    excluded=[];uncertain=[]
    for row in technical['records']:
        current=annotations.get(row['annotation_id'])
        if current is None or sha256(json.dumps(current,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=row['annotation_sha256']:
            raise ValueError('Technical proposal changed from saved annotation')
        if row['action']=='exclude_non_device_box':excluded.append(row['annotation_id'])
        elif row['action']=='retain_localization_uncertain_subtype':uncertain.append(row['annotation_id'])
        else:raise ValueError('Unsupported technical review proposal')
    return excluded,uncertain


def build(workspace,parent,checkpoint,output,authorization_path,*,groups=(21,22),technical_review=None):
    workspace,parent,checkpoint,output,authorization_path=map(Path,(workspace,parent,checkpoint,output,authorization_path))
    if output.exists():raise FileExistsError('Keep immutable dataset revisions')
    session_path=workspace/'data/saved-session.json';registry_path=workspace/'data/approved-references.json'
    session=json.loads(session_path.read_text(encoding='utf-8'));registry=json.loads(registry_path.read_text(encoding='utf-8'))
    auth=json.loads(authorization_path.read_text(encoding='utf-8'))
    if (auth.get('saved_session_sha256')!=digest(session_path) or auth.get('local_development_training') is not True
            or auth.get('production_approval') is not False or not auth.get('user_statement')
            or sorted(auth.get('groups',[]))!=sorted(groups)):
        raise ValueError('Current version-bound local training authorization required')
    excluded=[];uncertain=[];technical=None
    if technical_review:
        technical=json.loads(Path(technical_review).read_text())
        excluded,uncertain=technical_decisions(technical,session,digest(session_path))
    data=json.loads((parent/'manifest.json').read_text());classes=deepcopy(data['classes'])
    if [r['id'] for r in classes]!=list(range(len(classes))):raise ValueError('Parent class order')
    wanted={a.get('legend_entry') for s in session['sheets'] if s.get('group') in groups
        for a in s['annotations'] if a.get('layer')=='symbols' and a.get('review_state')=='user_reviewed'}
    catalog=registry['legend_catalog'];entries={r['legend_entry']:r for r in catalog}
    additions=[];old={r['legend_entry'] for r in classes}
    for identity in sorted(wanted & entries.keys() - old):
        entry=entries[identity]
        # A transfer seed is initialization only, never class equivalence.
        label=entry['label'].casefold();seed=52 if 'outlet' in label else 63 if 'switch' in label else 69 if 'breaker' in label else 61 if 'fan' in label else 32 if 'box' in label else 54
        additions.append(dict(label=entry['label'],seed_parent_class_id=seed))
        classes.append(dict(id=len(classes),label=entry['label'],legend_entry=identity,samples=0,
            source_definition_sha256=digest(registry_path),new_reviewed_plan_class=True))
    sources={}
    # Resolve declared hashes, not filenames, from the bounded source folders.
    required={s['source_sha256'] for s in session['sheets'] if s.get('group') in groups}
    for folder in (workspace/'references',workspace/'images'):
        for path in folder.rglob('*'):
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in ('.png','.jpg','.jpeg') and path.stat().st_size<=25_000_000:
                value=digest(path)
                if value in required:sources[value]=path
    targets,decisions,sheets=review_targets(session,catalog,sources,groups,classes,excluded,uncertain)
    output.mkdir(parents=True);(output/'sources').mkdir()
    shutil.copytree(parent/'images',output/'images');shutil.copytree(parent/'labels',output/'labels')
    shutil.copy2(session_path,output/'saved-session-snapshot.json');shutil.copy2(registry_path,output/'legend-registry-snapshot.json')
    shutil.copy2(authorization_path,output/'local-training-authorization.json')
    shutil.copy2(parent/'manifest.json',output/'parent-manifest-snapshot.json')
    from ultralytics import YOLO
    model=YOLO(str(checkpoint));old_names=dict(model.names)
    if len(old_names)!=len(data['classes']):raise ValueError('Parent checkpoint head mismatch')
    if additions:append_reviewed_head(model.model,additions)
    model.ckpt['ema']=None;model.ckpt['optimizer']=None;model.save(output/'initialized-head.pt')
    metadata=[];parent_hash=digest(parent/'manifest.json')
    for label_path in sorted((parent/'labels/train').glob('*.txt')):
        stem=label_path.stem;image_path=parent/'images/train'/f'{stem}.png'
        if not image_path.is_file():raise ValueError('Parent replay image missing')
        ids=[int(line.split()[0]) for line in label_path.read_text().splitlines() if line.strip()]
        metadata.append(dict(image_id=stem,image_sha256=digest(image_path),label_sha256=digest(label_path),
            allowed_class_ids=[[i] for i in ids],source_kind='parent_retention_replay',
            parent_manifest_sha256=parent_hash,split='train'))
    for sheet in sheets:
        members=[r for r in targets if r['sheet_id']==sheet['sheet_id']]
        source=Image.open(sheet['source_path']).convert('RGB')
        shutil.copy2(sheet['source_path'],output/'sources'/f"{sheet['sheet_id']}.png")
        if digest(output/'sources'/f"{sheet['sheet_id']}.png")!=sheet['source_sha256']:raise ValueError('Copied original source changed')
        scale=4096/max(source.size);size=tuple(round(v*scale) for v in source.size)
        resized=source.resize(size,Image.Resampling.LANCZOS);transform=[size[0]/source.width,size[1]/source.height]
        resized.save(output/'sources'/f"{sheet['sheet_id']}-normalized.png")
        sheet.update(normalized_size=list(size),review_to_training_source_scale=transform,
            normalized_image_sha256=digest(output/'sources'/f"{sheet['sheet_id']}-normalized.png"))
        windows=set()
        for target in members:
            a,b,c,d=target['source_box'];cx=(a+c)*transform[0]/2;cy=(b+d)*transform[1]/2
            for shift in ((0,0),(-48,32),(48,-32)):
                left=max(0,min(size[0]-256,round(cx-128+shift[0])));top=max(0,min(size[1]-256,round(cy-128+shift[1])))
                if (left,top) in windows:continue
                rows=tile_rows(members,(left,top),transform)
                if not rows:continue
                windows.add((left,top));stem=f"review-plan-{sheet['sheet_id']}-{left}-{top}"
                ip=output/'images/train'/f'{stem}.png';lp=output/'labels/train'/f'{stem}.txt'
                resized.crop((left,top,left+256,top+256)).save(ip)
                lines=[]
                for row in rows:
                    x1,y1,x2,y2=row['local_box'];lines.append(f"{row['class_id']} {(x1+x2)/512:.9f} {(y1+y2)/512:.9f} {(x2-x1)/256:.9f} {(y2-y1)/256:.9f}")
                lp.write_text('\n'.join(lines)+'\n')
                metadata.append(dict(image_id=stem,image_sha256=digest(ip),label_sha256=digest(lp),
                    source_kind='latest_user_reviewed_plan',
                    sheet_id=sheet['sheet_id'],project_id=sheet['project_id'],split='train',
                    supervised_record_ids=[r['record_id'] for r in rows],allowed_class_ids=[r['allowed_class_ids'] for r in rows],
                    tile_origin=[left,top],review_to_training_source_scale=transform,source_sha256=sheet['source_sha256'],
                    unannotated_anchor_policy='ignored',independent_example=False))
        source.close();resized.close()
    # Bounded retention sampler covers every old head identity, including old
    # construction-known references. Preserve the entire parent pool on disk.
    rng=random.Random(20261014);pool={};counts=Counter()
    for path in sorted((parent/'labels/train').glob('*.txt')):
        labels={int(line.split()[0]) for line in path.read_text().splitlines() if line.strip()}
        pool[path.stem]=labels
    old_selected=set()
    for cls in range(len(data['classes'])):
        eligible=[name for name,labels in pool.items() if cls in labels];rng.shuffle(eligible)
        if not eligible:raise ValueError(f'Parent class {cls} lacks retention examples')
        old_selected.update(eligible[:8])
    negatives=[r['image_id'] for r in data['reviewed_background_images']];rng.shuffle(negatives);old_selected.update(negatives[:64])
    selected=sorted(old_selected | {r['image_id'] for r in metadata if r['source_kind']=='latest_user_reviewed_plan'})
    for stem in selected:
        for line in (output/'labels/train'/f'{stem}.txt').read_text().splitlines():
            if line.strip():counts[int(line.split()[0])]+=1
    for row in classes:row['samples']=counts[row['id']]
    result=deepcopy(data);result.update(schema='ved_reviewed_multiclass_training_v1',kind='ved_reviewed_multiclass_training_v1',
        required_loss='reviewed_boxes_allowed_subtypes_and_explicit_background',classes=classes,authorization=auth,
        authorization_sha256=digest(authorization_path),saved_session_sha256=digest(session_path),legend_registry_sha256=digest(registry_path),
        parent_manifest_sha256=digest(parent/'manifest.json'),parent_checkpoint_sha256=digest(checkpoint),base_model_sha256=digest(output/'initialized-head.pt'),
        reviewed_plan_targets=targets,training_image_records=metadata,reviewed_plan_sheets=sheets,review_decisions=decisions,
        new_reviewed_positive_backgrounds=0,production_approval=False,diagnostic_only=True,
        reference_rights_exclusions=dict(historical_parent_exclusions=data.get('reference_rights_exclusions'),
            current_authorization_supersedes_selected_groups=list(groups)),
        training_sampler=dict(seed=20261014,old_class_windows_maximum=8,explicit_parent_negatives_maximum=64,
            old_pool_images=len(pool),selected_images=len(selected),train_sources='same-project floor views and all derived tiles remain train',
            class_counts=dict(counts),unknown_regions_are_negatives=False),
        geometry_targets_used=False,validation_status='training-source reviewed-positive recall only; no full-page precision or unseen claim')
    if technical is not None:result['technical_review_proposals']=technical
    (output/'manifest.json').write_text(json.dumps(result,indent=2))
    (output/'train-images.txt').write_text('\n'.join(str((output/'images/train'/f'{s}.png').resolve()) for s in selected)+'\n')
    names={r['id']:unicodedata.normalize('NFKD',r['label']).encode('ascii','ignore').decode() for r in classes}
    import yaml
    (output/'data.yaml').write_text(yaml.safe_dump(dict(path=output.resolve().as_posix(),train='train-images.txt',val='train-images.txt',names=names),sort_keys=False))
    used={i for r in metadata for i in r.get('supervised_record_ids',[])}
    if used!={t['record_id'] for t in targets}:raise ValueError('Reviewed positives lost during tile construction')
    if digest(session_path)!=auth['saved_session_sha256']:raise ValueError('Saved review changed during preparation')
    return dict(targets=len(targets),classes=len(classes),new_classes=len(additions),new_contexts=sum(r['source_kind']=='latest_user_reviewed_plan' for r in metadata),selected_images=len(selected),dataset_sha256=digest(output/'manifest.json'),decisions=dict(Counter(r['reason'] for r in decisions)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','parent','checkpoint','output','authorization'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--technical-review',type=Path)
    a=p.parse_args();print(json.dumps(build(a.workspace,a.parent,a.checkpoint,a.output,a.authorization,technical_review=a.technical_review)))
