"""One pinned local development detector; not a promoted release.

Names are never used to merge drawing-specific IDs. Prior experimental jobs
retain their old providers; new development uploads use this shared checkpoint.
"""
from functools import lru_cache
from hashlib import sha256
import json
import os
import re
import unicodedata

from app.core.config import REPOSITORY_ROOT, get_settings
from app.ai.floor_plan_interpretation import experimental_symbol_detector as shared
from app.ai.floor_plan_interpretation.legend_equivalence import EQUIVALENCE_REVISION, model_class_groups
from app.ai.floor_plan_interpretation.orientation_consensus import CONFIGURATION as ORIENTATION_CONFIGURATION

PROVIDER = "development_multiclass56_yolo"
LEGACY_CHECKPOINT = REPOSITORY_ROOT / "storage/training/symbol-quality-20260929-run3/weights/best.pt"
LEGACY_CHECKPOINT_SHA256 = "5951c7375bed147244e36cbd93bfdd6ecc8ab3942b0a96fa842363ea087efa22"
LEGACY_DATASET = REPOSITORY_ROOT / "storage/training/symbol-quality-20260929-v2/manifest.json"
LEGACY_DATASET_SHA256 = "26c3dcc6a843e110f4ed373ba2abbf15d0261d70ecbe6dd1fba1d91410c10d37"
PROFILE = get_settings().development_symbol_profile
PROFILES = {
    'original56': {
        'checkpoint': LEGACY_CHECKPOINT,
        'checkpoint_sha256': LEGACY_CHECKPOINT_SHA256,
        'base_sha256': '2c46051a30673d1fcee9255b7890ef9c2a5ff9481073b06bb4e419c0c272dafc',
        'prompt': 'reviewed-background-56-detector-v3',
        'dataset': LEGACY_DATASET,
        'dataset_sha256': LEGACY_DATASET_SHA256,
        'class_count': 56,
    },
    'lamps80': {
        'checkpoint': REPOSITORY_ROOT / 'storage/training/switch-real-20261004-run3/weights/last.pt',
        'checkpoint_sha256': '867c7fb399104bf91caff1d6aad859504cc923443cb3e02fcb2b00255b2affa2',
        'base_sha256': 'cb2271b6ccccd8f03fb221f12a2fe6bec7bf6eedbf5b031b7f6d29e93e03c1f6',
        'prompt': 'partial-label-80-switch-replay-v2',
        'dataset': REPOSITORY_ROOT / 'storage/training/switch-real-20261004-v2/manifest.json',
        'dataset_sha256': '11ef819e20b120ea1bb44e08a64822f820f2f575c7c76212d5043f2b6249f527',
        'class_count': 80,
    },
    'power80': {
        'checkpoint': REPOSITORY_ROOT / 'storage/training/power-quality-20261007-tail-contrast-v12/weights/last.pt',
        'checkpoint_sha256': '2800866028ff65f5828b1e592542a3b09a08c15ad4ac7e657f4ade849b856aaa',
        'base_sha256': 'd68595066681238fa3cfaf612a1e3f30a9b5232b1ed343bf93ced9da43b49477',
        'prompt': 'partial-label-80-native-anchor-ridge16-fusion-v12',
        # Identical decoded JSON, compacted separately; original training bytes stay frozen.
        'dataset': REPOSITORY_ROOT / 'storage/training/power-quality-20261007-column-v5/serving-manifest-column-v5.json',
        'dataset_sha256': '7182de3a9b8616df8d01b8a204b085f95841a40d2740f2239183b8892e763c30',
        'training_dataset_sha256': '286ebf9ec56ffda32d39f73d04f65058c2bad9e99544de6fcc26c4005ffc5470',
        'refinement_manifest': REPOSITORY_ROOT / 'storage/training/power-quality-20261007-tail-contrast-v12/run-manifest.json',
        'refinement_manifest_sha256': 'b409bef77ca13c3b1c9a25791d54369045ddad4dc7fc60d00c5acd5967456476',
        'class_count': 80,
    },
}
_profile = PROFILES[PROFILE]
CHECKPOINT = _profile['checkpoint']
CHECKPOINT_SHA256 = _profile['checkpoint_sha256']
TRAINING_BASE_SHA256 = _profile['base_sha256']
PROMPT_VERSION = _profile['prompt']
DATASET = _profile['dataset']
DATASET_SHA256 = _profile['dataset_sha256']
TRAINING_DATASET_SHA256 = _profile.get('training_dataset_sha256', DATASET_SHA256)
REFINEMENT_MANIFEST = _profile.get('refinement_manifest')
REFINEMENT_MANIFEST_SHA256 = _profile.get('refinement_manifest_sha256')
THRESHOLD = .50  # uncalibrated detector score; original configurable legacy path unchanged
CLASS_COUNT = _profile['class_count']
DENSE_LIGHTING_POLICY = 'native-context320-stride160-lighting-majority-v1'
AUTHORED_SOURCE_SHA256 = 'efa570519f08bc3596d443fcc63c96ddd6bf73039bcba7ed3e52881d0943d9af'
EXTENSION_IDENTITIES = (
    ('2 x 40 watts fluorescent lamp','pdf-efa570519f08:p7:L02'),
    ('1 x 40 watts fluorescent lamp','pdf-efa570519f08:p7:L07'),
    ('Duplex convenience outlet, grounding type, 10 amps, 250 volt with modern plate cover','pdf-efa570519f08:p7:L12'),
    ('Weatherproof type duplex convenience outlet, grounding type, 10 amps, 250 volt with modern plate cover','pdf-efa570519f08:p7:L13'),
)
EXPANDED_PARENT_DATASET = REPOSITORY_ROOT / 'storage/training/elect-20261004-v2/manifest.json'
EXPANDED_PARENT_SHA256 = '7440bc96c6e6a033060277c21234cf9456a724cc0fdad9f4db39533c280d3ec9'


def validate_replay_extension(data):
    """80-entry compatibility, not a detection-quality acceptance gate."""
    if (data.get('diagnostic_only') or data.get('class_scope')!='parent60_plus_twenty_pdf_source_definitions'
            or shared._digest(EXPANDED_PARENT_DATASET,5_000_000)!=EXPANDED_PARENT_SHA256):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')
    parent=json.loads(EXPANDED_PARENT_DATASET.read_text(encoding='utf-8'))
    identity=lambda rows:[(r['id'],r['label'],r['legend_entry']) for r in rows]
    if (identity(data['classes'])!=identity(parent['classes'])
            or data.get('reviewed_targets')!=parent.get('reviewed_targets')
            or data.get('images')!=parent.get('images')
            or data.get('authored_legend_synthetic_images')!=parent.get('authored_legend_synthetic_images')
            or data.get('authorized_pdf_targets',[])[:len(parent['authorized_pdf_targets'])]!=parent['authorized_pdf_targets']):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')
    for record in data.get('additional_training_authorizations',[]):
        path=DATASET.parent/record['filename']
        if path.parent!=DATASET.parent or shared._digest(path,1_048_576)!=record['sha256']:
            raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')
        auth=json.loads(path.read_text(encoding='utf-8'))
        if (auth.get('source_sha256')!=record['source_sha256']
                or auth.get('prepared_manifest_sha256')!=record['prepared_manifest_sha256']
                or auth.get('schema')!='ved-user-authorized-development-label-preparation-v1'
                or auth.get('local_development_training') is not True
                or auth.get('delegated_assistant_annotation') is not True
                or auth.get('human_review_claim') is not False or auth.get('production_approval') is not False
                or auth.get('missing_annotation_policy')!='ignore_unreviewed_not_empty_background'):
            raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')
    if not data.get('additional_training_authorizations'):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')


def validate_extension(data):
    if (data.get('diagnostic_only') or data.get('class_scope') != 'parent56_plus_four_authored_lamp_and_outlet_definitions'
            or data.get('parent_dataset_sha256') != LEGACY_DATASET_SHA256
            or data.get('authored_source_sha256') != AUTHORED_SOURCE_SHA256
            or data.get('source_approval_kind') != 'user_attested_source_permission'
            or data.get('new_real_page_reviewed_targets') != 0
            or data.get('synthetic_complete_background') is not True
            or shared._digest(LEGACY_DATASET,5_000_000) != LEGACY_DATASET_SHA256):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')
    parent=json.loads(LEGACY_DATASET.read_text(encoding='utf-8'))
    original=[(r['id'],r['label'],r['legend_entry']) for r in parent['classes']]
    actual=[(r['id'],r['label'],r['legend_entry']) for r in data['classes'][:56]]
    extension=[(r['label'],r['legend_entry']) for r in data['classes'][56:]]
    if actual != original or extension != list(EXTENSION_IDENTITIES):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_EXTENSION_INVALID')


def verify_refinement_artifact():
    if REFINEMENT_MANIFEST is None:
        return
    if shared._digest(REFINEMENT_MANIFEST,1_048_576) != REFINEMENT_MANIFEST_SHA256:
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_REFINEMENT_INTEGRITY_FAILED')
    data=json.loads(REFINEMENT_MANIFEST.read_text(encoding='utf-8'))
    invariants=data.get('invariants',{})
    if (data.get('kind')!='local_development_symbol_detector_diagnostic'
            or data.get('base_sha256')!=TRAINING_BASE_SHA256
            or data.get('checkpoint_sha256')!=CHECKPOINT_SHA256
            or data.get('dataset_manifest_sha256')!=TRAINING_DATASET_SHA256
            or data.get('production_approval') is not False or data.get('activation') is not False
            or data.get('diagnostic_only') is not True
            or data.get('native_positive_controls') is not True
            or data.get('contrast_settings')!={'positive_penalty':16,'ridge':1,'negative_training_target':.1,
                'unknown_anchor_policy':'ignored','max_abs_parameter_delta':1}
            or invariants.get('updated_class')!=58 or invariants.get('trainable_scalars')!=243
            or invariants.get('other_state_exact') is not True
            or invariants.get('serialized_and_reloaded_other_state_exact') is not True):
        raise shared.ExperimentalDetectorUnavailable('MULTICLASS_REFINEMENT_CONTRACT_INVALID')


def verify_artifacts():
    if (shared._digest(CHECKPOINT, 30_000_000) != CHECKPOINT_SHA256
            or shared._digest(DATASET, 5_000_000) != DATASET_SHA256):
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_MODEL_INTEGRITY_FAILED")
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rows = data.get("classes", [])
    if (data.get("all_eligible_entries") is not True
            or data.get("required_loss") not in {"positive_and_reviewed_box_only",
                                                 "positive_boxes_and_explicit_reviewed_background"}
            or CLASS_COUNT not in (56,60,80)
            or len(rows) != CLASS_COUNT or {r["id"] for r in rows} != set(range(CLASS_COUNT))
            or len({r["legend_entry"] for r in rows}) != CLASS_COUNT
            or any(r["samples"] < 1 for r in rows)
            or data.get("reference_rights_exclusions", {}).get("sheet_ids") != ["sheet-51", "sheet-52"]):
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_CLASS_MAP_INVALID")
    if CLASS_COUNT == 60:
        validate_extension(data)
    elif CLASS_COUNT == 80:
        validate_replay_extension(data)
    verify_refinement_artifact()
    return {row["id"]: (row["label"], row["legend_entry"]) for row in rows}


def configuration_sha256():
    from app.ai.floor_plan_interpretation.pdf_evidence import VERSION as pdf_version
    from app.ai.floor_plan_interpretation.pdf_views import VERSION as view_version
    from app.ai.floor_plan_interpretation.pdf_wall_evidence import VERSION as wall_version
    from app.ai.floor_plan_interpretation.pdf_wall_recognition import VERSION as native_wall_version
    from app.ai.floor_plan_interpretation.pdf_observed_wiring import VERSION as native_wiring_version
    from app.ai.floor_plan_interpretation.scoped_analysis import VERSION as pipeline_version, raster_configuration_versions
    return sha256(json.dumps({"provider": PROVIDER, "profile": PROFILE, "class_count":CLASS_COUNT,
        "pdf_pipeline": {"source_evidence":pdf_version,"view_scopes":view_version,"wall_evidence":wall_version,
                         "wall_recognition":native_wall_version,"wiring_recognition":native_wiring_version,"orchestration":pipeline_version},
        "checkpoint": CHECKPOINT_SHA256,
        "raster_pipeline": raster_configuration_versions(),
        "dataset": DATASET_SHA256,
        **({"training_dataset": TRAINING_DATASET_SHA256} if PROFILE == 'power80' else {}),
        **({"refinement_manifest": REFINEMENT_MANIFEST_SHA256,
            "refinement": "reviewed-native-anchor-ridge16-v12"} if REFINEMENT_MANIFEST_SHA256 else {}),
        **({"dense_lighting_localization": {"policy": DENSE_LIGHTING_POLICY,
            "minimum_fixture_observations":8,"minimum_physical_device_fraction":.70,
            "detail_tile":320,"detail_stride":160,"total_window_cap":shared.MAX_TILES},
            "orientation_consensus": ORIENTATION_CONFIGURATION,
            "plan_region_filter":"source-centre-v1",
            "fixture_wall_conflicts":"two-central-ceiling-fixtures-v1",
            "coordinate_fusion": "best-two-same-class-v1", "internal_seam_fragment":
            {"edge_pixels":4,"overlap_fraction":.4,"fragment_to_complete_area_min":.25,
             "complete_observation_required":True}, "alias_evidence":"score-warning-with-batched-references-v2"}
           if PROFILE == 'power80' else {}),
        "threshold": THRESHOLD,
        "tile": shared.TILE_SIZE, "stride": shared.TILE_STRIDE, "model_input": 320,
        "second_grid_offset": 128, "second_grid_policy": "only if total within existing 500-window cap",
        "batch": 8,
        "nms": shared.NMS_IOU, "max_tiles": shared.MAX_TILES,
        "nested_nms": {"intersection_over_smaller":.85,"center_tolerance_short_edge_fraction":.5},
        "equivalent_class_fusion": EQUIVALENCE_REVISION,
        "max_candidates": shared.MAX_CANDIDATES}, sort_keys=True).encode()).hexdigest()


@lru_cache(maxsize=1)
def _model():
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    from ultralytics import YOLO
    classes = verify_artifacts()
    model = YOLO(str(CHECKPOINT))
    expected = {i: unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
                for i, (label, _) in classes.items()}
    if model.names != expected:
        raise shared.ExperimentalDetectorUnavailable("MULTICLASS_CHECKPOINT_HEAD_INVALID")
    # The manifest is hash-bound to the head's numeric identities. Duplicate
    # visible wording does not collapse drawing-specific model outputs.
    return model


def locate(rgb):
    classes = verify_artifacts()
    catalog={"classes": classes, "threshold": THRESHOLD, "model": _model(),
             "class_groups": model_class_groups(classes),"box_fusion": PROFILE == 'power80'}
    if PROFILE == 'power80':
        from app.ai.floor_plan_interpretation.orientation_consensus import locate_orientation_consensus
        diagnostics={}
        rows,truncated=locate_orientation_consensus(rgb, lambda image: _locate_context(image,catalog,classes),
                                                    catalog['class_groups'], diagnostics=diagnostics)
        return tuple({**row,**({'orientation_assessment':diagnostics} if diagnostics else {})} for row in rows),truncated
    return _locate_context(rgb,catalog,classes)


def _locate_context(rgb,catalog,classes):
    baseline,truncated=shared.locate(rgb,catalog=catalog)
    physical=[p for p in baseline if not re.search(r'home.?run|circuit.*notation',classes[p['class_id']][0],re.I)]
    fixtures=[p for p in physical if re.search(r'troffer|fluorescent|downlight|lighting point|light point',
                                              classes[p['class_id']][0],re.I)]
    # Content-based context adaptation, never filename/sheet coordinates or a
    # lower score cutoff. Native 320px crops keep small glyph context without
    # the ordinary 256→320 enlargement on dense gridded lighting drawings.
    # Keep broad contextual localization for power/mixed pages and rollback heads.
    if PROFILE=='power80' and len(fixtures)>=8 and len(fixtures)>=len(physical)*.70:
        height,width=rgb.shape[:2]
        standard=shared.tile_positions(width,height,dual_phase=True)
        detail=shared.tile_positions(width,height,dual_phase=True,tile_size=320,stride=160)
        if len(standard)+len(detail)<=shared.MAX_TILES:
            return shared.locate(rgb,catalog={**catalog,'tile_size':320,'tile_stride':160})
    return baseline,truncated


def with_proposals(payload, predictions, truncated=False):
    classes=verify_artifacts()
    # Overview inference sees the full page; only drawing-region observations
    # belong in the editable device collection (titles/legends are not devices).
    regions=[r.bounds for r in payload.regions if r.kind=='plan_region']
    if regions and PROFILE=='power80':
        predictions=tuple(row for row in predictions if any(
            region.x<=(row['bbox'][0]+row['bbox'][2])/2<=region.x+region.width
            and region.y<=(row['bbox'][1]+row['bbox'][3])/2<=region.y+region.height for region in regions))
    result=shared.with_trained_symbol_proposals(payload, predictions, truncated,
        catalog={"classes": classes,"dataset_sha256": TRAINING_DATASET_SHA256,
                 "alias_evidence_in_score":PROFILE=='power80'})
    from app.ai.floor_plan_interpretation.candidate import CandidateWarning
    assessment=next((row['orientation_assessment'] for row in predictions if row.get('orientation_assessment')),None)
    if assessment and len(result.warnings)<256:
        result=result.model_copy(update={'warnings':result.warnings+(CandidateWarning(
            code='symbol_orientation_assessment',severity='info',
            message='Bounded quarter-turn inference; one coherent view selected, not a union. '
                    'Agreement ranking is not calibrated confidence or approval: '
                    +json.dumps(assessment,separators=(',',':'))),)})
    alias_refs = tuple(f'symbol:symbol-{index:04d}' for index,row in enumerate(predictions,start=1)
                       if row.get('equivalent_observations'))
    # Evidence is preserved once in each symbol's existing score warning.
    # Bounded marker groups avoid 200 extra warnings exceeding the strict 256 cap.
    alias_warnings = tuple(CandidateWarning(code='equivalent_legend_observations',severity='info',
        entity_refs=alias_refs[offset:offset+64],
        message='Co-located equivalent legend observations fused, not approved. Winning IDs, '
            'source legend entries and every raw observation are preserved in the referenced '
            'symbols\' experimental_detector_score warnings.') for offset in range(0,len(alias_refs),64)) if PROFILE=='power80' else tuple(
        CandidateWarning(code='equivalent_legend_observations',severity='info',
            entity_refs=(f'symbol:symbol-{index:04d}',),
            message='Co-located equivalent legend observations fused, not approved. Winning model ID '
                +str(row['class_id'])+'; preserved source entries and raw observations: '
                +json.dumps([{'legend_entry':classes[o['class_id']][1],**o}
                             for o in row['equivalent_observations']],separators=(',',':')))
        for index,row in enumerate(predictions,start=1) if row.get('equivalent_observations'))
    if alias_warnings:
        result=result.model_copy(update={'warnings':result.warnings+alias_warnings})
    names={name for name,_ in classes.values()}
    if not {name for name,_ in EXTENSION_IDENTITIES[:2]} <= names:
        from app.ai.floor_plan_interpretation.candidate import CandidateWarning
        warning=CandidateWarning(code='fluorescent_lamp_classes_unavailable',severity='warning',
            message='This running checkpoint does not include the authored 1 x 40 W and 2 x 40 W fluorescent-lamp classes. Catalog import does not train or activate weights. Smoke-detector proposals on lamp layouts may be misclassifications; inspect the drawing legend and correct them. Do not interpret these proposals as reliable lamp detection.')
        result=result.model_copy(update={'warnings':result.warnings+(warning,)})
    elif PROFILE == 'power80':
        warning=CandidateWarning(code='experimental_eighty_entry_checkpoint',severity='warning',
            message='Shared experimental 80-entry development YOLO, not VLM or production. '
                'Same-source power checks at score .50 / IoU .50: 12/12 inspected outlets, '
                'one panelboard and three homeruns at native and .375 scale; zero proposals '
                'inside 15 inspected non-device patches, including the hatched column. '
                'Only the outlet-class tail was refined using reviewed native-context '
                'anchors; other class rows, BN and box heads stayed unchanged. Original '
                'guarded-fusion training-source replay: 806/830 versus fresh active baseline '
                '800/830; no capped pages. Switch checks 3/4, 9/9 and 9/9; lamps 20/20 '
                'on the PDF view. These are development evidence, '
                'not full-page precision or independent accuracy. All proposals need review.')
        result=result.model_copy(update={'warnings':result.warnings+(warning,)})
    elif CLASS_COUNT == 80:
        from app.ai.floor_plan_interpretation.candidate import CandidateWarning
        warning=CandidateWarning(code='experimental_eighty_entry_checkpoint',severity='warning',
            message='Shared experimental 80-entry development YOLO, not VLM or production. Recorded pre-fusion training-source checks: switches PDF 9/9, derivative 8/9, other PDF 3/4; lamps 20/20 in both related views. Seventeen entries have no real source boxes. Original replay: 802/830 versus recorded 806/830 baseline; three pages capped. Equivalent complete meanings now share spatial fusion; source IDs remain preserved. Precision and independent accuracy unverified. All proposals need review.')
        result=result.model_copy(update={'warnings':result.warnings+(warning,)})
    # model_copy is not validation; enforce warning/text/reference bounds after additions.
    return type(result).model_validate(result.model_dump())
