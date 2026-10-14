from copy import deepcopy
from pathlib import Path
import sys
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).parent))
from prepare_reviewed_plan_training import review_targets,tile_rows,append_reviewed_head


def scene(tmp_path):
    path=tmp_path/'source.png';Image.new('RGB',(600,400),'white').save(path)
    classes=[dict(id=0,label='normal',legend_entry='s:L01N'),dict(id=1,label='UPS',legend_entry='s:L01U')]
    catalog=[dict(legend_entry=r['legend_entry'],label='Duplex convenience outlet - '+('normal power' if r['id']==0 else 'UPS power'),examples=[dict(source_sheet_id='s')]) for r in classes]
    symbol=dict(id='a',layer='symbols',label='Convenience outlet - verify normal or UPS variant',legend_entry='uncertain',
        review_state='user_reviewed',class_state='unmapped',geometry=dict(type='bbox',coordinates=[20,30,34,50]))
    sheet=dict(id='s',group=1,width=600,height=400,source_sha256='hash',annotations=[symbol])
    return dict(sheets=[sheet]),catalog,{'hash':path},classes


def test_uncertain_subtype_retains_box_without_forcing_normal(tmp_path):
    s,c,p,k=scene(tmp_path);old=deepcopy(s)
    targets,decisions,sheets=review_targets(s,c,p,[1],k)
    assert targets[0]['allowed_class_ids']==[0,1] and targets[0]['subtype_unresolved']
    assert targets[0]['source_box']==[20,30,34,50] and s==old
    assert sheets[0]['coverage']=='reviewed_positive_records_only'


def test_deletion_legend_and_unreviewed_objects_are_not_device_or_background_targets(tmp_path):
    s,c,p,k=scene(tmp_path);a=s['sheets'][0]['annotations'][0]
    s['sheets'][0]['annotations']+=[dict(a,id='d',review_state='deleted'),dict(a,id='l',layer='legend'),dict(a,id='u',review_state='needs_review')]
    t,d,_=review_targets(s,c,p,[1],k)
    assert len(t)==1
    assert {r['reason'] for r in d}=={'included_reviewed_positive','deleted_preserved_not_negative','not_installed_symbol_layer','not_user_reviewed'}


def test_technical_uncertainty_preserves_original_label_and_localization(tmp_path):
    s,c,p,k=scene(tmp_path);a=s['sheets'][0]['annotations'][0]
    a.update(legend_entry='s:L01N',class_state='approved_legend_mapping',label='normal')
    t,_,_=review_targets(s,c,p,[1],k,uncertain=['a'])
    assert t[0]['allowed_class_ids']==[0,1] and t[0]['technical_subtype_uncertainty']
    assert t[0]['label']=='normal' and a['class_state']=='approved_legend_mapping'


@pytest.mark.parametrize('box',[[0,0,0,4],[-1,1,4,5],[590,390,610,410]])
def test_invalid_boxes_excluded_with_reason(tmp_path,box):
    s,c,p,k=scene(tmp_path);s['sheets'][0]['annotations'][0]['geometry']['coordinates']=box
    with pytest.raises(ValueError,match='Missing selected'):review_targets(s,c,p,[1],k)


def test_stable_box_edges_and_neighbor_targets_under_scaled_tile_origin():
    targets=[dict(source_box=[100,200,110,220],allowed_class_ids=[0,1]),dict(source_box=[120,210,130,230],allowed_class_ids=[1])]
    rows=tile_rows(targets,(180,380),[2,2])
    assert [r['local_box'] for r in rows]==[[20,20,40,60],[60,40,80,80]]
    assert targets[0]['source_box']==[100,200,110,220]
    assert tile_rows(targets,(250,450),[2,2])==[]


def test_existing_test_split_is_never_moved_into_training(tmp_path):
    s,c,p,k=scene(tmp_path);s['sheets'][0]['split']='sealed_test'
    with pytest.raises(ValueError,match='Protected'):review_targets(s,c,p,[1],k)


def test_head_extension_keeps_previous_logits_and_distinct_new_identity():
    from types import SimpleNamespace as NS
    import torch
    class Detect(torch.nn.Module):
        def __init__(self):
            super().__init__();self.cv3=torch.nn.ModuleList([torch.nn.Sequential(torch.nn.Conv2d(4,2,1))]);self.reg_max=16
    head=Detect();prior=head.cv3[0][-1];weight=prior.weight.detach().clone();bias=prior.bias.detach().clone()
    model=NS(model=[head],names={0:'normal',1:'other'},yaml={'nc':2})
    append_reviewed_head(model,[dict(label='UPS',seed_parent_class_id=0)])
    assert torch.equal(head.cv3[0][-1].weight[:2],weight) and torch.equal(head.cv3[0][-1].bias[:2],bias)
    assert model.names=={0:'normal',1:'other',2:'UPS'} and head.nc==3 and head.no==67
