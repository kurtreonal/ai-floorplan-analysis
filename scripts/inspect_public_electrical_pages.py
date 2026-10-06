"""Render explicit inspection pages without granting training eligibility."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import math
import re

from PIL import Image, ImageDraw
import pypdfium2 as pdfium

from prepare_pdf_training_source import render_size


def extract_reference_regions(inspected, regions, output):
    """Preserve authored legend panels; never imply individual label review."""
    inspected,output=Path(inspected),Path(output)
    if output.exists():
        raise FileExistsError('Reference-panel revisions are immutable')
    raw=(inspected/'manifest.json').read_bytes()
    if len(raw)>1_048_576:
        raise ValueError('Inspection manifest exceeds bound')
    data=json.loads(raw)
    if data.get('schema')!='ved-public-electrical-page-inspection-v2':
        raise ValueError('Expected inspection manifest')
    pages={p['page_number']:p for p in data['pages']}
    checked=[]; identities=set()
    if not isinstance(regions,list) or not 1<=len(regions)<=50:
        raise ValueError('Reference region bound exceeded')
    for region in regions:
        identity,number,box=region['region_id'],region['page_number'],region['bbox_source_pixels']
        if (not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',identity)
                or identity in identities or type(number) is not int or number not in pages
                or len(box)!=4 or any(type(v) is not int for v in box)):
            raise ValueError('Invalid region identity')
        page=pages[number]
        if not (0<=box[0]<box[2]<=page['width'] and 0<=box[1]<box[3]<=page['height']):
            raise ValueError('Region exceeds source page')
        name=page['filename']
        if Path(name).name!=name or sha256((inspected/name).read_bytes()).hexdigest()!=page['image_sha256']:
            raise ValueError('Inspection image changed')
        identities.add(identity); checked.append((region,page))
    output.mkdir(parents=True)
    rows=[]
    for region,page in checked:
        with Image.open(inspected/page['filename']) as image:
            if image.size!=(page['width'],page['height']):
                raise ValueError('Inspection dimensions changed')
            with image.crop(region['bbox_source_pixels']) as crop:
                filename=region['region_id']+'.png'
                with (output/filename).open('xb') as stream: crop.save(stream,format='PNG')
        scale=page['pdf_points_to_image'][0]
        if not math.isfinite(scale) or scale<=0:
            raise ValueError('Invalid source transform')
        rows.append({**region,'filename':filename,'crop_sha256':sha256((output/filename).read_bytes()).hexdigest(),
                     'source_page_id':page['source_page_id'],'source_image_sha256':page['image_sha256'],
                     'bbox_rendered_page_top_left_points':[v/scale for v in region['bbox_source_pixels']],
                     'pdf_page_rotation_degrees':page['pdf_page_rotation_degrees'],
                     'annotation_origin':'assistant_reference_panel_proposal','human_review_claim':False,
                     'training_eligible':False,'model_class_id':None})
    result={'schema':'ved-public-legend-panel-preparation-v1','source_sha256':data['source_sha256'],
            'inspection_manifest_sha256':sha256(raw).hexdigest(),'regions':rows,
            'rights_status':'unverified_training_excluded','model_changed':False}
    with (output/'manifest.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    return result


def inspect(source, pages, output, *, dpi=100):
    source, output=Path(source),Path(output)
    if output.exists():
        raise FileExistsError('Inspection revisions are immutable')
    if source.stat().st_size>25*1024*1024:
        raise ValueError('Source exceeds bound')
    original=source.read_bytes(); digest=sha256(original).hexdigest()
    if type(dpi) is not int or not 72<=dpi<=200:
        raise ValueError('Invalid inspection resolution')
    rows=[]
    with pdfium.PdfDocument(original) as doc:
        if (not pages or len(pages)>50 or len(set(pages))!=len(pages)
                or any(type(p) is not int or not 1<=p<=len(doc) for p in pages)):
            raise ValueError('Select <=50 explicit distinct pages')
        for number in pages:
            page=doc[number-1]
            try:
                render_size(page.get_size(),dpi)
            finally:
                page.close()
        output.mkdir(parents=True)
        cards=[]
        for number in pages:
            page=doc[number-1]
            bitmap=None
            try:
                bitmap=page.render(scale=dpi/72)
                try:
                    image=bitmap.to_pil().convert('RGB')
                    filename=f'page-{number:03d}.png'
                    with (output/filename).open('xb') as stream:
                        image.save(stream,format='PNG')
                    rows.append({'source_page_id':f'{digest}:page:{number}',
                                 'page_number':number,'filename':filename,
                                 'image_sha256':sha256((output/filename).read_bytes()).hexdigest(),
                                 'width':image.width,'height':image.height,
                                 'coordinate_frame':'rendered_page_top_left_points',
                                 'pdf_page_rotation_degrees':page.get_rotation(),
                                 'pdf_points_to_image':[dpi/72,0,0,0,dpi/72,0],
                                 'pdf_points_to_image_frame':'rendered_page_top_left_points_not_unrotated_pdf_user_space',
                                 'training_eligible':False,'label_state':'not_annotated'})
                    image.thumbnail((450,320)); cards.append((number,image))
                finally:
                    bitmap.close()
            finally:
                page.close()
        for k in range(0,len(cards),12):
            group=cards[k:k+12]
            canvas=Image.new('RGB',(1380,345*((len(group)+2)//3)),'white')
            draw=ImageDraw.Draw(canvas)
            for j,(number,image) in enumerate(group):
                x,y=(j%3)*460,(j//3)*345
                canvas.paste(image,(x,y+23)); draw.text((x+5,y+5),f'Page {number}',fill='black')
                image.close()
            canvas.save(output/f'contact-{k//12:02d}.jpg'); canvas.close()
    if sha256(source.read_bytes()).hexdigest()!=digest:
        raise ValueError('Original changed during inspection')
    result={'schema':'ved-public-electrical-page-inspection-v2','source_sha256':digest,
            'dpi':dpi,'pages':rows,'rights_status':'unverified_training_excluded',
            'model_changed':False,'production_approval':False}
    with (output/'manifest.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--page',type=int,action='append',required=True)
    args=parser.parse_args()
    print(json.dumps({'pages':len(inspect(args.source,args.page,args.output)['pages'])}))
