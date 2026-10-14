"""Synthetic PDF regressions; no private drawings, models or database required."""
from copy import deepcopy
from hashlib import sha256

import numpy as np
import pypdfium2 as pdfium
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject,ArrayObject,NumberObject
import pytest

from app.ai.floor_plan_interpretation import pdf_evidence as evidence


def make_pdf(path, content, rotation=0):
    writer=PdfWriter()
    page=writer.add_blank_page(width=300,height=200)
    stream=DecodedStreamObject()
    stream.set_data(content.encode('ascii'))
    page[NameObject('/Contents')]=writer._add_object(stream)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),
        NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    if rotation:page.rotate(rotation)
    writer.write(path)
    return path


@pytest.mark.parametrize('rotation',[0,90,180,270])
def test_vector_endpoints_match_rotated_reference_and_original_is_unchanged(tmp_path,rotation):
    path=make_pdf(tmp_path/'plan.pdf','2 w 0 0 1 RG 30 40 m 150 40 l S',rotation)
    original=path.read_bytes()
    width,height=(600,400) if rotation in (0,180) else (400,600)
    result=evidence.extract_pdf_evidence(path,page_number=1,width=width,height=height)
    with pdfium.PdfDocument(path) as doc:
        page=doc[0]; bitmap=page.render(scale=2)
        rgb=np.array(bitmap.to_pil().convert('RGB'))
        converter=bitmap.get_posconv(page)
        commands=result['objects'][0]['commands']
        for command,point in zip(commands,[(30,40),(150,40)]):
            expected=converter.to_bitmap(*point)
            assert np.linalg.norm(np.array(command[1:3])-expected)<.51
        middle=np.rint((np.array(commands[0][1:3])+commands[1][1:3])/2).astype(int)
        assert rgb[middle[1],middle[0],2]>200
        assert rgb[middle[1],middle[0],0]<50
        bitmap.close();page.close()
    assert path.read_bytes()==original
    assert result['source_sha256']==sha256(original).hexdigest()
    assert result['physical_thickness_available'] is False


def test_preserves_curves_fill_dash_text_clip_and_transform(tmp_path):
    path=make_pdf(tmp_path/'styles.pdf',
        'q 10 10 200 150 re W n 2 0 0 2 10 5 cm 2 w [3 2] 1 d '
        '0 0 1 RG 30 40 m 40 80 90 80 100 40 c S Q '
        '0.5 g 20 20 10 30 re f '
        'BT /F1 12 Tf 30 160 Td (GROUND FLOOR) Tj ET')
    first=evidence.extract_pdf_evidence(path,page_number=1,width=600,height=400)
    second=evidence.extract_pdf_evidence(path,page_number=1,width=600,height=400)
    assert first==second
    curve=first['objects'][0]
    assert curve['own_transform']==[2,0,0,2,10,5]
    assert curve['dash_array']==[3,2]
    assert curve['dash_phase']==1
    assert curve['stroke_color']==[0,0,255,255]
    assert curve['clip_paths']
    assert sum(c[0]==1 for c in curve['commands'])==3
    assert any(o.get('fill_mode',0)>0 for o in first['objects'])
    assert any(o.get('text')=='GROUND FLOOR' for o in first['objects'])


def test_scanned_or_blank_pdf_reports_raster_capability(tmp_path):
    path=make_pdf(tmp_path/'scan.pdf','')
    result=evidence.extract_pdf_evidence(path,page_number=1,width=600,height=400)
    assert result['capability']=='raster'
    assert result['object_counts']['paths']==0


def test_parser_budgets_are_explicit_not_silent_truncation(tmp_path,monkeypatch):
    path=make_pdf(tmp_path/'dense.pdf','0 0 m 20 20 l S 20 20 m 30 20 l S')
    monkeypatch.setattr(evidence,'MAX_OBJECTS',1)
    with pytest.raises(evidence.PdfEvidenceError,match='OBJECT_BUDGET'):
        evidence.extract_pdf_evidence(path,page_number=1,width=600,height=400)
    with pytest.raises(evidence.PdfEvidenceError,match='INVALID_PLANE'):
        evidence.extract_pdf_evidence(path,page_number=1,width=9000,height=400)


def test_spatial_index_matches_exhaustive_intersections_without_mutation():
    rows=[dict(id=i,bounds=[i*10,i*5,i*10+30,i*5+30]) for i in range(100)]
    rows.append(dict(id=100,bounds=[0,0,4000,3000]))
    before=deepcopy(rows)
    index=evidence.PrimitiveIndex({'objects':rows})
    for box in ([120,100,250,180],[0,0,4096,4096],[900,350,1200,500]):
        a,b,c,d=box
        expected=[o for o in rows if o['bounds'][0]<=c and o['bounds'][2]>=a
                  and o['bounds'][1]<=d and o['bounds'][3]>=b]
        assert index.query(box)==expected
    assert rows==before


def test_nested_form_transform_and_parent_identity_match_rendered_pixels(tmp_path):
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=200)
    form=DecodedStreamObject();form.set_data(b'2 w 0 0 1 RG 10 15 m 30 15 l S')
    form.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Form'),
        NameObject('/BBox'):ArrayObject([NumberObject(v) for v in [0,0,100,100]]),
        NameObject('/Matrix'):ArrayObject([NumberObject(v) for v in [2,0,0,2,5,10]]),
        NameObject('/Resources'):DictionaryObject()})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):
        DictionaryObject({NameObject('/Fm'):writer._add_object(form)})})
    content=DecodedStreamObject();content.set_data(b'q 1 0 0 1 30 20 cm /Fm Do Q')
    page[NameObject('/Contents')]=writer._add_object(content)
    path=tmp_path/'form.pdf';writer.write(path)
    result=evidence.extract_pdf_evidence(path,page_number=1,width=600,height=400)
    parent=next(o for o in result['objects'] if o['type']==5)
    child=next(o for o in result['objects'] if o['type']==2)
    assert child['parent_id']==parent['id'] and child['level']==1
    assert np.allclose([c[1:3] for c in child['commands']],[[110,280],[190,280]],atol=1e-6)
    with pdfium.PdfDocument(path) as doc:
        page=doc[0];bitmap=page.render(scale=2)
        rgb=np.array(bitmap.to_pil().convert('RGB'))
        assert rgb[280,150,2]>200 and rgb[280,150,0]<50
        bitmap.close();page.close()
