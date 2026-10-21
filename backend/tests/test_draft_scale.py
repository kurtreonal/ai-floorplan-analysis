from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace as NS
import pytest
from app.geometry.draft_scale import resolve_draft_scale
from app.services.draft_bom_service import document_takeoff, price_rows
from app.services.bom_display import cost_summary, grouped_rows


@pytest.mark.parametrize('width,height,factor', [(841,594,1),(594,841,1),(1682,1188,2),(420.5,297,.5)])
def test_a1_ratio_is_isotropic_and_consistent_under_rotation_and_resize(width,height,factor):
    result=resolve_draft_scale(width,height)
    assert result['pixels_per_meter']==pytest.approx(10*factor)
    assert 100*factor/result['pixels_per_meter']==pytest.approx(10)
    assert result['scale_basis']=='ved_paper_ratio_draft' and not result['scale_approved']


def test_calibration_overrides_policy_and_stale_calibration_never_falls_back():
    calibration=NS(pixels_per_meter=25,reference_width_pixels=841,reference_height_pixels=594)
    result=resolve_draft_scale(841,594,calibration=calibration)
    assert result['pixels_per_meter']==25 and result['scale_approved']
    assert resolve_draft_scale(1682,1188,calibration=calibration)['pixels_per_meter'] is None
    assert resolve_draft_scale(841,594,calibration=NS(**{**vars(calibration),'pixels_per_meter':None}))['pixels_per_meter'] is None


def test_source_page_metadata_and_explicit_ratio_take_precedence():
    result=resolve_draft_scale(840,594,page=dict(paper_size='A3',page_width_mm=420,page_height_mm=297))
    assert result['pixels_per_meter']==20 and result['paper_size']=='A3'
    assert resolve_draft_scale(841,594,settings=dict(scale_denominator=50))['pixels_per_meter']==20
    assert resolve_draft_scale(400,300)['scale_reason']=='paper_aspect_mismatch'
    assert resolve_draft_scale(841,594,page=dict(cropped=True))['pixels_per_meter'] is None
    assert resolve_draft_scale(841,594,page=dict(multiple_scaled_views=True))['pixels_per_meter'] is None


def test_partial_trace_is_costed_automatically_but_missing_drops_stay_partial():
    document=dict(symbols=[dict(id='s1',class_id=1,class_name='Outlet')],observed_wiring=[
        dict(id='w1',disposition='unresolved',completeness='partial',wiring_legend_name='Conduit',
             points=[dict(x=0,y=0),dict(x=100,y=0)],device_attachments=[dict(symbol_id='s1',point_index=0)])])
    before=deepcopy(document)
    ppm=resolve_draft_scale(841,594)['pixels_per_meter']
    rows=document_takeoff(document,scale=ppm)
    result=price_rows(rows,[dict(id=1,name='Conduit',unit='meter',unit_price=Decimal(25),currency='PHP',price_revision_id=1)])
    path=result['items'][1]
    path['material_kind']='conduit'
    assert path['quantity']==10 and path['line_total']==250
    assert path['missing_vertical_inputs'] and path['pricing_state']=='partial_measurement_priced'
    summary=cost_summary(result['items'])
    assert summary['currencies']['PHP']['conduit']==250 and summary['incomplete']
    assert next(g for g in grouped_rows(result['items']) if g['kind']=='path')['incomplete']
    assert document==before  # No fake completeness, review or source mutation.


def test_nominal_scale_cost_is_never_presented_as_final():
    row=dict(kind='path',name='Conduit',quantity=10,unit='meter',line_total=250,currency='PHP',
        scale_approved=False,scale_basis='ved_paper_ratio_draft')
    assert cost_summary([row])['incomplete']
    assert grouped_rows([row])[0]['incomplete']


def test_no_known_prices_has_numeric_known_costs_but_no_invented_currency():
    summary=cost_summary([dict(kind='device',line_total=None,currency=None)])
    assert summary['currencies']=={} and summary['incomplete']
    assert summary['known_costs_without_currency']==dict(devices=0,conduit=0,wire=0,total=0)
