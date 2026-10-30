"""Read-only source inspection, saved separately from original drawings."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
from prepare_authored_legend_extension import digest


def freeze_inspection(output):
    """Record assistant findings separately; never alter prior user annotations."""
    parent=Path('storage/training/lamps-real-20261004-v4')
    data=json.loads((parent/'manifest.json').read_text())
    permission=json.loads((parent/'development-source-authorization.json').read_text())
    common={'human_review_claim':False,'production_approval':False,
        'missing_annotation_policy':'ignore_unreviewed_not_empty_background',
        'annotation_origin':'assistant_visual_under_user_development_authorization',
        'user_statement':permission['user_statement']}
    sources=[]
    for prefix,page_number,group in [('76f411c60b6d',3,'elect-76f411c60b6d'),('efa570519f08',7,'deped-efa570519f08')]:
        prepared=Path(f'storage/training/pdf-source-20261004-{prefix}-v3')
        source=json.loads((prepared/'manifest.json').read_text())
        page=next(p for p in source['pages'] if p['page_number']==page_number)
        entry={**common,'prepared':prepared.as_posix(),'source_sha256':source['source_sha256'],
            'prepared_manifest_sha256':digest(prepared/'manifest.json'),'source_image_sha256':page['image_sha256'],
            'page_number':page_number,'project_group_id':group,'targets':[]}
        if prefix=='76f411c60b6d':
            for t in data['authorized_pdf_targets']:
                if t['pdf_sha256']==source['source_sha256'] and t['class_id'] in (62,64):
                    entry['targets'].append({'id':t['record_id'],'class_id':t['class_id'],'box':t['source_box'],
                        'label':t['label'],'source_legend_entry':t['legend_entry'],
                        'meaning_evidence':'Original assistant-inspected S / Sabc drawings; source legend L04/L06. Prior box retained unchanged.'})
        else:
            observations=[(62,[806,348,837,379]),(62,[708,417,739,449]),(62,[557,491,587,523]),
                (62,[478,540,507,574]),(62,[803,893,840,922]),(63,[1098,893,1157,922]),
                (62,[1506,893,1542,922]),(63,[318,946,357,975]),(63,[1510,946,1551,975])]
            for i,(cls,box) in enumerate(observations):
                entry['targets'].append({'id':f'depedswitch{i:02d}','class_id':cls,
                    'box':[box[0]+305,box[1]+1930,box[2]+305,box[3]+1930],
                    'label':data['classes'][cls]['label'],
                    'source_legend_entry':f"pdf-{prefix}:p7:L{'04' if cls==62 else '05'}",
                    'meaning_evidence':'Visible S / one circuit suffix versus two circuit suffixes; authored S/Sa and Sab legend, exact matching one/two-gang meaning. No inference of three-way or fan subtype.'})
            entry['excluded']=[{'box':[623,2821,657,2853],
                'reason':'Sf conflicts with fan-control legend while controlling fluorescent branch f; subtype unresolved, ignored.'}]
        sources.append(entry)
    upload={**common,'source_sha256':digest(parent/'original-upload.png'),
        'source_image_sha256':digest(parent/'original-upload.png'),
        'prepared_manifest_sha256':digest(parent/'upload-preparation.json'),
        'parent_pdf_sha256':sources[1]['source_sha256'],'project_group_id':'deped-efa570519f08','targets':[]}
    observations=[(62,[280,36,296,52]),(62,[234,69,248,88]),(62,[164,103,180,121]),
        (62,[128,126,144,145]),(62,[280,284,298,304]),(63,[413,284,441,304]),
        (62,[599,284,618,304]),(63,[62,311,82,329]),(63,[599,311,619,329])]
    for i,(cls,box) in enumerate(observations):
        upload['targets'].append({'id':f'uploadswitch{i:02d}','class_id':cls,'box':box,
            'label':data['classes'][cls]['label'],
            'source_legend_entry':f"pdf-efa570519f08:p7:L{'04' if cls==62 else '05'}",
            'meaning_evidence':'Exact PNG pixels inspected separately; same DepED drawing glyph/circuit-letter convention. No claimed PDF affine transform or independent source.'})
    upload['excluded']=[{'box':[61,284,77,304],'reason':'Ambiguous Sf subtype; ignored.'}]
    path=output/'inspection.json'
    if path.exists():raise FileExistsError('Inspection revisions are immutable')
    path.write_text(json.dumps({'parent_manifest_sha256':digest(parent/'manifest.json'),
                               'sources':sources,'upload':upload},indent=2))
    return digest(path)


def contacts(source, boxes, output):
    if output.exists():
        raise FileExistsError('Inspection evidence is immutable')
    result = Image.new('RGB', (900, ((len(boxes)+3)//4)*190), 'white')
    with Image.open(source) as opened:
        for index, (name, box) in enumerate(boxes):
            crop = opened.crop(box).convert('RGB')
            crop.thumbnail((210,155))
            x,y = (index%4)*225,(index//4)*190
            result.paste(crop,(x,y))
            ImageDraw.Draw(result).text((x,y+158), name, fill='black')
            ImageDraw.Draw(result).text((x,y+172),str(box),fill='black')
            crop.close()
    result.save(output); result.close()


if __name__ == '__main__':
    output = Path('storage/training/switch-inspection-20261004-v2')
    output.mkdir(exist_ok=False)
    contacts(Path('storage/training/pdf-source-20261004-efa570519f08-v3/lighting-layout.png'),
        [(str(i),box) for i,box in enumerate([
            [806,348,837,379],[708,417,739,449],[557,491,587,523],[478,540,507,574],
            [318,891,352,923],[803,893,840,922],[1098,893,1157,922],[1506,893,1542,922],
            [318,946,357,975],[1510,946,1551,975]])],output/'deped-switch-context.png')
    contacts(Path('storage/training/lamps-real-20261004-v4/original-upload.png'),
        [(str(i),box) for i,box in enumerate([
            [280,36,296,52],[234,69,248,88],[164,103,180,121],[128,126,144,145],
            [61,284,77,304],[280,284,298,304],[413,284,441,304],[599,284,618,304],
            [62,311,82,329],[599,311,619,329]])],output/'upload-switch-context.png')
