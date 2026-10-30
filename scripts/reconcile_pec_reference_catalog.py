"""Source-bound reference/catalog reconciliation and full reference diagnostic.

No live catalog writes, project approvals, publisher certification or detector
activation. All requested device definitions remain traceable; wiring references
remain a separate task. New classes are explicitly reference-only, not inferred
engineering meanings or secretly approved production project classes.
"""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import re
import unicodedata

from PIL import Image

from prepare_pec_reference import (CLEANED_SHA256, PARENT_CHECKPOINT_SHA256,
    PARENT_DATASET_SHA256, PREPARED_SHA256, SOURCE_SHA256, digest, entries)
from prepare_authored_legend_extension import extend_head, synthetic_tile
from prepare_symbol_detector_dev import UNRESOLVED_REFERENCE_SHEETS


def read_json(path, limit=5_000_000):
    with Path(path).open('rb') as stream: raw=stream.read(limit+1)
    if len(raw)>limit: raise ValueError('Reference metadata exceeds allocation bound')
    return json.loads(raw)


def meaning_key(label):
    return ' '.join(unicodedata.normalize('NFKC',label).casefold().split())


def catalog_evidence(references, session, images):
    """Current reviewed records and original image identity, not file-name trust."""
    if not isinstance(references.get('legend_catalog'),list) or len(references['legend_catalog'])>1000:
        raise ValueError('Catalog exceeds reference bound')
    records={};pages={};identities=set()
    for sheet in session['sheets']:
        if sheet['id'] in pages: raise ValueError('Duplicate source sheet identity')
        pages[sheet['id']]=sheet
        for annotation in sheet.get('annotations',[]):
            if annotation['id'] in records: raise ValueError('Duplicate annotation identity')
            records[annotation['id']]=(sheet,annotation)
    eligible=[];excluded=[];verified={};reconciled=[]
    reference_pages={r['id']:r for r in references.get('sheets',[])}
    for entry in references['legend_catalog']:
        if entry['legend_entry'] in identities: raise ValueError('Duplicate catalog entry identity')
        identities.add(entry['legend_entry']);evidence=[]
        for example in entry.get('examples',[]):
            pair=records.get(example['source_annotation_id'])
            reason=None
            if pair is None: reason='source_annotation_missing'
            else:
                page,annotation=pair
                if annotation.get('review_state')!='user_reviewed':
                    reason='current_'+str(annotation.get('review_state'))
                elif annotation.get('deleted') or annotation.get('excluded'):
                    reason='explicitly_deleted_or_excluded'
                elif (annotation.get('layer')!='legend' or example.get('role')!='legend_definition'
                      or example['source_sheet_id']!=page['id']
                      or example['source_sha256']!=page['source_sha256']
                      or annotation.get('label')!=example['label']):
                    reason='source_annotation_identity_differs'
                else:
                    if page['id'] not in verified:
                        name=page['filename']
                        if Path(name).name!=name: raise ValueError('Source image path differs')
                        if not re.fullmatch(r'sheet-\d{2,4}',page['id']):
                            raise ValueError('Source sheet filename identity differs')
                        # Portable storage uses sheet-XX.jpg while the manifest
                        # preserves original names. Only the exact source hash
                        # plus dimensions can resolve that alias, never a guess.
                        names=[name]+[page['id']+suffix for suffix in ('.jpg','.jpeg','.png')]
                        candidates=[Path(images)/n for n in names]
                        matching=[p for p in candidates if p.is_file() and not p.is_symlink()
                            and p.stat().st_size<=25*1024*1024 and digest(p)==page['source_sha256']]
                        if not matching and page['id'] in UNRESOLVED_REFERENCE_SHEETS:
                            alias=reference_pages.get(page['id'],{}).get('image','')
                            alias_path=Path(images).parent/alias
                            path=alias_path.resolve()
                            boundary=(Path(images).parent/'references/additional').resolve()
                            if (alias and path.is_relative_to(boundary) and path.is_file() and not alias_path.is_symlink()
                                    and path.stat().st_size<=25*1024*1024 and digest(path)==page['source_sha256']):
                                matching=[path]
                        if not matching:
                            raise ValueError('Catalog source image changed')
                        path=matching[0].resolve()
                        if (path.parent!=Path(images).resolve() and page['id'] not in UNRESOLVED_REFERENCE_SHEETS):
                            raise ValueError('Source image path differs')
                        with Image.open(path) as opened:
                            if (max(opened.size)>10_000 or opened.width*opened.height>60_000_000
                                    or opened.size!=(page['width'],page['height'])):
                                raise ValueError('Catalog page dimensions differ')
                        verified[page['id']]={'source_sha256':page['source_sha256'],
                            'storage_filename':path.name,'declared_original_filename':name,
                            'pixel_training_eligible':page['id'] not in UNRESOLVED_REFERENCE_SHEETS}
                    geometry=annotation['geometry']
                    box=geometry.get('coordinates',[])
                    if (geometry.get('type')!='bbox' or len(box)!=4
                            or any(type(v) not in (int,float) or not math.isfinite(v) for v in box)
                            or not 0<=box[0]<box[2]<=page['width']
                            or not 0<=box[1]<box[3]<=page['height']):
                        reason='legend_box_invalid'
                    else:
                        current=deepcopy(example)
                        if geometry!=example['geometry']:
                            current['export_geometry']=deepcopy(example['geometry'])
                            current['geometry']=deepcopy(geometry)
                            current['reconciliation']='same_source_and_label_current_user_reviewed_geometry'
                            reconciled.append({'legend_entry':entry['legend_entry'],
                                'source_annotation_id':example['source_annotation_id'],
                                'export_geometry':example['geometry'],'current_reviewed_geometry':geometry})
                        evidence.append(current)
            if reason: excluded.append({'legend_entry':entry['legend_entry'],
                'source_annotation_id':example['source_annotation_id'],'reason':reason})
        if evidence: eligible.append({'legend_entry':entry['legend_entry'],
            'label':entry['label'],'examples':evidence,'review_basis':'existing_user_reviewed_source_record'})
    return {'eligible_entries':eligible,'excluded_examples':excluded,'verified_source_images':verified,
            'reconciled_geometry_examples':reconciled}


def write_catalog_audit(references,session,images,output):
    """New evidence revision, never rewrite a frozen training run or workspace."""
    output=Path(output)
    if output.exists(): raise FileExistsError('Catalog audit revisions are immutable')
    evidence=catalog_evidence(read_json(references,10_000_000),read_json(session,10_000_000),images)
    result={'schema':'ved-reference-catalog-reconciliation-v1','references_sha256':digest(references),
        'session_sha256':digest(session),'evidence':evidence,'workspace_changed':False,
        'scope':'reference_meaning_links_not_production_approval_or_source_pixel_training_permission',
        'human_review_claim':'existing_user_reviewed_records_not_assistant_review',
        'production_approval':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    return {'current_reviewed_catalog_entries':len(evidence['eligible_entries']),
        'excluded_examples':len(evidence['excluded_examples']),
        'reconciled_geometry_examples':len(evidence['reconciled_geometry_examples']),
        'audit_sha256':digest(output)}


def reference_label(row):
    identity=row['reference_id'];label=row['proposed_label']
    if identity.startswith('1.20.'): label='Outlet - '+label
    elif identity.startswith('1.21.'): label='Switch - '+label
    elif identity.startswith('1.36.'): label='Fire alarm - '+label
    return label+f' [reference {identity}]'


def reference_specification(registry, parent_classes, evidence):
    """Preserve parent IDs; give unmatched authored meanings source-scoped IDs."""
    if ({r['id'] for r in parent_classes}!=set(range(len(parent_classes)))
            or any(type(r['id']) is not int for r in parent_classes)):
        raise ValueError('Parent numeric identities differ')
    variants={}
    for row in registry['references']:
        variants.setdefault(row['reference_id'],[]).append(row)
    if set(variants)!={r['reference_id'] for r in entries()}: raise ValueError('Requested reference coverage differs')
    # Explicit, limited equivalence rules. Never strip ratings, mounting,
    # addressability, gang counts or material details to obtain a match.
    meanings={'1.22':'Junction box','1.23':'Pull box','1.26':'Circuit home-run notation',
        '1.35':'Telephone terminal cabinet','1.36.2':'Fire alarm control panel',
        '1.36.3':'Heat detector','1.36.5':'Smoke detector','1.20.19':'Telephone outlet',
        '1.21.4':'Two-pole switch (S2P)'}
    additions=[];mapping=[];wiring=[]
    for source_row in entries():
        identity=source_row['reference_id'];glyphs=variants[identity]
        if source_row['annotation_layer']=='wiring':
            wiring.append({'reference_id':identity,'label':source_row['proposed_label'],
                'annotation_layer':'wiring','model_class_id':None});continue
        aliases=glyphs[0]['mapped_model_class_ids']
        if any(g['mapped_model_class_ids']!=aliases for g in glyphs):
            raise ValueError('Variants disagree on existing class identity')
        if aliases:
            if any(type(i) is not int or i not in range(len(parent_classes)) for i in aliases):
                raise ValueError('Reference aliases do not exist in the parent head')
            class_id=min(aliases);model_label=parent_classes[class_id]['label']
        else:
            class_id=len(parent_classes)+len(additions);model_label=reference_label(source_row)
            # This is transfer initialization ONLY, not semantic equivalence.
            # Generic symbol features are reused; labels/approvals are not.
            additions.append({'id':class_id,'label':model_label,'seed_parent_class_id':23,
                'reference_id':identity,'initialization_basis':'generic_symbol_classifier_transfer_not_class_equivalence'})
        target=meanings.get(identity)
        links=[r for r in evidence['eligible_entries'] if target and meaning_key(r['label'])==meaning_key(target)]
        mapping.append({'reference_id':identity,'authored_label':source_row['proposed_label'],
            'annotation_layer':'symbols','model_class_id':class_id,'model_label':model_label,
            'existing_model_aliases':aliases,'glyph_ids':[g['glyph_id'] for g in glyphs],
            'catalog_links':[{'legend_entry':r['legend_entry'],'label':r['label'],
                'source_annotation_ids':[x['source_annotation_id'] for x in r['examples']]} for r in links],
            'catalog_mapping_state':'assistant_meaning_reconciliation' if links else 'reference_only_no_catalog_match',
            'project_mapping_state':'unresolved_until_drawing_legend_review',
            'production_approval':False,'human_review_claim':False,
            'real_layout_targets':0,'independent_real_examples':0})
    if len(mapping)!=54 or len(wiring)!=12:
        raise ValueError('Requested point/wiring coverage differs')
    return {'point_mappings':mapping,'wiring_references':wiring,'additions':additions,
        'new_class_scope':'authored_reference_definitions_only_not_project_approvals',
        'existing_numeric_head_count':len(parent_classes),'new_numeric_head_count':len(parent_classes)+len(additions)}


def build(cleaned, parent_manifest, checkpoint, references, session, images, output, *, examples=4):
    """Complete bounded reference diagnostic; no real-page or old-class claims."""
    from probe_symbol_detector_dev import validate_model_classes
    from ultralytics import YOLO
    paths=map(Path,(cleaned,parent_manifest,checkpoint,references,session,images,output))
    cleaned,parent_manifest,checkpoint,references,session,images,output=paths
    if output.exists(): raise FileExistsError('Reference-head revisions are immutable')
    if type(examples) is not int or not 4<=examples<=8: raise ValueError('Reference sampling exceeds bound')
    if (digest(cleaned/'manifest.json')!=CLEANED_SHA256 or digest(parent_manifest)!=PARENT_DATASET_SHA256
            or digest(checkpoint)!=PARENT_CHECKPOINT_SHA256):
        raise ValueError('Pinned reference, parent or checkpoint changed')
    registry=read_json(cleaned/'manifest.json');parent=read_json(parent_manifest)
    prepared=Path(registry['prepared_directory'])
    if digest(prepared/'manifest.json')!=PREPARED_SHA256 or digest(prepared/'original.pdf')!=SOURCE_SHA256:
        raise ValueError('Pinned supplied reference changed')
    source=read_json(prepared/'manifest.json')
    permission=read_json(prepared/'source-authorization.json')
    if (digest(prepared/'source-authorization.json')!=source['authorization_sha256']
            or permission.get('scope')!='local_development_only' or permission.get('human_review_claim') is not False
            or permission.get('production_approval') is not False or 'training' not in permission['allowed_purposes']):
        raise ValueError('Supplied-reference development permission changed')
    # Existing portable snapshots are 6.8/7.3 MB; keep their offline read bound
    # separate from the unchanged 5 MB model/dataset manifest bound.
    evidence=catalog_evidence(read_json(references,10_000_000),read_json(session,10_000_000),images)
    spec=reference_specification(registry,parent['classes'],evidence)
    glyphs={r['glyph_id']:r for r in registry['references']}
    if len(glyphs)!=74: raise ValueError('Reference variants differ')
    for row in glyphs.values():
        if (Path(row['filename']).name!=row['filename'] or digest(cleaned/row['filename'])!=row['glyph_sha256']
                or row['human_review_claim'] is not False or row['production_approval'] is not False):
            raise ValueError('Source glyph or review identity changed')
    # Preflight all size/placement limits before creating a head or output files.
    for row in glyphs.values():
        if row['annotation_layer']=='wiring': continue
        with Image.open(cleaned/row['filename']) as raw:
            if max(raw.size)>512: raise ValueError('Reference glyph exceeds bounds')
            for index in range(4):
                composite,_=synthetic_tile(raw,index,random.Random(0));composite.close()
    loaded=YOLO(str(checkpoint));validate_model_classes(loaded,parent['classes'])
    extend_head(loaded.model,spec['additions'])
    loaded.ckpt['ema']=None;loaded.ckpt['optimizer']=None
    output.mkdir(parents=True);(output/'images/train').mkdir(parents=True);(output/'labels/train').mkdir(parents=True)
    loaded.save(output/'initialized-head.pt')
    authority={'schema':'ved-user-authorized-development-label-preparation-v1',
        'source_sha256':SOURCE_SHA256,'prepared_manifest_sha256':PREPARED_SHA256,
        'local_development_training':True,'delegated_assistant_annotation':True,
        'human_review_claim':False,'production_approval':False,'user_statement':permission['user_statement'],
        'scope':'all_requested_reference_definitions_synthetic_diagnostic_only',
        'missing_annotation_policy':'ignore_unreviewed_not_empty_background',
        'project_group_id':permission['project_group_id'],'targets':[],
        'rights_evidence':permission['rights_evidence']}
    (output/'reference-development-authorization.json').write_text(json.dumps(authority,indent=2),encoding='utf-8')
    classes=deepcopy(parent['classes'])+[{'id':r['id'],'label':r['label'],
        'legend_entry':f"reference-{SOURCE_SHA256[:12]}:{r['reference_id']}",
        'source_reference_examples':1,'real_page_reviewed_targets':0} for r in spec['additions']]
    data={'kind':'positive_only_masked_symbol_detection_diagnostic_v1','diagnostic_only':True,
        'all_eligible_entries':False,'required_loss':'synthetic_complete_known_composite_only',
        'synthetic_complete_background':True,'base_model_sha256':digest(output/'initialized-head.pt'),
        'parent_dataset_sha256':digest(parent_manifest),'parent_checkpoint_sha256':digest(checkpoint),
        'reference_registry_sha256':CLEANED_SHA256,'classes':classes,'class_agnostic':False,
        'reviewed_targets':[],'reviewed_background_images':[],'images':[],'authored_legend_synthetic_images':[],
        'additional_training_authorizations':[{'filename':'reference-development-authorization.json',
            'sha256':digest(output/'reference-development-authorization.json'),
            'source_sha256':SOURCE_SHA256,'prepared_manifest_sha256':PREPARED_SHA256}],
        'reference_specification':spec,'catalog_evidence':evidence,'catalog_snapshot_sha256':digest(references),
        'catalog_session_sha256':digest(session),'new_real_page_reviewed_targets':0,
        'new_real_world_independent_examples':0,'production_approval':False,
        'scope':'full_requested_reference_learning_diagnostic_not_universal_detector_release',
        'warnings':['All 54 point definitions included; 12 wiring patterns excluded from point-device labels.',
            'Old numeric IDs preserved but 75 old classes unsupervised here: never activate this checkpoint.',
            'No independent validation; training-resubstitution only. Old-class/full-page regression pending.',
            'New classes are authored reference meanings, not approved drawing-specific project mappings.']}
    rng=random.Random(20261005)
    for mapping in spec['point_mappings']:
        for identity in mapping['glyph_ids']:
            row=glyphs[identity]
            with Image.open(cleaned/row['filename']) as raw:
                for index in range(examples):
                    image,box=synthetic_tile(raw,index%4,rng)
                    name=f"authored-legend-pec-{mapping['model_class_id']}-{identity}-{index:02d}"
                    ip=output/'images/train'/f'{name}.png';lp=output/'labels/train'/f'{name}.txt'
                    image.save(ip);image.close();x1,y1,x2,y2=box
                    lp.write_text(f"{mapping['model_class_id']} {(x1+x2)/512:.8f} {(y1+y2)/512:.8f} {(x2-x1)/256:.8f} {(y2-y1)/256:.8f}\n")
                    data['authored_legend_synthetic_images'].append({'image_id':name,'class_id':mapping['model_class_id'],
                        'legend_entry':f"reference-{SOURCE_SHA256[:12]}:{row['reference_id']}:{row['variant']}",
                        'reference_id':row['reference_id'],'variant':row['variant'],'glyph_sha256':row['glyph_sha256'],
                        'box':box,'image_sha256':digest(ip),'label_sha256':digest(lp),
                        'label_origin':'known_synthetic_composite_geometry','human_review_claim':False,
                        'source_sha256':SOURCE_SHA256,'source_reference_examples':1,'split':'train',
                        'augmentation':'native_orientation_isotropic_scale_known_composite_placement',
                        'independent_example':False})
    for row in classes:
        row['samples']=sum(s['class_id']==row['id'] for s in data['authored_legend_synthetic_images'])
    (output/'manifest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    with (output/'data.yaml').open('x',encoding='utf-8') as stream:
        stream.write(f'path: {output.resolve().as_posix()}\ntrain: images/train\nval: images/train\nnames:\n')
        for row in classes:
            label=unicodedata.normalize('NFKD',row['label']).encode('ascii','ignore').decode()
            stream.write(f"  {row['id']}: {json.dumps(label)}\n")
    return {'requested_point_entries':54,'wiring_reference_entries':12,'synthetic_images':len(data['authored_legend_synthetic_images']),
        'numeric_head_classes':len(classes),'new_reference_only_classes':len(spec['additions']),
        'catalog_linked_reference_entries':sum(bool(r['catalog_links']) for r in spec['point_mappings']),
        'current_reviewed_catalog_entries':len(evidence['eligible_entries']),
        'excluded_catalog_examples':len(evidence['excluded_examples']),
        'manifest_sha256':digest(output/'manifest.json'),'production_approval':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('build','audit'),default='build')
    for name in ('cleaned','parent-manifest','checkpoint','references','session','images','output'):
        parser.add_argument('--'+name,type=Path,required=name in ('references','session','images','output'))
    parser.add_argument('--examples',type=int,default=4)
    args=parser.parse_args()
    if args.mode=='audit': result=write_catalog_audit(args.references,args.session,args.images,args.output)
    else:
        if args.cleaned is None or args.parent_manifest is None or args.checkpoint is None:
            parser.error('--cleaned, --parent-manifest and --checkpoint required for build')
        result=build(args.cleaned,args.parent_manifest,args.checkpoint,args.references,args.session,args.images,args.output,examples=args.examples)
    print(json.dumps(result))
