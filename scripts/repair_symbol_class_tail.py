"""Bounded frozen-feature class-row diagnostic; never changes a serving profile.

Not generalization evidence. Only explicitly inspected negative windows and
known positive boxes supervise this run; every unknown region stays ignored.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ['YOLO_OFFLINE'] = 'true'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import cv2
import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.nn import functional as F


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class FrozenClassTailRepair:
    """Optimize separate row tensors; no backbone/BN/box optimizer exists."""
    def __init__(self, model, class_id):
        head = model.model[-1]
        if (type(class_id) is not int or not 0 <= class_id < head.nc
                or getattr(head, 'end2end', False) or len(head.cv3) != 3):
            raise ValueError('Unsupported class or detection head')
        self.tails = [branch[-1] for branch in head.cv3]
        if any(not isinstance(t, nn.Conv2d) or t.out_channels != head.nc
               or t.kernel_size != (1, 1) or t.groups != 1 or t.bias is None for t in self.tails):
            raise ValueError('Expected three ordinary 1x1 class tails')
        self.model, self.head, self.class_id = model, head, class_id
        self.before = {k: v.detach().clone() for k, v in model.state_dict().items()}
        self.tail_names = [name for t in self.tails for name, layer in model.named_modules() if layer is t]
        if len(self.tail_names) != 3:
            raise ValueError('Ambiguous tail ownership')
        model.eval().requires_grad_(False)
        self.rows = [nn.Parameter(t.weight[class_id:class_id+1].detach().clone()) for t in self.tails]
        self.biases = [nn.Parameter(t.bias[class_id:class_id+1].detach().clone()) for t in self.tails]

    def parameters(self):
        return self.rows + self.biases

    def cache(self, images):
        if (images.ndim != 4 or images.shape[1:] != (3, 320, 320) or not 1 <= len(images) <= 8
                or not torch.isfinite(images).all() or images.min() < 0 or images.max() > 1):
            raise ValueError('Images exceed fixed local cache bounds')
        features, handles = [], []
        self.model.eval()
        self.head.training = True  # Raw outputs only; every BN remains eval.
        try:
            for tail in self.tails:
                handles.append(tail.register_forward_pre_hook(lambda _, args: features.append(args[0].detach().clone())))
            with torch.no_grad():
                output = self.model(images)
            if (not isinstance(output, dict) or len(features) != 3
                    or output['scores'].shape[1] != self.head.nc):
                raise ValueError('Unexpected raw detection output')
            return {'boxes': output['boxes'].detach(), 'scores': output['scores'].detach(),
                    'feats': [torch.empty(len(images), 1, *f.shape[2:]) for f in output['feats']],
                    'tail_features': features}
        finally:
            for handle in handles:
                handle.remove()
            self.head.training = False

    def predictions(self, cached):
        row = torch.cat([F.conv2d(f, w, b).flatten(2)
                         for f, w, b in zip(cached['tail_features'], self.rows, self.biases)], dim=2)
        k = self.class_id
        scores = torch.cat((cached['scores'][:, :k], row, cached['scores'][:, k+1:]), dim=1)
        return {**cached, 'scores': scores}

    def verify_protected(self, model):
        protected = {name + suffix for name in self.tail_names for suffix in ('.weight', '.bias')}
        after = model.state_dict()
        if set(after) != set(self.before):
            raise ValueError('Frozen state keys changed')
        for name, original in self.before.items():
            current = after[name]
            if name in protected:
                mask = torch.arange(len(original)) != self.class_id
                equal = torch.equal(original[mask], current[mask])
            else:
                equal = torch.equal(original, current)
            if current.dtype != original.dtype or not equal:
                raise ValueError('Frozen state changed: ' + name)

    def apply(self):
        with torch.no_grad():
            for tail, row, bias in zip(self.tails, self.rows, self.biases):
                tail.weight[self.class_id:self.class_id+1].copy_(row)
                tail.bias[self.class_id:self.class_id+1].copy_(bias)
        self.verify_protected(self.model)
        return {'protected_state_entries': len(self.before), 'updated_class': self.class_id,
                'trainable_scalars': sum(p.numel() for p in self.parameters()), 'other_state_exact': True}


def selected_windows(dataset, data, inspection, class_id):
    negatives = [r for r in data['reviewed_background_images'] if any(
        r.get('box') == region['box'] and r.get('source_sha256') == inspection['source_sha256']
        for region in inspection['background_regions'])]
    positives = [r for r in data['authorized_pdf_training_images'] if r.get('primary_class_id') == class_id]
    # Evenly spaced original windows, not copies counted as new real examples.
    positives = [positives[i] for i in np.linspace(0, len(positives)-1, min(32, len(positives)), dtype=int)]
    if not negatives or not positives or len(negatives) + len(positives) > 64:
        raise ValueError('Bounded inspected-negative and real-positive subset required')
    selected = [(r, True) for r in negatives] + [(r, False) for r in positives]
    for row, negative in selected:
        name = row['image_id']
        if Path(name).name != name:
            raise ValueError('Invalid image identity')
        image, label = dataset/'images/train'/f'{name}.png', dataset/'labels/train'/f'{name}.txt'
        if digest(image) != row.get('sha256', row.get('image_sha256')):
            raise ValueError('Training image hash changed')
        if negative and label.read_text().strip():
            raise ValueError('Inspected negative has labels')
        if not negative and digest(label) != row['label_sha256']:
            raise ValueError('Positive label hash changed')
    return selected


def native_context_windows(prepared, data, inspection, *, positive_controls=False):
    """Select by inspected-region overlap, not by a predicted target location."""
    from prepare_power_quality_replay import checked_inspection, validate_power_source
    from app.ai.floor_plan_interpretation.experimental_symbol_detector import tile_positions
    source, region, image_path = validate_power_source(prepared, inspection)
    with Image.open(image_path) as opened:
        targets, negatives = checked_inspection(inspection, data, source, region, opened.size)
        if targets:
            raise ValueError('Native-context diagnostic requires negative-only inspection revision')
        if opened.width*opened.height > 60_000_000:
            raise ValueError('Source allocation bound exceeded')
        rows = []
        positions=tile_positions(opened.width, opened.height, dual_phase=True)
        controls=set()
        positives=[r for r in data.get('power_source_targets',[]) if r['class_id']==58
                   and r.get('source_sha256')==region['crop_sha256']
                   and r.get('pdf_sha256')==source['source_sha256']]
        if positive_controls:
            for target in positives:
                a,b,c,d=target['source_box']
                contained=[(x,y) for x,y in positions if x<=a<c<=x+256 and y<=b<d<=y+256]
                # Two best-contained lattice views, selected by annotation
                # geometry, never by prediction score or detection success.
                contained.sort(key=lambda p:(-min(a-p[0],b-p[1],p[0]+256-c,p[1]+256-d),p))
                controls.update(contained[:2])
            if not positives:raise ValueError('Existing reviewed outlet controls required')
        for x,y in positions:
            masks=[]
            for negative in negatives:
                a,b,c,d=negative['box']; intersection=[max(a,x),max(b,y),min(c,x+256),min(d,y+256)]
                if (intersection[2]-intersection[0] >= 8 and intersection[3]-intersection[1] >= 8):
                    masks.append([(intersection[0]-x)*1.25,(intersection[1]-y)*1.25,
                                  (intersection[2]-x)*1.25,(intersection[3]-y)*1.25])
            if not masks and (x,y) not in controls:continue
            with opened.crop((x,y,x+256,y+256)) as crop:
                rgb=np.array(crop.convert('RGB'))
            rows.append({'image_id':f'native-context-{x}-{y}','pixels':rgb,
                'pixel_sha256':hashlib.sha256(rgb.tobytes()).hexdigest(), 'source_image_sha256':digest(image_path),
                'source_origin':[x,y],'negative_regions_training_pixels':masks,
                'annotation_origin':inspection['annotation_origin'],'human_review_claim':False,
                'independent_example':False})
            if positive_controls:
                reviewed=[t for t in positives if x<=t['source_box'][0]<t['source_box'][2]<=x+256
                          and y<=t['source_box'][1]<t['source_box'][3]<=y+256]
                rows[-1]['supervised_records']=[t['record_id'] for t in reviewed]
                rows[-1]['labels']=[[58, ((t['source_box'][0]+t['source_box'][2])/2-x)/256,
                    ((t['source_box'][1]+t['source_box'][3])/2-y)/256,
                    (t['source_box'][2]-t['source_box'][0])/256,(t['source_box'][3]-t['source_box'][1])/256]
                    for t in reviewed]
        if not rows or len(rows)>32:raise ValueError('Context windows exceed bounded diagnostic')
        return rows


def fit_reviewed_contrast(repair, caches):
    """Small ridge solve on known false-anchor/true-anchor features only.

    Preserve teacher logits for reviewed positives; target .10 for class58
    anchors within inspected negatives. This is a training target, not a change
    to inference thresholds or calibrated confidence. No unknown anchor enters
    the fit. Other class rows and box regression cannot be updated.
    """
    from ultralytics.utils.tal import make_anchors
    from app.ai.symbol_detection.partial_label_training import reviewed_region_weights
    statistics=[]
    for level,(row,bias) in enumerate(zip(repair.rows,repair.biases)):
        matrices, desired, kinds=[],[],[]
        for cached,batch in caches:
            anchors,strides=make_anchors(cached['feats'],repair.model.stride,.5)
            scores=cached['scores'].permute(0,2,1)
            known=reviewed_region_weights(torch.zeros_like(scores[:,:,0]),anchors*strides,
                batch['reviewed_negative_regions'],logits=scores,mining_class=repair.class_id)>0
            negative=known & (scores[:,:,repair.class_id].sigmoid()>=.10)
            positive=batch['preserve_reviewed_positive']
            sizes=[f.shape[2]*f.shape[3] for f in cached['tail_features']]
            start=sum(sizes[:level]); stop=start+sizes[level]
            features=cached['tail_features'][level].flatten(2).permute(0,2,1)
            baseline=scores[:,start:stop,repair.class_id]
            for mask,is_positive in ((positive[:,start:stop],True),(negative[:,start:stop],False)):
                if not mask.any():continue
                values=features[mask].double()
                matrices.append(torch.cat((values,torch.ones(len(values),1)),dim=1))
                desired.append(torch.zeros(len(values),dtype=torch.float64) if is_positive
                    else torch.full((len(values),),float(torch.logit(torch.tensor(.10))),dtype=torch.float64)-baseline[mask].double())
                kinds.extend([is_positive]*len(values))
        if not matrices:continue
        matrix=torch.cat(matrices); delta_targets=torch.cat(desired)
        positive=torch.tensor(kinds,dtype=torch.bool)
        if not (~positive).any():continue
        # Fixed positive preservation penalty and minimal parameter movement.
        scale=torch.where(positive,torch.tensor(4.),torch.tensor(1.)).double()
        width=matrix.shape[1]
        augmented=torch.cat((matrix*scale[:,None],torch.eye(width,dtype=torch.float64)))
        target=torch.cat((delta_targets*scale,torch.zeros(width,dtype=torch.float64)))
        delta=torch.linalg.lstsq(augmented,target,rcond=1e-8).solution
        if not torch.isfinite(delta).all() or delta.abs().max()>1:
            raise ValueError(f'Contrast solve exceeds bounded class-row movement ({float(delta.abs().max()):.3f})')
        with torch.no_grad():
            row.add_(delta[:-1].reshape_as(row).float());bias.add_(delta[-1:].float())
        residual=matrix@delta-delta_targets
        statistics.append({'level':level,'positive_anchors':int(positive.sum()),
            'negative_anchors':int((~positive).sum()),'max_parameter_delta':float(delta.abs().max()),
            'positive_logit_rms_delta':float(residual[positive].square().mean().sqrt()) if positive.any() else None,
            'negative_logit_target_rms_error':float(residual[~positive].square().mean().sqrt())})
    if not statistics:raise ValueError('No reproduced inspected false anchors for contrast diagnostic')
    return statistics


def run(dataset, base, inspection, output, *, steps=100, learning_rate=.001, class_id=58, prepared=None,
        native_controls=False, contrast_ridge=False):
    if output.exists():
        raise FileExistsError('Diagnostic artifacts are immutable')
    if type(steps) is not int or not 1 <= steps <= 200 or not .00001 <= learning_rate <= .001 or class_id != 58:
        raise ValueError('Development repair bounds exceeded')
    data = json.loads((dataset/'manifest.json').read_text())
    evidence = json.loads(inspection.read_text())
    from prepare_authorized_pdf_detection import validate_training_sources
    from train_symbol_detector_dev import validate_restorative_replay
    from probe_symbol_detector_dev import validate_model_classes
    from app.ai.symbol_detection.partial_label_training import ReviewedBackgroundLoss
    from ultralytics import YOLO
    from ultralytics.cfg import DEFAULT_CFG_DICT
    validate_training_sources(dataset, data)
    validate_restorative_replay(dataset, data)
    if (data['required_loss'] != 'positive_boxes_and_explicit_reviewed_background'
            or len(data['classes']) != 80 or evidence.get('human_review_claim') is not False
            or evidence.get('production_approval') is not False):
        raise ValueError('Exact development-only 80-class contract required')
    # The source/inspection was already reconciled by the immutable preparation;
    # require its exact archived copy and checkpoint lineage, not an approval flag.
    archived = dataset/'power-inspections'/f'{digest(inspection)}.json'
    if not archived.is_file() or digest(archived) != digest(inspection):
        raise ValueError('Exact preparation inspection archive required')
    parent = json.loads((base.parent.parent/'run-manifest.json').read_text())
    if (parent['dataset_manifest_sha256'] != data['parent_dataset_sha256']
            or digest(base) != data['base_model_sha256']):
        raise ValueError('Repair must start at exact parent run, not failed candidate')
    samples = selected_windows(dataset, data, evidence, class_id)
    if native_controls and prepared is None:raise ValueError('Native controls require exact prepared source')
    if contrast_ridge and not native_controls:raise ValueError('Contrast repair requires reviewed native controls')
    context = native_context_windows(prepared, data, evidence, positive_controls=native_controls) if prepared else []
    if context:
        samples = [(r,False) for r in context] + ([] if native_controls else [(r,n) for r,n in samples if not n])
    if len(samples)>64:raise ValueError('Sample cache bound exceeded')
    torch.set_num_threads(4)
    torch.manual_seed(0)
    wrapper = YOLO(str(base)); validate_model_classes(wrapper, data['classes'])
    model = wrapper.model.float()
    model.args = SimpleNamespace(**{**DEFAULT_CFG_DICT, **wrapper.ckpt.get('train_args', {}), **model.args})
    repair = FrozenClassTailRepair(model, class_id)
    loss = ReviewedBackgroundLoss(model)
    caches = []
    # One bounded cache; exactly the same deterministic resizing as square YOLO
    # windows. No random augmentation or pixel edits to the original files.
    for start in range(0, len(samples), 8):
        rows = samples[start:start+8]; images, labels, indexes = [], [], []
        for index, (row, _) in enumerate(rows):
            name = row['image_id']
            if 'pixels' in row:rgb=row['pixels']
            else:
                with Image.open(dataset/'images/train'/f'{name}.png') as opened:
                    if opened.size != (256, 256):
                        raise ValueError('Only existing square windows are supported')
                    rgb = np.asarray(opened.convert('RGB'))
            images.append(torch.from_numpy(cv2.resize(rgb, (320, 320)).copy()).permute(2,0,1).float()/255)
            lines=[] if 'pixels' in row else (dataset/'labels/train'/f'{name}.txt').read_text().splitlines()
            for label in row.get('labels',[]):
                labels.append(label); indexes.append(index)
            for line in lines:
                labels.append([float(v) for v in line.split()]); indexes.append(index)
        targets = torch.tensor(labels).reshape(-1,5)
        batch = {'batch_idx': torch.tensor(indexes), 'cls':targets[:,:1], 'bboxes':targets[:,1:],
                 'reviewed_background':torch.tensor([negative for _,negative in rows]),
                 'reviewed_background_sampling':'top_score_anchors', 'reviewed_background_mining_class':class_id}
        if context:
            maximum=max(1,max(len(r.get('negative_regions_training_pixels',[])) for r,_ in rows))
            batch['reviewed_negative_regions']=torch.tensor([
                r.get('negative_regions_training_pixels',[])+[[0,0,0,0]]*(maximum-len(r.get('negative_regions_training_pixels',[])))
                for r,_ in rows])
            batch['context_only']=torch.tensor(['pixels' in r for r,_ in rows])
        cached=repair.cache(torch.stack(images))
        if native_controls:
            from ultralytics.utils.tal import make_anchors
            from torchvision.ops import box_iou
            anchors,strides=make_anchors(cached['feats'],model.stride,.5)
            decoded=loss.bbox_decode(anchors,cached['boxes'].permute(0,2,1))*strides
            keep=torch.zeros(len(rows),decoded.shape[1],dtype=torch.bool)
            for i in range(len(rows)):
                gt=targets[torch.tensor(indexes)==i,1:]*320
                if len(gt):
                    xyxy=torch.cat((gt[:,:2]-gt[:,2:]/2,gt[:,:2]+gt[:,2:]/2),dim=1)
                    keep[i]=(box_iou(decoded[i],xyxy).amax(dim=1)>=.5) & (cached['scores'][i,class_id].sigmoid()>=.5)
            batch['preserve_reviewed_positive']=keep
        caches.append((cached, batch))
    cache_bytes = sum(t.numel()*t.element_size() for c,_ in caches
                      for value in c.values() for t in (value if isinstance(value,list) else [value]))
    if cache_bytes > 128*1024*1024:
        raise ValueError('Cache exceeds 128 MiB bound')
    optimizer = torch.optim.SGD(repair.parameters(), lr=learning_rate, momentum=0, weight_decay=0)
    def cache_summary():
        negative_scores, positive_scores = [], []
        with torch.no_grad():
            for cached, batch in caches:
                maximum = repair.predictions(cached)['scores'][:,class_id].sigmoid().amax(dim=1)
                flags = batch['reviewed_background'] | batch.get('context_only',torch.zeros_like(batch['reviewed_background']))
                if native_controls:
                    flags = flags & ~batch['preserve_reviewed_positive'].any(dim=1)
                negative_scores.extend(maximum[flags].tolist())
                positive_scores.extend(maximum[~flags].tolist())
        return {'negative_maxima':negative_scores, 'positive_window_maxima':positive_scores,
                'interpretation':'Raw-anchor training-window maxima, not NMS detection or independent accuracy'}
    before_scores = cache_summary()
    progression = []
    contrast=fit_reviewed_contrast(repair,caches) if contrast_ridge else []
    for step in range(0 if contrast_ridge else steps):
        cached,batch = caches[step % len(caches)]
        optimizer.zero_grad(set_to_none=True)
        predictions=repair.predictions(cached)
        value = loss.get_assigned_targets_and_loss(predictions, batch)[1][1]
        if native_controls:
            keep=batch['preserve_reviewed_positive']
            if keep.any():
                # Output preservation only on reviewed, correctly localized
                # positives. This is a teacher regularizer, not a new label or
                # calibrated confidence, and never supervises unknown regions.
                value=value+F.mse_loss(predictions['scores'][:,class_id][keep],cached['scores'][:,class_id][keep])
        if not torch.isfinite(value): raise ValueError('Nonfinite repair loss')
        value.backward(); torch.nn.utils.clip_grad_norm_(repair.parameters(), 10); optimizer.step()
        if step % 20 == 0 or step == steps-1:
            progression.append({'step':step+1,'loss':float(value.detach())})
            print(json.dumps(progression[-1]), flush=True)
    invariants = repair.apply()
    output.mkdir(parents=True); (output/'weights').mkdir()
    # Restore the serializable args shape; inference contract is unchanged.
    model.args = vars(model.args)
    wrapper.ckpt['ema'] = None  # Never allow an unchanged teacher to win loading.
    wrapper.save(str(output/'weights/last.pt'))
    reloaded = YOLO(str(output/'weights/last.pt'))
    validate_model_classes(reloaded, data['classes'])
    repair.verify_protected(reloaded.model.float())
    invariants['serialized_and_reloaded_other_state_exact'] = True
    result = {'kind':'local_development_symbol_detector_diagnostic', 'diagnostic_only':True,
        'base_sha256':digest(base), 'dataset_manifest_sha256':digest(dataset/'manifest.json'),
        'inspection_sha256':digest(inspection), 'class_remapping':'disabled; all 80 classes retained',
        'repair':'frozen features, BN, box heads and 79 class rows; class58-only '+('reviewed-anchor ridge solve' if contrast_ridge else 'SGD'),
        'steps':1 if contrast_ridge else steps,'learning_rate':None if contrast_ridge else learning_rate,
        'optimizer_resume':False,'cache_bytes':cache_bytes,
        'contrast_ridge':contrast,'contrast_settings':{'positive_penalty':16,'ridge':1,'negative_training_target':.10,
            'unknown_anchor_policy':'ignored','max_abs_parameter_delta':1} if contrast_ridge else None,
        'samples':[{'image_id':r['image_id'],'negative':n} for r,n in samples],
        'native_context_windows':[{k:v for k,v in r.items() if k!='pixels'} for r in context],
        'native_context_unknown_policy':'Ignore everything outside inspected negative rectangles',
        'native_positive_controls':native_controls,
        'positive_teacher_regularizer':('ridge logit preservation; penalty16' if contrast_ridge else
            'MSE logits at known-class anchors IoU>=.5 and baseline score>=.5; strength1') if native_controls else None,
        'training_window_scores_before':before_scores,'training_window_scores_after':cache_summary(),
        'progression':progression,'invariants':invariants,'checkpoint_sha256':digest(output/'weights/last.pt'),
        'production_approval':False,'independent_accuracy':None,'activation':False}
    (output/'run-manifest.json').write_text(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','base','inspection','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--steps',type=int,default=100)
    parser.add_argument('--learning-rate',type=float,default=.001)
    parser.add_argument('--prepared',type=Path,help='Opt-in source-native context with masked negative rectangles')
    parser.add_argument('--native-controls',action='store_true',help='Reviewed native-grid controls and positive-only teacher preservation')
    parser.add_argument('--contrast-ridge',action='store_true',help='Bounded reviewed-anchor contrast solve instead of SGD')
    args=parser.parse_args()
    result=run(args.dataset,args.base,args.inspection,args.output,steps=args.steps,learning_rate=args.learning_rate,
               prepared=args.prepared,native_controls=args.native_controls,contrast_ridge=args.contrast_ridge)
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','progression','native_context_windows',
                    'training_window_scores_before','training_window_scores_after')}))
