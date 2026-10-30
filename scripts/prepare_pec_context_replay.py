"""Native source-context revision of the frozen 129-class development replay.

Reference definitions are not real-layout positives. Every unlabelled part of
these real source images stays ignored by the existing reviewed-box loss.
"""
import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import unicodedata

from PIL import Image
from prepare_pec_reference import digest,SOURCE_SHA256,PREPARED_SHA256,CLEANED_SHA256,PARENT_DATASET_SHA256
from prepare_pec_replay import SCOPE,label_classes,inventory
from prepare_authorized_pdf_detection import validate_training_sources
from prepare_real_lamp_replay import transformed_labels
from probe_pec_reference import reference_page_targets,lost_retention_examples
from probe_symbol_detector_dev import validate_model_classes
from reconcile_pec_reference_catalog import read_json

REPLAY_SHA256='cc73bd2d58c3f1bd9411aab7ff35c2f2596bce9ceac62e80eca6049bf7a4a7af'
CANDIDATE_SHA256='3943a088310b3d926b797293af56effb8af87ae9b3833b09688eff248a788911'
RECOVERY_AUDIT_SHA256='cdb74f91cc1cb6a732b40c21b6120cd70a9f48b4e82702e333c94ecb5e20793f'
CONTEXT_SHA256='586a80b94a67b02911d99c9ec3ea0aaef27c021d737353a4c82ffe5cddc2fe24'
CONTEXT_CHECKPOINT_SHA256='cedd27914e7c7e95e4896852703d6ffbede4e082cedc4fc890efac6c78f91e00'
ORIGINAL_REPORT_SHA256='dd5a8f8d1ca2c8d3912d2923fb6b5699e4dd67d62c1066fc9fdc374c602e0bd5'
CONTEXT_REPORT_SHA256='747637493a6d9b21cc021b4765df370849cd3caa23c2591ddcecda0d072416e1'


def source_views(image,targets,focus,*,scales=(1,)):
    """Complete source boxes, known neighbours, isotropic views; unknown ignored."""
    if max(image.size)>10000 or image.width*image.height>60_000_000:
        raise ValueError('Source allocation exceeds existing bound')
    identities=set()
    for target in targets:
        box=target['source_box']
        if (target['record_id'] in identities or type(target['class_id']) is not int or not 0<=target['class_id']<129
                or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                or not 0<=box[0]<box[2]<=image.width or not 0<=box[1]<box[3]<=image.height):
            raise ValueError('Invalid source target or duplicate identity')
        identities.add(target['record_id'])
    known={t['record_id']:t for t in targets}
    if not focus or any(t['record_id'] not in identities or t!=known[t['record_id']] for t in focus):
        raise ValueError('Focus must be an unchanged existing source target')
    seen=set()
    for scale in scales:
        if type(scale) not in (int,float) or scale not in (1,1.5,2):raise ValueError('Unsupported source-view scale')
        scaled_size=(round(image.width*scale),round(image.height*scale))
        if max(scaled_size)>10000 or scaled_size[0]*scaled_size[1]>60_000_000:
            raise ValueError('Scaled source allocation exceeds existing bound')
        view=image.resize(scaled_size,Image.Resampling.LANCZOS) if scale!=1 else image.copy()
        if min(view.size)<256:raise ValueError('Source view smaller than detail tile')
        for target in focus:
            a,b,c,d=target['source_box']
            for dx,dy in ((-48,-48),(48,-48),(-48,48),(48,48)):
                x=max(0,min(view.width-256,round((a+c)*scale/2-128+dx)))
                y=max(0,min(view.height-256,round((b+d)*scale/2-128+dy)))
                if (scale,x,y) in seen:continue
                lines,ids=transformed_labels(targets,scale,x,y)
                if target['record_id'] not in ids:continue
                seen.add((scale,x,y))
                yield view.crop((x,y,x+256,y+256)),lines,ids,scale,[x,y]
        view.close()


def verified_backfills(original,audit):
    if (audit.get('kind')!='historical_recovery_byte_reconstruction_audit'
            or audit.get('parent_manifest_sha256')!=PARENT_DATASET_SHA256
            or audit.get('recovery_manifest_sha256')!=original['recovery_manifest_sha256']
            or audit.get('human_review_claim') is not False or audit.get('production_approval') is not False
            or audit.get('originals_modified') is not False):raise ValueError('Exact technical reconstruction audit required')
    missing={r['record_id']:r for r in original['images'] if not r.get('image_sha256') or not r.get('label_sha256')}
    rows={r['image_id']:r for r in audit['verified_records']}
    if len(rows)!=len(audit['verified_records']) or set(rows)!=set(missing):raise ValueError('Every historical exclusion requires exact byte evidence')
    result=[]
    for name,row in rows.items():
        if (Path(name).name!=name or row['original_metadata']!=missing[name]
                or row.get('verification')!='exact_original_RGB_pixels_and_historical_source_labels'
                or row['source_sha256']!=missing[name]['source_sha256']
                or row['source_crop']!=missing[name]['source_crop']):raise ValueError('Recovery identity or geometry changed')
        result.append({**deepcopy(missing[name]),'image_sha256':row['image_sha256'],'label_sha256':row['label_sha256'],
                       'byte_evidence_origin':'immutable_original_pixel_and_historical_label_reconstruction',
                       'reconstruction_audit_sha256':RECOVERY_AUDIT_SHA256})
    return result


def prepare(parent,original,checkpoint,prepared,registry_path,recovery_audit,output):
    parent,original,checkpoint,prepared,registry_path,recovery_audit,output=map(Path,
        (parent,original,checkpoint,prepared,registry_path,recovery_audit,output))
    if output.exists():raise FileExistsError('Native-context revisions are immutable')
    if (digest(parent/'manifest.json')!=REPLAY_SHA256 or digest(original/'manifest.json')!=PARENT_DATASET_SHA256
            or not checkpoint.is_file() or checkpoint.stat().st_size>30_000_000 or digest(checkpoint)!=CANDIDATE_SHA256
            or digest(prepared/'manifest.json')!=PREPARED_SHA256 or digest(prepared/'original.pdf')!=SOURCE_SHA256
            or digest(registry_path)!=CLEANED_SHA256 or digest(recovery_audit)!=RECOVERY_AUDIT_SHA256):
        raise ValueError('Exact unchanged source/replay/checkpoint/audit required')
    data=read_json(parent/'manifest.json');old=read_json(original/'manifest.json')
    registry=read_json(registry_path);source=read_json(prepared/'manifest.json');audit=read_json(recovery_audit)
    if (data.get('scope')!=SCOPE or data.get('diagnostic_only') is not True or data.get('all_eligible_entries') is not True
            or len(data['classes'])!=129 or data.get('required_loss')!='positive_boxes_and_explicit_reviewed_background'):
        raise ValueError('Preserve complete development head and unknown-region mask')
    validate_training_sources(parent,data)
    backfills=verified_backfills(old,audit)
    # Verify every selected inherited image/label and complete construction known flag.
    inventory=[]
    for key in ('images','authorized_pdf_training_images','authored_legend_synthetic_images','reviewed_background_images'):
        inventory.extend(data.get(key,[]))
    names=set()
    for row in inventory:
        name=row.get('image_id',row.get('record_id'));ip=parent/'images/train'/f'{name}.png';lp=parent/'labels/train'/f'{name}.txt'
        if (Path(name).name!=name or name in names or digest(ip)!=row.get('image_sha256',row.get('sha256'))
                or row.get('label_sha256') and digest(lp)!=row['label_sha256']):raise ValueError('Inherited training bytes changed')
        label_classes(lp,129);names.add(name)
    for row in backfills:
        name=row['record_id']
        if name in names or digest(original/'images/train'/f'{name}.png')!=row['image_sha256'] or digest(original/'labels/train'/f'{name}.txt')!=row['label_sha256']:
            raise ValueError('Verified reconstruction bytes changed')
        label_classes(original/'labels/train'/f'{name}.txt',129);names.add(name)
    pages=[];all_targets=[]
    for number in (1,2):
        page=next(p for p in source['pages'] if p['page_number']==number)
        if Path(page['filename']).name!=page['filename'] or digest(prepared/page['filename'])!=page['image_sha256']:
            raise ValueError('Prepared source-reference page changed')
        targets=[]
        for r in reference_page_targets(registry,data['reference_specification'],number):
            targets.append({**r,'record_id':f"reference-{number}-{r['reference_id'].replace('.','_')}-{r['variant']}",
                'source_sha256':page['image_sha256'],'pdf_sha256':SOURCE_SHA256,'page_number':number,
                'legend_entry':f"reference-{SOURCE_SHA256[:12]}:{r['reference_id']}:{r['variant']}",
                'annotation_origin':'assistant_reference_definition_extraction_not_real_layout_positive',
                'human_review_claim':False,'split':'train','project_group_id':f'reference-{SOURCE_SHA256[:12]}'})
        pages.append((page,targets));all_targets.extend(targets)
    if len(all_targets)!=62:raise ValueError('All requested reference variants required')
    upload=original/'original-upload.png';upload_source=read_json(original/'upload-preparation.json')
    if digest(upload)!=upload_source['source_sha256']:raise ValueError('Retained upload changed')
    focus=[r for r in old['switch_source_targets'] if r['source_sha256']==upload_source['source_sha256']]
    if len(focus)!=9 or len(old['lamp_upload_targets'])!=20:raise ValueError('Exact original switch/lamp targets required')
    from ultralytics import YOLO
    model=YOLO(str(checkpoint));validate_model_classes(model,data['classes']);del model
    # Source checks complete before materializing a separate revision.
    output.mkdir(parents=True)
    shutil.copytree(parent/'images',output/'images',ignore=shutil.ignore_patterns('*.cache'))
    shutil.copytree(parent/'labels',output/'labels',ignore=shutil.ignore_patterns('*.cache'))
    for auth in data['additional_training_authorizations']:shutil.copy2(parent/auth['filename'],output/auth['filename'])
    shutil.copy2(recovery_audit,output/'historical-byte-audit.json')
    for row in backfills:
        name=row['record_id']
        for folder,suffix in (('images/train','png'),('labels/train','txt')):shutil.copy2(original/folder/f'{name}.{suffix}',output/folder/f'{name}.{suffix}')
    data['images'].extend(backfills)
    origin='assistant_visual_under_user_development_authorization'
    authority=next(a for a in data['additional_training_authorizations'] if a['source_sha256']==SOURCE_SHA256)
    permission=read_json(parent/authority['filename'])
    permission.update(scope='requested_source_reference_definition_context_local_development_only',
        targets=all_targets,annotation_origin='assistant_reference_definition_extraction_not_real_layout_positive',
        human_review_claim=False,production_approval=False)
    authname='reference-context-development-authorization.json'
    (output/authname).write_text(json.dumps(permission,indent=2),encoding='utf-8')
    data['additional_training_authorizations'].append({'filename':authname,'sha256':digest(output/authname),
        'source_sha256':SOURCE_SHA256,'prepared_manifest_sha256':PREPARED_SHA256})
    reference_windows=0;switch_windows=0
    def save_views(path,targets,focused,source_hash,image_hash,kind,scales):
        count=0
        with Image.open(path) as opened:image=opened.convert('RGB')
        for index,(tile,lines,ids,scale,origin_xy) in enumerate(source_views(image,targets,focused,scales=scales)):
            name=f'pdfdev-{kind}-{image_hash[:12]}-{index:03d}'
            ip=output/'images/train'/f'{name}.png';lp=output/'labels/train'/f'{name}.txt'
            if ip.exists() or lp.exists():raise ValueError('New context view collides with history')
            tile.save(ip);tile.close();lp.write_text('\n'.join(lines)+'\n')
            label_classes(lp,129)
            data['authorized_pdf_training_images'].append({'image_id':name,'source_sha256':source_hash,
                'source_image_sha256':image_hash,'image_sha256':digest(ip),'label_sha256':digest(lp),
                'supervised_record_ids':ids,'tile_origin':origin_xy,'isotropic_view_scale':scale,
                'human_review_claim':False,'annotation_origin':origin,'context_kind':kind,
                'missing_annotation_policy':'ignore_unreviewed_not_empty_background','independent_example':False,'split':'train'})
            count+=1
        image.close();return count
    for page,targets in pages:
        reference_windows+=save_views(prepared/page['filename'],targets,targets,SOURCE_SHA256,page['image_sha256'],'reference-native',(1,))
    switch_windows=save_views(upload,old['lamp_upload_targets']+focus,focus,upload_source['source_sha256'],
        upload_source['source_sha256'],'switch-retention-native',(1,1.5,2))
    counts=Counter()
    for path in (output/'labels/train').glob('*.txt'):counts.update(label_classes(path,129))
    if set(counts)!=set(range(129)):raise ValueError('Native context revision omitted a class')
    total=len(list((output/'images/train').glob('*.png')))
    if total>1200 or reference_windows>248 or switch_windows>108:raise ValueError('Source-context replay exceeds bounded preparation')
    for row in data['classes']:row['samples']=counts[row['id']]
    data['replay_sampling']['historical_exclusions_v1']=deepcopy(data['replay_sampling']['excluded_inherited_records'])
    data['replay_sampling']['excluded_inherited_records']=[]
    data.update(base_model_sha256=CANDIDATE_SHA256,parent_dataset_sha256=REPLAY_SHA256,
        initialization_kind='new_dataset_revision_initialized_from_prior_development_replay_weights_optimizer_reset',
        reference_source_context_targets=all_targets,production_approval=False,
        context_revision={'parent_windows':727,'reference_native_windows':reference_windows,
            'switch_retention_windows':switch_windows,'historical_byte_backfills':len(backfills),
            'reconstruction_audit_sha256':RECOVERY_AUDIT_SHA256,'independent_examples_added':0,
            'transform':'source pixels plus explicit isotropic scale/origin; no flips/rotation',
            'unknown_regions':'ignored; source-reference context is NOT complete synthetic background'},
        synthetic_complete_background=True)
    data['warnings'].append('Native reference-source contexts are reference definitions, not real-layout positives. Unrequested reference glyphs/text/wiring remain unlabelled and ignored. Same-source switch views are dependent training examples; no production/independent approval.')
    payload=json.dumps(data,indent=2)
    if len(payload.encode())>5_000_000:raise ValueError('Manifest exceeds existing artifact bound')
    (output/'manifest.json').write_text(payload,encoding='utf-8')
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            name=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(name)}\n")
    validate_training_sources(output,data)
    return {'head_classes':129,'train_windows':total,'reference_native_windows':reference_windows,
            'switch_retention_windows':switch_windows,'historical_byte_backfills':len(backfills),
            'manifest_sha256':digest(output/'manifest.json'),'independent_examples_added':0}


def selected_reference_contexts(data,*,per_variant=2):
    """Hash-order repeated views; preserve supervision for every source variant."""
    if type(per_variant) is not int or per_variant!=2:raise ValueError('Frozen two-view sampling required')
    targets=data['reference_source_context_targets'];ids=[r['record_id'] for r in targets]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate reference variant')
    rows=[r for r in data['authorized_pdf_training_images'] if r.get('context_kind')=='reference-native']
    if len({r['image_id'] for r in rows})!=len(rows):raise ValueError('Duplicate native reference image')
    selected=set()
    for identity in ids:
        pool=sorted((r for r in rows if identity in r['supervised_record_ids']),key=lambda r:(r['image_sha256'],r['image_id']))
        if len(pool)<per_variant:raise ValueError('Insufficient complete reference-variant contexts')
        selected.update(r['image_id'] for r in pool[:per_variant])
    return selected


def retention_windows(image,targets,focus):
    """Two existing inference-grid views; never clip or alter a reviewed box."""
    from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions
    if max(image.size)>10000 or image.width*image.height>60_000_000:raise ValueError('Source allocation exceeds bound')
    # Reuse source_views validation without constructing transformed images.
    known={t['record_id']:t for t in targets}
    if len(known)!=len(targets) or any(t['record_id'] not in known or t!=known[t['record_id']] for t in focus):
        raise ValueError('Exact unique original source targets required')
    for target in targets:
        box=target['source_box']
        if (type(target['class_id']) is not int or not 0<=target['class_id']<80 or len(box)!=4
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                or not 0<=box[0]<box[2]<=image.width or not 0<=box[1]<box[3]<=image.height):
            raise ValueError('Invalid original source target')
    positions=tile_positions(*image.size,dual_phase=True);seen=set()
    for target in focus:
        a,b,c,d=target['source_box']
        choices=[(x,y) for x,y in positions if x<=a<c<=x+256 and y<=b<d<=y+256]
        choices.sort(key=lambda p:(-min(a-p[0],b-p[1],p[0]+256-c,p[1]+256-d),p[0],p[1]))
        for x,y in choices[:2]:
            if (x,y) in seen:continue
            lines,ids=transformed_labels(targets,1,x,y)
            if target['record_id'] not in ids:raise ValueError('Original target lost during coordinate transform')
            seen.add((x,y))
            yield image.crop((x,y,x+256,y+256)),lines,ids,[x,y]


def prepare_retention(parent,original,checkpoint,source_root,parent_report,candidate_report,output):
    """New revision of existing reviewed sources; no new labels/approval claims."""
    parent,original,checkpoint,source_root,parent_report,candidate_report,output=map(Path,
        (parent,original,checkpoint,source_root,parent_report,candidate_report,output))
    if output.exists():raise FileExistsError('Retention-context revisions are immutable')
    if (digest(parent/'manifest.json')!=CONTEXT_SHA256 or digest(original/'manifest.json')!=PARENT_DATASET_SHA256
            or not checkpoint.is_file() or checkpoint.stat().st_size>30_000_000
            or digest(checkpoint)!=CONTEXT_CHECKPOINT_SHA256 or digest(parent_report)!=ORIGINAL_REPORT_SHA256
            or digest(candidate_report)!=CONTEXT_REPORT_SHA256):raise ValueError('Exact frozen retention evidence required')
    data=read_json(parent/'manifest.json');old=read_json(original/'manifest.json')
    before=read_json(parent_report);after=read_json(candidate_report)
    if (data.get('scope')!=SCOPE or data.get('diagnostic_only') is not True or data.get('all_eligible_entries') is not True
            or data.get('required_loss')!='positive_boxes_and_explicit_reviewed_background' or len(data['classes'])!=129
            or data['reviewed_targets']!=old['reviewed_targets'] or data.get('source_approval_kind')!='user_attested_source_permission'
            or after['checkpoint_sha256']!=CONTEXT_CHECKPOINT_SHA256 or after['dataset_manifest_sha256']!=CONTEXT_SHA256
            or any(r.get('threshold')!=.50 or r.get('candidate_shared_tiler_without_activation') is not True for r in (before,after))):
        raise ValueError('Preserve reviewed labels, all classes, masked loss and frozen comparison')
    validate_training_sources(parent,data)
    records=inventory(parent,data,class_count=129)
    audit=parent/'historical-byte-audit.json'
    if digest(audit)!=RECOVERY_AUDIT_SHA256:raise ValueError('Historical byte audit changed')
    if len(records)!=1114:raise ValueError('Complete frozen context inventory required')
    keep_refs=selected_reference_contexts(data)
    ref_rows=[r for r in data['authorized_pdf_training_images'] if r.get('context_kind')=='reference-native']
    omitted=[r for r in ref_rows if r['image_id'] not in keep_refs]
    if len(ref_rows)!=248 or len(data['reference_source_context_targets'])!=62:raise ValueError('All reference variants required')
    omitted_ids={r['image_id'] for r in omitted};chosen=set(records)-omitted_ids
    focus=lost_retention_examples(old,before,after,class_ids=tuple(range(80)),examples_per_class=200)
    if not focus or len(focus)>100:raise ValueError('Retention target count exceeds bounded experiment')
    by_source={}
    for target in old['reviewed_targets']:by_source.setdefault(target['source_sha256'],[]).append(target)
    paths={};focused_sources={r['source_sha256'] for r in focus}
    for source_hash in focused_sources:
        source_targets=by_source[source_hash];sheets={r['sheet_id'] for r in source_targets}
        if len(sheets)!=1:raise ValueError('Resolve source-page identity before creating views')
        sheet=next(iter(sheets));path=source_root/f'{sheet}.jpg'
        if (Path(sheet).name!=sheet or sheet in ('sheet-51','sheet-52') or path.is_symlink()
                or path.stat().st_size>25_000_000 or digest(path)!=source_hash):raise ValueError('Exact authorized original required')
        with Image.open(path) as image:
            if max(image.size)>10000 or image.width*image.height>60_000_000:raise ValueError('Source allocation exceeds bound')
        paths[source_hash]=path
    from ultralytics import YOLO
    model=YOLO(str(checkpoint));validate_model_classes(model,data['classes']);del model
    output.mkdir(parents=True);(output/'images/train').mkdir(parents=True);(output/'labels/train').mkdir(parents=True)
    for name in sorted(chosen):
        for folder,suffix in (('images/train','png'),('labels/train','txt')):shutil.copy2(parent/folder/f'{name}.{suffix}',output/folder/f'{name}.{suffix}')
    for auth in data['additional_training_authorizations']:shutil.copy2(parent/auth['filename'],output/auth['filename'])
    shutil.copy2(audit,output/audit.name)
    data['authorized_pdf_training_images']=[r for r in data['authorized_pdf_training_images'] if r['image_id'] not in omitted_ids]
    byte_parents={(r['image_sha256'],r['label_sha256']):name for name,r in records.items()}
    new_rows=[];covered=set()
    for source_hash in sorted(paths):
        targets=by_source[source_hash];local_focus=[r for r in focus if r['source_sha256']==source_hash]
        with Image.open(paths[source_hash]) as opened:image=opened.convert('RGB')
        for index,(tile,lines,ids,origin) in enumerate(retention_windows(image,targets,local_focus)):
            name=f'retention-native-{source_hash[:12]}-{index:03d}';ip=output/'images/train'/f'{name}.png';lp=output/'labels/train'/f'{name}.txt'
            if name in records or ip.exists():raise ValueError('Retention view collides with original history')
            tile.save(ip);tile.close();lp.write_text('\n'.join(lines)+'\n')
            image_sha,label_sha=digest(ip),digest(lp);label_classes(lp,129)
            supervised=[deepcopy(r) for r in targets if r['record_id'] in ids]
            covered.update((source_hash,rid) for rid in ids)
            row={'record_id':name,'sheet_id':targets[0]['sheet_id'],'source_sha256':source_hash,
                'source_page_id':f'{source_hash}:page:1','source_crop':origin+[origin[0]+256,origin[1]+256],
                'tile_origin':origin,'isotropic_view_scale':1,'local_to_source_coords':[1,0,origin[0],0,1,origin[1]],
                'source_to_local_coords':[1,0,-origin[0],0,1,-origin[1]],'image_sha256':image_sha,'label_sha256':label_sha,
                'supervised_records':supervised,'supervised_record_ids':ids,'split':'training_diagnostic_only',
                'annotation_origin':'unchanged_existing_user_attested_reviewed_targets_new_technical_crop',
                'missing_annotation_policy':'ignore_unreviewed_not_empty_background','independent_example':False,
                'byte_identical_training_parent':byte_parents.get((image_sha,label_sha))}
            data['images'].append(row);new_rows.append(row)
        image.close()
    skipped=[r for r in focus if (r['source_sha256'],r['record_id']) not in covered]
    total=len(chosen)+len(new_rows)
    if len(new_rows)>200 or total>1200:raise ValueError('Retention context exceeds existing window budget')
    counts=Counter()
    for path in (output/'labels/train').glob('*.txt'):counts.update(label_classes(path,129))
    if set(counts)!=set(range(129)):raise ValueError('Retention revision omitted a model class')
    for row in data['classes']:row['samples']=counts[row['id']]
    data.update(base_model_sha256=CONTEXT_CHECKPOINT_SHA256,parent_dataset_sha256=CONTEXT_SHA256,
        initialization_kind='best_context_run1_old_class_retention_weights_new_dataset_optimizer_reset',
        retention_context_revision={'parent_windows':1114,'selected_native_reference_windows':len(keep_refs),
            'reference_variants':62,'minimum_native_windows_per_reference_variant':2,
            'omitted_repeated_reference_views':omitted,'new_original_retention_windows':len(new_rows),
            'parent_report_sha256':ORIGINAL_REPORT_SHA256,'candidate_report_sha256':CONTEXT_REPORT_SHA256,
            'selected_regressions':focus,'regressions_without_complete_native_window':skipped,
            'covered_focus_targets':sum((r['source_sha256'],r['record_id']) in covered for r in focus),
            'independent_examples_added':0,'original_labels_changed':False,
            'selection':'All prior-correct/current-missed original targets; up to two native inference-grid windows each. Two hash-ordered reference views per variant.',
            'project_policy':'Original training-source identities retained; related groups 1-6 not split; no project-separated evaluation claimed.'})
    data['warnings'].append('Retention windows reuse existing user-attested source boxes/neighbor labels. Failure-driven sampling is development-only, not independent validation. Repeated reference views remain recoverable in the immutable parent. No thresholds, meanings, approvals or original annotations changed.')
    payload=json.dumps(data,indent=2)
    if len(payload.encode())>5_000_000:raise ValueError('Manifest exceeds existing artifact bound')
    (output/'manifest.json').write_text(payload,encoding='utf-8')
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in data['classes']:
            name=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(name)}\n")
    validate_training_sources(output,data);inventory(output,data,class_count=129)
    return {'head_classes':129,'train_windows':total,'native_reference_windows':len(keep_refs),
        'new_original_retention_windows':len(new_rows),'focus_targets':len(focus),'covered_focus_targets':len(focus)-len(skipped),
        'skipped_focus_targets':len(skipped),'manifest_sha256':digest(output/'manifest.json'),'independent_examples_added':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('reference','retention'),default='reference')
    for name in ('parent','original','checkpoint','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('prepared','registry','recovery-audit','source-root','parent-report','candidate-report'):
        parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.phase=='reference':
        if not all((args.prepared,args.registry,args.recovery_audit)):parser.error('Reference phase requires preparation, registry and recovery audit')
        result=prepare(args.parent,args.original,args.checkpoint,args.prepared,args.registry,args.recovery_audit,args.output)
    else:
        if not all((args.source_root,args.parent_report,args.candidate_report)):parser.error('Retention phase requires source root and both frozen reports')
        result=prepare_retention(args.parent,args.original,args.checkpoint,args.source_root,args.parent_report,args.candidate_report,args.output)
    print(json.dumps(result))
