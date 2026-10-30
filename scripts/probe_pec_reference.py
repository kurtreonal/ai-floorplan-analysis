"""Reference-table context check and per-entry learning report, never accuracy."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from prepare_pec_reference import SOURCE_SHA256, PREPARED_SHA256, CLEANED_SHA256, PARENT_DATASET_SHA256, digest
from probe_symbol_detector_dev import probe_unreviewed_image, probe_authored_synthetic, match_targets
from reconcile_pec_reference_catalog import read_json


def reference_page_targets(registry,specification,page_number):
    if type(page_number) is not int or page_number not in (1,2):
        raise ValueError('Select explicit requested reference page one or two')
    mappings=specification['point_mappings']
    mapping={r['reference_id']:r for r in mappings}
    if len(mapping)!=len(mappings):
        raise ValueError('Duplicate requested reference identity')
    targets=[]
    identities=set()
    for row in registry['references']:
        if row['annotation_layer']=='wiring' or row['source_page_id']!=f'{SOURCE_SHA256}:page:{page_number}':continue
        target=mapping[row['reference_id']]
        identity=(row['reference_id'],row['variant'])
        box=row['bbox_source_pixels']
        if (identity in identities or len(box)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                or not (0<=box[0]<box[2] and 0<=box[1]<box[3])
                or type(target['model_class_id']) is not int or target['model_class_id']<0):
            raise ValueError('Invalid or duplicated reference target')
        identities.add(identity)
        targets.append({'reference_id':row['reference_id'],'variant':row['variant'],
            'source_box':row['bbox_source_pixels'],'class_id':target['model_class_id'],
            'label':target['model_label'],'source_page_id':row['source_page_id'],
            'annotation_origin':'assistant_source_reference_extraction_not_real_layout_annotation'})
    return targets


def table_probe(dataset,checkpoint,prepared,registry_path,output,*,page_number=1):
    dataset,checkpoint,prepared,registry_path,output=map(Path,(dataset,checkpoint,prepared,registry_path,output))
    if output.exists():raise FileExistsError('Reference-table probe revisions are immutable')
    if type(page_number) is not int or page_number not in (1,2):
        raise ValueError('Select explicit requested reference page one or two')
    if (digest(prepared/'manifest.json')!=PREPARED_SHA256 or digest(prepared/'original.pdf')!=SOURCE_SHA256
            or digest(registry_path)!=CLEANED_SHA256):raise ValueError('Exact source-reference revision required')
    manifest=read_json(dataset/'manifest.json');registry=read_json(registry_path);source=read_json(prepared/'manifest.json')
    if (manifest.get('scope') not in ('full_requested_reference_learning_diagnostic_not_universal_detector_release',
                                   'all_class_reference_replay_development_not_release')
            or manifest.get('diagnostic_only') is not True):
        raise ValueError('Expected full reference diagnostic, not an active release')
    targets=reference_page_targets(registry,manifest['reference_specification'],page_number)
    page=next(p for p in source['pages'] if p['page_number']==page_number)
    path=prepared/page['filename']
    if Path(page['filename']).name!=page['filename'] or digest(path)!=page['image_sha256']:
        raise ValueError('Reference page image changed')
    probe_unreviewed_image(path,output,checkpoint=checkpoint,dataset=dataset)
    raw=read_json(output/'report.json');predictions=raw['predictions']
    localized=match_targets(targets,predictions,require_class=False);classified=match_targets(targets,predictions)
    with Image.open(path) as opened:
        image=opened.convert('RGB');draw=ImageDraw.Draw(image)
        for i,target in enumerate(targets):
            draw.rectangle(target['source_box'],outline='green' if i in classified else 'red',width=2)
        for row in predictions:draw.rectangle(row['bbox'],outline='orange',width=1)
        image.save(output/'expected-vs-predicted.png');image.close()
    result={**raw,'kind':'source_reference_table_context_probe_not_floorplan_generalization',
        'source_pdf_sha256':SOURCE_SHA256,'source_page_id':page['source_page_id'],
        'model_class_count':len(manifest['classes']),'precision':None,'independent_accuracy':None,
        'targets':targets,'target_count':len(targets),'localized':len(localized),
        'classified_and_localized':len(classified),'matching':'maximum one-to-one IoU >= 0.50',
        'scope':'full supplied reference page; requested glyphs only, reused source, unrequested content unscored',
        'human_review_claim':False,'production_approval':False,'active_model_changed':False}
    (output/'reference-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return {'source_page_number':page_number,'targets':len(targets),'localized':len(localized),
        'classified_and_localized':len(classified),'proposals':len(predictions),'truncated':raw['truncated'],
        'independent_accuracy':None,'seconds':raw['seconds']}


def write_coverage(dataset,checkpoint,probe_report,output):
    dataset,checkpoint,probe_report,output=map(Path,(dataset,checkpoint,probe_report,output))
    if output.exists():raise FileExistsError('Reference coverage reports are immutable')
    data=read_json(dataset/'manifest.json');report=read_json(probe_report)
    if (report['dataset_sha256']!=digest(dataset/'manifest.json') or report['checkpoint_sha256']!=digest(checkpoint)
            or report.get('full_requested_reference_diagnostic') is not True
            or data.get('scope')!='full_requested_reference_learning_diagnostic_not_universal_detector_release'
            or data.get('diagnostic_only') is not True):
        raise ValueError('Coverage cannot combine different datasets or checkpoints')
    by_class={r['class_id']:r for r in report['summary']}
    expected={r['model_class_id'] for r in data['reference_specification']['point_mappings']}
    if len(by_class)!=len(report['summary']) or set(by_class)!=expected:
        raise ValueError('Coverage must report every requested class exactly once')
    tested=Counter();localized=Counter();correct=Counter();identities=set()
    for row in report['results']:
        cls=row['expected_class_id']
        if (row['image_id'] in identities or cls not in expected
                or type(row['localized']) is not bool or type(row['localized_and_classified']) is not bool
                or row['localized_and_classified'] and not row['localized']):
            raise ValueError('Invalid learning-check result identity or outcome')
        identities.add(row['image_id']);tested[cls]+=1
        localized[cls]+=row['localized'];correct[cls]+=row['localized_and_classified']
    for cls,measurement in by_class.items():
        if (measurement['tested']!=tested[cls] or measurement['localized']!=localized[cls]
                or measurement['localized_and_classified']!=correct[cls]
                or tested[cls]!=data['classes'][cls]['samples']):
            raise ValueError('Summary differs from actual complete learning-check outcomes')
    rows=[]
    for source in data['reference_specification']['point_mappings']:
        cls=source['model_class_id'];measurement=by_class[cls]
        rows.append({**source,'training_images':data['classes'][cls]['samples'],
            'prediction_count':sum(p['class_id']==cls for r in report['results'] for p in r['predictions']),
            'synthetic_tested':measurement['tested'],'synthetic_localized':measurement['localized'],
            'synthetic_localized_and_classified':measurement['localized_and_classified'],
            'real_page_recall':None,'real_page_precision':None,'independent_accuracy':None,
            'limitations':['Synthetic reference resubstitution, not independent real-page detection.',
                'No new real-layout positives for this reference meaning.',
                'Drawing-specific project mapping remains unresolved.']})
    wiring=[{**r,'included_in_point_training':False,'training_status':'wiring_reference_only_not_point_device',
        'known_limitation':'Requires a separate observed-wiring task; not converted to installed devices.'}
        for r in data['reference_specification']['wiring_references']]
    result={'schema':'ved-requested-reference-coverage-v1','dataset_manifest_sha256':digest(dataset/'manifest.json'),
        'checkpoint_sha256':digest(checkpoint),'probe_report_sha256':digest(probe_report),
        'entries':rows,'wiring_references':wiring,'active_model_changed':False,'production_approval':False,
        'unsupported_metrics':['real_page_precision','real_page_recall','independent_accuracy'],
        'unsupervised_parent_class_ids':[r['id'] for r in data['classes'] if not r['samples']]}
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return {'device_entries':len(rows),'wiring_entries':len(wiring),'all_have_nonzero_synthetic_matches':all(r['synthetic_localized_and_classified'] for r in rows),
        'report_sha256':digest(output)}


def replay_probe(dataset,checkpoint,prepared,registry,retention,output):
    """Frozen reference/table and original-upload checks for the same candidate."""
    from prepare_pec_replay import SCOPE
    from probe_real_lamps import select_lamp_view
    from probe_authorized_pdf_detection import score
    dataset,checkpoint,prepared,registry,retention,output=map(Path,(dataset,checkpoint,prepared,registry,retention,output))
    if output.exists():raise FileExistsError('Replay evaluation revisions are immutable')
    data=read_json(dataset/'manifest.json');old=read_json(retention/'manifest.json')
    if (data.get('scope')!=SCOPE or data.get('diagnostic_only') is not True
            or data.get('all_eligible_entries') is not True or len(data['classes'])!=129
            or digest(retention/'manifest.json')!=PARENT_DATASET_SHA256
            or [(r['id'],r['label']) for r in old['classes']]!=[(r['id'],r['label']) for r in data['classes'][:80]]):
        raise ValueError('Exact all-class replay/retention identities required')
    source,_,path,lamps=select_lamp_view(retention,old,upload=True)
    switches=[r for r in old['switch_source_targets'] if r['source_sha256']==source['source_sha256']]
    if len(lamps)!=20 or len(switches)!=9:raise ValueError('Exact original upload targets required')
    probe_authored_synthetic(dataset,checkpoint,output/'synthetic',samples_per_class=64)
    synthetic=read_json(output/'synthetic/report.json')
    pages=[]
    for page in (1,2):
        table_probe(dataset,checkpoint,prepared,registry,output/f'table-page{page}',page_number=page)
        pages.append(read_json(output/f'table-page{page}/reference-report.json'))
    probe_unreviewed_image(path,output/'retention-upload',checkpoint=checkpoint,dataset=dataset)
    upload=read_json(output/'retention-upload/report.json');predictions=upload['predictions']
    targets=lamps+switches
    with Image.open(path) as opened:
        overlay=opened.convert('RGB');pen=ImageDraw.Draw(overlay);matches=match_targets(targets,predictions)
        for index,target in enumerate(targets):pen.rectangle(target['source_box'],outline='green' if index in matches else 'red',width=2)
        for row in predictions:pen.rectangle(row['bbox'],outline='orange',width=1)
        overlay.save(output/'retention-upload/expected-vs-predicted.png');overlay.close()
    measured={r['class_id']:r for r in synthetic['summary']}
    entries=[];references=[]
    for row in data['classes']:
        cls=row['id'];real=[t for t in targets if t['class_id']==cls]
        entries.append({**row,'included_in_training':True,'training_count_unit':'windows containing this class',
            'synthetic_learning_check':measured.get(cls),
            'original_upload_retention':score(real,predictions) if real else None,
            'independent_accuracy':None,'real_page_precision':None,'production_approval':False})
    for reference in data['reference_specification']['point_mappings']:
        tests=[r for r in synthetic['results'] if r.get('reference_id')==reference['reference_id']]
        context=Counter()
        for page in pages:
            class_matches=match_targets(page['targets'],page['predictions'])
            location_matches=match_targets(page['targets'],page['predictions'],require_class=False)
            for index,target in enumerate(page['targets']):
                if target['reference_id']==reference['reference_id']:
                    context['tested']+=1;context['localized']+=index in location_matches
                    context['localized_and_classified']+=index in class_matches
        references.append({**reference,'synthetic_tested':len(tests),
            'synthetic_correct':sum(r['localized_and_classified'] for r in tests),
            'source_reference_table_context':dict(context),'independent_accuracy':None,'real_page_precision':None})
    result={'kind':'all_class_reference_replay_same_source_development_probe_v1',
        'dataset_manifest_sha256':digest(dataset/'manifest.json'),'checkpoint_sha256':digest(checkpoint),
        'retention_parent_manifest_sha256':PARENT_DATASET_SHA256,'source_pdf_sha256':SOURCE_SHA256,
        'threshold':.50,'matching':'one-to-one IoU >= .50, numeric class ID',
        'model_entries':entries,'requested_device_references':references,
        'wiring_references':data['reference_specification']['wiring_references'],
        'retention_upload':{'source_sha256':source['source_sha256'],'proposals':len(predictions),
            'truncated':upload['truncated'],'all':score(targets,predictions),
            'lamps':score(lamps,predictions),'switches':score(switches,predictions)},
        'table_pages':[{'source_page_id':p['source_page_id'],'target_count':p['target_count'],
            'localized':p['localized'],'classified_and_localized':p['classified_and_localized'],
            'proposals':len(p['predictions']),'truncated':p['truncated']} for p in pages],
        'precision':None,'independent_accuracy':None,'human_review_claim':False,'active_model_changed':False,
        'production_approval':False,'limitations':['All probes reuse development/training sources, not independent evaluation.',
            'New reference-only meanings have no real-layout positives; requested wiring patterns not trained as devices.',
            'Unmatched real-page proposals unresolved; precision cannot be scored from partial targets.']}
    (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return {'head_classes':129,'requested_reference_meanings':54,
        'reference_synthetic_correct':sum(r['synthetic_correct'] for r in references),
        'reference_synthetic_tested':sum(r['synthetic_tested'] for r in references),
        'zero_match_reference_ids':[r['reference_id'] for r in references if not r['synthetic_correct']],
        'table_correct':sum(p['classified_and_localized'] for p in pages),
        'table_tested':sum(p['target_count'] for p in pages),'retention_upload':result['retention_upload'],
        'independent_accuracy':None,'checkpoint_sha256':result['checkpoint_sha256']}


def write_replay_checkpoint_report(dataset,checkpoint,replay_report,original_report,output):
    """Join per-entry coverage without equating proposals to correct detections."""
    dataset,checkpoint,replay_report,original_report,output=map(Path,(dataset,checkpoint,replay_report,original_report,output))
    if output.exists():raise FileExistsError('Per-entry checkpoint reports are immutable')
    data=read_json(dataset/'manifest.json');replay=read_json(replay_report);original=read_json(original_report)
    dataset_hash=digest(dataset/'manifest.json');checkpoint_hash=digest(checkpoint)
    if (data.get('scope')!='all_class_reference_replay_development_not_release' or data.get('diagnostic_only') is not True
            or len(data['classes'])!=129 or original.get('candidate_shared_tiler_without_activation') is not True
            or original.get('class_agnostic') is not False or original.get('kind')!='partial_label_full_page_probe_v1'
            or replay.get('kind')!='all_class_reference_replay_same_source_development_probe_v1'
            or any(r.get('dataset_manifest_sha256')!=dataset_hash or r.get('checkpoint_sha256')!=checkpoint_hash
                   or r.get('threshold')!=.50 or r.get('precision') is not None for r in (replay,original))):
        raise ValueError('Exact same-source development reports required')
    measures={r['class_id']:r for r in original['summary']['per_class']}
    entries={r['id']:r for r in replay['model_entries']};expected=set(range(129))
    if (any(type(c.get('id')) is not int for c in data['classes']) or {c['id'] for c in data['classes']}!=expected
            or any(type(r.get('class_id')) is not int for r in original['summary']['per_class'])
            or any(type(r.get('id')) is not int for r in replay['model_entries'])
            or set(measures)!=expected or len(original['summary']['per_class'])!=129 or set(entries)!=expected
            or len(replay['model_entries'])!=129 or len(replay['requested_device_references'])!=54):
        raise ValueError('Every model identity and reference meaning must remain visible')
    counts=Counter();tested=Counter();located=Counter();correct=Counter();identities=set()
    for page in original['pages']:
        for target in page['targets']:
            identity=(page['source_sha256'],target['record_id']);index=target['class_id']
            if (identity in identities or type(index) is not int or index not in expected
                    or type(target.get('localized')) is not bool
                    or type(target.get('localized_and_classified')) is not bool):
                raise ValueError('Invalid or duplicated original target outcome')
            identities.add(identity);tested[index]+=1
            located[index]+=target['localized'];correct[index]+=target['localized_and_classified']
        for row in page['predictions']:
            if (type(row['class_id']) is not int or row['class_id'] not in expected
                    or type(row['score']) not in (int,float) or not math.isfinite(row['score']) or not .50<=row['score']<=1):
                raise ValueError('Unexpected proposal class or score')
            counts[row['class_id']]+=1
    summary=original['summary']
    if (sum(counts.values())!=summary['fused_proposals']
            or any(type(summary.get(key)) is not int or summary[key]!=value for key,value in
                   (('reviewed_positive_count',sum(tested.values())),('localized',sum(located.values())),
                    ('localized_and_classified',sum(correct.values()))))
            or not sum(correct.values())<=sum(located.values())<=sum(tested.values())):
        raise ValueError('Original-source totals changed')
    rows=[]
    for cls in data['classes']:
        index=cls['id'];entry=entries[index];measured=measures[index]
        if (any(entry.get(k)!=cls.get(k) for k in ('id','legend_entry','label','samples'))
                or any(measured.get(k)!=cls.get(k) for k in ('label','legend_entry'))
                or entry.get('included_in_training') is not True
                or type(cls['samples']) is not int or cls['samples']<=0
                or any(type(measured.get(key)) is not int or measured[key]!=value for key,value in
                       (('reviewed_positive_count',tested[index]),('localized',located[index]),
                        ('localized_and_classified',correct[index])))):
            raise ValueError('Model identity or original-source measurements changed')
        rows.append({'model_class_id':index,'legend_entry':cls['legend_entry'],'label':cls['label'],
            'original_56_entry':index<56,'included_in_training':True,'training_windows':cls['samples'],
            'training_count_unit':'windows containing the class; dependent replay/augmentation, not independent examples',
            'proposals_on_original_source_pages':counts[index],
            'reviewed_original_source_targets':measured['reviewed_positive_count'],
            'matched_original_source_targets':measured['localized_and_classified'],
            'localized_original_source_targets':measured['localized'],
            'synthetic_learning_check':entry['synthetic_learning_check'],
            'source_reference_meanings':[r for r in replay['requested_device_references'] if r['model_class_id']==index],
            'precision':None,'independent_accuracy':None,'production_approval':False,
            'limitations':['Proposal counts are not counts of confirmed/correct devices; unreviewed proposals remain unresolved.',
                'Partially annotated development/training sources, not independent project validation.',
                *(['Reference-only meaning without real-layout positives or approved project mapping.'] if index>=80 else [])]})
    result={'kind':'all_class_development_checkpoint_entry_coverage_v1','dataset_manifest_sha256':dataset_hash,
        'checkpoint_sha256':checkpoint_hash,'replay_report_sha256':digest(replay_report),
        'original_report_sha256':digest(original_report),'source_page_count':len(original['pages']),
        'original_56_entries':[r for r in rows if r['original_56_entry']],'all_129_entries':rows,
        'requested_device_references':replay['requested_device_references'],'wiring_references':replay['wiring_references'],
        'original_source_summary':{k:v for k,v in original['summary'].items() if k!='per_class'},
        'matching_note':'Class-aware and class-agnostic maximum one-to-one assignments are independent. '
                        'Overlapping targets can be assigned differently, so per-class location counts '
                        'are not necessarily a superset of per-class class-aware matches.',
        'precision':None,'independent_accuracy':None,'active_model_changed':False,'human_review_claim':False,'production_approval':False}
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    return {'original_entries':56,'all_model_entries':129,'device_references':54,'source_pages':len(original['pages']),
        'proposals':sum(counts.values()),'report_sha256':digest(output),'independent_accuracy':None}


def lost_retention_examples(original,parent_report,candidate_report,*,class_ids=(20,33,53,55),examples_per_class=1):
    """Deterministic target-guided diagnostics, never another evaluation split."""
    if (type(examples_per_class) is not int or not 1<=examples_per_class<=200
            or len(set(class_ids))!=len(class_ids) or any(type(c) is not int or not 0<=c<80 for c in class_ids)):
        raise ValueError('Bounded original-class retention selection required')
    expected={}
    for target in original['reviewed_targets']:
        key=(target['source_sha256'],target['record_id'])
        if key in expected:raise ValueError('Duplicate original target identity')
        expected[key]=target
    def observations(report):
        if report.get('kind')!='partial_label_full_page_probe_v1':raise ValueError('Frozen full-page report required')
        rows={}
        for page in report['pages']:
            for target in page['targets']:
                key=(page['source_sha256'],target['record_id'])
                if (key in rows or key not in expected or target['class_id']!=expected[key]['class_id']
                        or type(target.get('localized_and_classified')) is not bool):
                    raise ValueError('Full-page target identity or decision changed')
                rows[key]=target['localized_and_classified']
        if set(rows)!=set(expected):raise ValueError('Compared reports must cover the same original targets')
        return rows
    before,after=observations(parent_report),observations(candidate_report)
    selected=[]
    for cls in class_ids:
        lost=[key for key,target in expected.items() if target['class_id']==cls and before[key] and not after[key]]
        selected.extend(expected[key] for key in sorted(lost)[:examples_per_class])
    return selected


def retention_diagnostic(dataset,checkpoint,original,parent_checkpoint,source_root,parent_report,candidate_report,output):
    """Compare exact native/isolated lost targets on both models, serial CPU."""
    from ultralytics import YOLO
    from prepare_pec_replay import PARENT_CHECKPOINT_SHA256
    from probe_symbol_detector_dev import validate_model_classes,iou
    from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions
    dataset,checkpoint,original,parent_checkpoint,source_root,parent_report,candidate_report,output=map(Path,
        (dataset,checkpoint,original,parent_checkpoint,source_root,parent_report,candidate_report,output))
    if output.exists():raise FileExistsError('Retention diagnostics are immutable')
    if (digest(original/'manifest.json')!=PARENT_DATASET_SHA256 or digest(parent_checkpoint)!=PARENT_CHECKPOINT_SHA256
            or not checkpoint.is_file() or checkpoint.stat().st_size>30_000_000):
        raise ValueError('Exact bounded original/candidate weights required')
    data=read_json(dataset/'manifest.json');old=read_json(original/'manifest.json')
    before=read_json(parent_report);after=read_json(candidate_report)
    if (data.get('scope')!='all_class_reference_replay_development_not_release' or data.get('diagnostic_only') is not True
            or before.get('checkpoint_sha256')!=digest(parent_checkpoint) or after.get('checkpoint_sha256')!=digest(checkpoint)
            or before.get('dataset_manifest_sha256')!=PARENT_DATASET_SHA256
            or after.get('dataset_manifest_sha256')!=digest(dataset/'manifest.json')
            or any(r.get('threshold')!=.50 or r.get('candidate_shared_tiler_without_activation') is not True
                   for r in (before,after))):raise ValueError('Exact frozen same-source reports required')
    identities=lambda rows:[{key:r[key] for key in ('id','label','legend_entry')} for r in rows]
    if len(old['classes'])!=80 or len(data['classes'])!=129 or identities(data['classes'][:80])!=identities(old['classes']):
        raise ValueError('Original class identities changed')
    targets=lost_retention_examples(old,before,after)
    if not targets:raise ValueError('No selected retention regression to diagnose')
    by_hash={digest(p):p for p in source_root.rglob('*') if p.is_file() and not p.is_symlink()
             and p.suffix.lower() in ('.jpg','.jpeg','.png') and p.stat().st_size<=25_000_000}
    items=[]
    for target in targets:
        if target['source_sha256'] not in by_hash:raise ValueError('Exact original source missing')
        with Image.open(by_hash[target['source_sha256']]) as opened:image=opened.convert('RGB')
        if max(image.size)>10000 or image.width*image.height>60_000_000:raise ValueError('Source allocation exceeds bound')
        a,b,c,d=target['source_box']
        if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b,c,d))
                or not 0<=a<c<=image.width or not 0<=b<d<=image.height):raise ValueError('Invalid source target')
        choices=[(x,y) for x,y in tile_positions(*image.size,dual_phase=True) if x<=a<c<=x+256 and y<=b<d<=y+256]
        if not choices:raise ValueError('No complete bounded original tile')
        x,y=max(choices,key=lambda p:min(a-p[0],b-p[1],p[0]+256-c,p[1]+256-d))
        native=image.crop((x,y,x+256,y+256));box=[a-x,b-y,c-x,d-y]
        isolated=Image.new('RGB',(256,256),'white');isolated.paste(image.crop((a,b,c,d)),(round(a-x),round(b-y)))
        items.extend([(target,'native_source_tile',native,box,[x,y]),
                      (target,'isolated_original_glyph',isolated,box,[x,y])]);image.close()
    output.mkdir(parents=True);rows=[]
    for name,path,classes in (('current_80_class_parent',parent_checkpoint,old['classes']),
                              ('context_129_class_candidate',checkpoint,data['classes'])):
        model=YOLO(str(path));validate_model_classes(model,classes)
        for offset in range(0,len(items),2):
            batch=items[offset:offset+2]
            predictions=model.predict([r[2] for r in batch],imgsz=320,conf=.01,batch=2,device='cpu',verbose=False,max_det=200)
            for (target,kind,image,box,origin),prediction in zip(batch,predictions):
                raw=[{'bbox':b.xyxy[0].tolist(),'class_id':int(b.cls[0]),'score':float(b.conf[0])} for b in prediction.boxes]
                overlaps=[r for r in raw if iou(box,r['bbox'])>=.50]
                correct=[r for r in overlaps if r['class_id']==target['class_id']]
                annotated=image.copy();pen=ImageDraw.Draw(annotated);pen.rectangle(box,outline='green',width=1)
                for r in raw:pen.rectangle(r['bbox'],outline='orange',width=1)
                filename=f"{name}-{target['class_id']}-{kind}.png";annotated.save(output/filename);annotated.close()
                rows.append({'model':name,'kind':kind,'original_target':target,'tile_origin':origin,
                    'expected_local_box':box,'best_correct_overlap_score':max((r['score'] for r in correct),default=None),
                    'best_overlap':max(overlaps,key=lambda r:r['score'],default=None),'raw_predictions':raw,'overlay':filename})
        del model
    for item in items:item[2].close()
    result={'kind':'paired_original_retention_raw_output_diagnostic','dataset_manifest_sha256':digest(dataset/'manifest.json'),
        'parent_checkpoint_sha256':digest(parent_checkpoint),'candidate_checkpoint_sha256':digest(checkpoint),
        'parent_report_sha256':digest(parent_report),'candidate_report_sha256':digest(candidate_report),'rows':rows,
        'raw_observation_threshold':.01,'unchanged_live_and_scored_threshold':.50,
        'independent_accuracy':None,'precision':None,'active_model_changed':False,'human_review_claim':False,
        'interpretation':'Target-guided technical comparison on previously trained pages; not generalization or a changed metric.'}
    (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return [{'class_id':r['original_target']['class_id'],**{k:r[k] for k in ('model','kind','best_correct_overlap_score','best_overlap')}} for r in rows]


def context_diagnostic(dataset,checkpoint,prepared,registry_path,output,*,reference_ids=('1.20.10','1.21.1')):
    """Six paired raw-score inputs, not a modified detection metric or threshold."""
    from ultralytics import YOLO
    from probe_symbol_detector_dev import validate_model_classes,iou
    from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions
    dataset,checkpoint,prepared,registry_path,output=map(Path,(dataset,checkpoint,prepared,registry_path,output))
    if output.exists():raise FileExistsError('Context diagnostic revisions are immutable')
    if not checkpoint.is_file() or checkpoint.stat().st_size>30_000_000:
        raise ValueError('Existing bounded local checkpoint required')
    if digest(prepared/'manifest.json')!=PREPARED_SHA256 or digest(registry_path)!=CLEANED_SHA256:
        raise ValueError('Exact supplied source context required')
    data=read_json(dataset/'manifest.json');registry=read_json(registry_path);source=read_json(prepared/'manifest.json')
    if (data.get('scope')!='all_class_reference_replay_development_not_release'
            or data.get('diagnostic_only') is not True or len(data['classes'])!=129):
        raise ValueError('Expected frozen replay experiment')
    available={t['reference_id']:t for t in reference_page_targets(registry,data['reference_specification'],1)}
    if (not 1<=len(reference_ids)<=6 or len(set(reference_ids))!=len(reference_ids)
            or any(identity not in available for identity in reference_ids)):
        raise ValueError('Select bounded, explicit page-one reference identities')
    model=YOLO(str(checkpoint));validate_model_classes(model,data['classes']);rows=[]
    page=next(p for p in source['pages'] if p['page_number']==1);path=prepared/page['filename']
    if digest(path)!=page['image_sha256']:raise ValueError('Original reference image changed')
    with Image.open(path) as opened:original=opened.convert('RGB')
    items=[]
    for identity in reference_ids:
        target=available[identity]
        a,b,c,d=target['source_box']
        choices=[(x,y) for x,y in tile_positions(*original.size,dual_phase=True) if x<=a<c<=x+256 and y<=b<d<=y+256]
        if not choices:raise ValueError('No complete bounded reference tile')
        x,y=max(choices,key=lambda p:min(a-p[0],b-p[1],p[0]+256-c,p[1]+256-d))
        real=original.crop((x,y,x+256,y+256));local=[a-x,b-y,c-x,d-y]
        isolated=Image.new('RGB',(256,256),'white');isolated.paste(original.crop((a,b,c,d)),(a-x,b-y))
        trained=next(r for r in data['authored_legend_synthetic_images'] if r.get('reference_id')==identity and r['image_id'].endswith('-02'))
        trained_path=dataset/'images/train'/f"{trained['image_id']}.png"
        if digest(trained_path)!=trained['image_sha256']:raise ValueError('Training example changed')
        with Image.open(trained_path) as opened:synthetic=opened.convert('RGB')
        for kind,image,box in (('native_source_tile',real,local),('exact_source_glyph_on_white',isolated,local),
                               ('same_scale_training_composite',synthetic,trained['box'])):
            items.append((identity,kind,image,box,target['class_id']))
    output.mkdir(parents=True)
    for offset in range(0,len(items),2):
        batch=items[offset:offset+2]
        predictions=model.predict([item[2] for item in batch],imgsz=320,conf=.01,batch=2,device='cpu',verbose=False,max_det=200)
        for (identity,kind,image,box,cls),prediction in zip(batch,predictions):
            raw=[{'bbox':b.xyxy[0].tolist(),'class_id':int(b.cls[0]),'score':float(b.conf[0])} for b in prediction.boxes]
            overlapping=[r for r in raw if iou(box,r['bbox'])>=.50]
            expected=[r for r in overlapping if r['class_id']==cls]
            rows.append({'reference_id':identity,'kind':kind,'expected_class_id':cls,'expected_box':box,
                         'best_correct_overlap_score':max((r['score'] for r in expected),default=None),
                         'best_overlap':max(overlapping,key=lambda r:r['score'],default=None),'raw_predictions':raw})
            pen=ImageDraw.Draw(image);pen.rectangle(box,outline='green',width=1)
            for r in raw:pen.rectangle(r['bbox'],outline='orange',width=1)
            image.save(output/f"{identity}-{kind}.png");image.close()
    original.close()
    result={'kind':'paired_reference_context_raw_output_diagnostic','source_page_sha256':page['image_sha256'],
        'checkpoint_sha256':digest(checkpoint),'dataset_manifest_sha256':digest(dataset/'manifest.json'),
        'rows':rows,'raw_observation_threshold':.01,'unchanged_live_and_scored_threshold':.50,
        'independent_accuracy':None,'precision':None,'active_model_changed':False,
        'interpretation':'Target-guided technical inputs; not full-page evaluation, held-out evidence or model acceptance.'}
    (output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return [{k:r[k] for k in ('reference_id','kind','best_correct_overlap_score','best_overlap')} for r in rows]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','checkpoint','prepared','registry','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--mode',choices=('table','replay'),default='table')
    parser.add_argument('--page',type=int)
    parser.add_argument('--retention',type=Path)
    args=parser.parse_args()
    if args.mode=='replay':
        if args.retention is None or args.page is not None:parser.error('Replay requires retention dataset and no implicit page selection')
        result=replay_probe(args.dataset,args.checkpoint,args.prepared,args.registry,args.retention,args.output)
    else:
        if args.page is None:parser.error('Table probe requires explicit --page')
        result=table_probe(args.dataset,args.checkpoint,args.prepared,args.registry,args.output,page_number=args.page)
    print(json.dumps(result))
