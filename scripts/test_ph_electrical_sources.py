from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from PIL import Image, ImageDraw

from collect_ph_electrical_sources import bounded_pdf, collect, inspect_pages, official_url
from inspect_public_electrical_pages import inspect, extract_reference_regions
from prepare_pec_reference import entries, build, clean_glyph, existing_class_mapping, clean_reference, prepare_learning_check


def fixture_pdf():
    writer=PdfWriter(); writer.add_blank_page(72,48); writer.add_blank_page(72,48)
    stream=BytesIO(); writer.write(stream)
    return stream.getvalue()


class DiscoveryTests(unittest.TestCase):
    def test_official_https_only_without_credentials(self):
        for url in ['https://www.dpwh.gov.ph/file.pdf','https://bsu.edu.ph/file.pdf']:
            self.assertTrue(official_url(url))
        for url in ['http://www.dpwh.gov.ph/a','https://dpwh.gov.ph.evil.example/a',
                    'https://user:secret@www.dpwh.gov.ph/a','file:///a','https://localhost/a',
                    'https://www.dpwh.gov.ph:8080/a']:
            self.assertFalse(official_url(url))

    def test_html_blockpage_and_byte_bound_rejected(self):
        with self.assertRaises(ValueError): bounded_pdf(BytesIO(b'<html>Access blocked</html>'))
        with patch('collect_ph_electrical_sources.MAX_BYTES',4):
            with self.assertRaises(ValueError): bounded_pdf(BytesIO(b'%PDF-more'))

    def test_inspection_archive_does_not_relax_intake_or_grant_training(self):
        content,reader=bounded_pdf(BytesIO(fixture_pdf()))
        self.assertTrue(content.startswith(b'%PDF-'))
        self.assertEqual(len(reader.pages),2)
        self.assertEqual(inspect_pages(reader),[])
        class FakePage:
            def extract_text(self): return 'LIGHTING LAYOUT POWER LAYOUT LEGEND Philippine Electrical Code'
        record=inspect_pages(type('Doc',(),{'pages':[FakePage()]})())[0]
        self.assertFalse(record['training_eligible']); self.assertTrue(record['pec_note_present'])
        self.assertEqual(record['selection_state'],'assistant_proposal_not_visual_review')

    def test_unavailable_source_is_recorded_without_forged_download(self):
        with TemporaryDirectory() as folder:
            output=Path(folder)/'run'
            with patch('collect_ph_electrical_sources.urlopen',side_effect=OSError('private-secret')):
                result=collect(output,[('official','https://www.dpwh.gov.ph/a.pdf')])
            row=result['sources'][0]
            self.assertEqual(row['status'],'unavailable')
            self.assertFalse(row['training_eligible'])
            self.assertNotIn('private-secret',(output/'manifest.json').read_text())
            with self.assertRaises(FileExistsError): collect(output,[])


class SelectionTests(unittest.TestCase):
    def test_explicit_selection_identity_hash_transform_and_source_preserved(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.pdf'; original=fixture_pdf(); source.write_bytes(original)
            result=inspect(source,[2],root/'out',dpi=144)
            row=result['pages'][0]
            self.assertEqual(row['source_page_id'],sha256(original).hexdigest()+':page:2')
            self.assertEqual(row['pdf_points_to_image'],[2,0,0,0,2,0])
            self.assertEqual((row['width'],row['height']),(144,96))
            self.assertFalse(row['training_eligible'])
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(sha256((root/'out'/row['filename']).read_bytes()).hexdigest(),row['image_sha256'])
            before=(root/'out/manifest.json').read_bytes()
            with self.assertRaises(FileExistsError): inspect(source,[1],root/'out')
            self.assertEqual(before,(root/'out/manifest.json').read_bytes())

    def test_invalid_pages_rejected_before_writes(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.pdf'; source.write_bytes(fixture_pdf())
            for pages in ([],[0],[True],[1,1],[3],list(range(1,52))):
                with self.subTest(pages=pages),self.assertRaises(ValueError): inspect(source,pages,root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_panel_preserves_identity_and_does_not_claim_label_review(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.pdf'; source.write_bytes(fixture_pdf())
            prepared=inspect(source,[2],root/'pages',dpi=144)
            rows=[{'region_id':'legend','page_number':2,'bbox_source_pixels':[10,10,30,30]}]
            result=extract_reference_regions(root/'pages',rows,root/'panels')
            row=result['regions'][0]
            self.assertEqual(row['source_page_id'],prepared['pages'][0]['source_page_id'])
            self.assertEqual(row['bbox_rendered_page_top_left_points'],[5,5,15,15])
            self.assertFalse(row['training_eligible']); self.assertFalse(row['human_review_claim'])
            self.assertIsNone(row['model_class_id'])
            with self.assertRaises(FileExistsError): extract_reference_regions(root/'pages',rows,root/'panels')

    def test_panel_out_of_bounds_path_escape_and_changed_image_rejected(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.pdf'; source.write_bytes(fixture_pdf())
            inspect(source,[2],root/'pages',dpi=144)
            for identity,box in [('../escape',[1,1,10,10]),('legend',[-1,1,10,10]),
                                 ('legend',[1,1,200,200])]:
                with self.subTest(identity=identity),self.assertRaises(ValueError):
                    extract_reference_regions(root/'pages',[{'region_id':identity,'page_number':2,'bbox_source_pixels':box}],root/'bad')
            self.assertFalse((root/'bad').exists())

            (root/'pages/page-002.png').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'image changed'):
                extract_reference_regions(root/'pages',[{'region_id':'legend','page_number':2,'bbox_source_pixels':[1,1,10,10]}],root/'bad')
            self.assertFalse((root/'bad').exists())

    def test_rotated_pdf_keeps_rendered_frame_explicit(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'rotated.pdf'
            writer=PdfWriter(); writer.add_blank_page(72,48).rotate(270)
            with source.open('wb') as stream: writer.write(stream)
            result=inspect(source,[1],root/'pages',dpi=144)
            row=result['pages'][0]
            self.assertEqual(row['pdf_page_rotation_degrees'],270)
            self.assertEqual(row['coordinate_frame'],'rendered_page_top_left_points')
            self.assertEqual((row['width'],row['height']),(96,144))
            regions=extract_reference_regions(root/'pages',[{'region_id':'glyph','page_number':1,'bbox_source_pixels':[10,20,30,40]}],root/'panels')
            self.assertEqual(regions['regions'][0]['bbox_rendered_page_top_left_points'],[5,10,15,20])
            self.assertEqual(regions['regions'][0]['pdf_page_rotation_degrees'],270)


class ReferenceTests(unittest.TestCase):
    def test_cleanup_splits_variants_keeps_mount_stub_and_coordinates(self):
        image=Image.new('RGB',(100,60),'white');draw=ImageDraw.Draw(image)
        draw.ellipse((10,12,35,42),outline='black',width=2)
        draw.ellipse((65,12,90,42),outline='black',width=2)
        draw.line((58,28,65,28),fill='black',width=2)  # Authored wall mount.
        draw.line((50,0,50,59),fill='black',width=2)
        draw.line((0,58,99,58),fill='black',width=2)
        ceiling,cb=clean_glyph(image,variant='ceiling')
        wall,wb=clean_glyph(image,variant='wall')
        self.assertLess(cb[2],50);self.assertGreater(wb[0],51)
        self.assertLessEqual(wb[0],58);self.assertGreaterEqual(wb[2],91)
        self.assertLess(cb[3],58);self.assertLess(wb[3],58)
        self.assertEqual(ceiling.tobytes(),image.crop(cb).tobytes())
        self.assertEqual(wall.tobytes(),image.crop(wb).tobytes())
        ceiling.close();wall.close();image.close()

    def test_faint_wiring_line_is_not_erased_or_called_a_device(self):
        image=Image.new('RGB',(100,20),'white');draw=ImageDraw.Draw(image)
        draw.line((0,18,99,18),fill=(230,230,230))
        clean,box=clean_glyph(image,wiring=True)
        self.assertEqual(box,[0,0,100,20]);self.assertEqual(clean.tobytes(),image.tobytes())
        clean.close();image.close()

    def test_cleanup_preserves_subscript_and_removes_rule_antialias_fringe(self):
        image=Image.new('RGB',(100,60),'white');draw=ImageDraw.Draw(image)
        draw.line((30,10,30,35),fill='black',width=2)
        draw.rectangle((40,35,48,45),fill=(120,120,120))  # Lower subscript.
        draw.line((30,57,99,57),fill=(230,230,230))
        draw.line((0,58,99,58),fill=(230,230,230))
        draw.line((0,59,99,59),fill='black')
        clean,box=clean_glyph(image)
        self.assertGreaterEqual(box[3],46);self.assertLessEqual(box[3],57)
        self.assertEqual(clean.tobytes(),image.crop(box).tobytes())
        clean.close();image.close()

    def test_reference_semantics_do_not_guess_ratings_subtypes_or_fire_alarm_meaning(self):
        classes=[{'id':0,'label':'Smoke detector'},{'id':1,'label':'Smoke detector'},
                 {'id':2,'label':'Conventional smoke detector'},{'id':3,'label':'Smoke detector (new)'},
                 {'id':4,'label':'2 x 40 watts fluorescent lamp'},{'id':5,'label':'One gang device switch'},
                 {'id':6,'label':'Panelboard'},{'id':7,'label':'Fire alarm control panel'}]
        self.assertEqual(existing_class_mapping('1.36.5',classes),[0,1])
        self.assertEqual(existing_class_mapping('1.36.2',classes),[7])
        for identity in ('1.20.5','1.21.1','1.14','1.15','1.16','1.36.1','1.37.1'):
            self.assertEqual(existing_class_mapping(identity,classes),[])

    def test_cleanup_and_diagnostic_fail_closed_on_tampered_source_without_writes(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'source').mkdir()
            (root/'source/manifest.json').write_text('{}')
            with self.assertRaises(ValueError):clean_reference(root/'source',root/'parent.json',root/'out')
            self.assertFalse((root/'out').exists())
            with self.assertRaises(ValueError):prepare_learning_check(root/'source',root/'parent.json',root/'weights.pt',root/'out')
            self.assertFalse((root/'out').exists())
            with self.assertRaises(ValueError):prepare_learning_check(root/'source',root/'parent.json',root/'weights.pt',root/'out',examples=17)

    def test_five_class_probe_uses_unchanged_numeric_names_and_reports_no_accuracy(self):
        from types import SimpleNamespace
        from probe_symbol_detector_dev import probe_authored_synthetic
        with TemporaryDirectory() as folder:
            root=Path(folder);(root/'images/train').mkdir(parents=True)
            checkpoint=root/'local.pt';checkpoint.write_bytes(b'local-test-checkpoint')
            rows=[];classes=[]
            for index in range(5):
                name=f'authored-legend-test-{index}';path=root/'images/train'/f'{name}.png'
                Image.new('RGB',(256,256),'white').save(path)
                rows.append({'image_id':name,'human_review_claim':False,'class_id':index,
                             'image_sha256':sha256(path.read_bytes()).hexdigest(),'box':[10,10,20,20]})
                classes.append({'id':index,'label':f'class-{index}'})
            (root/'manifest.json').write_text(json.dumps({'classes':classes,'authored_legend_synthetic_images':rows}))
            model=SimpleNamespace(names={r['id']:r['label'] for r in classes},
                predict=lambda images,**kw:[SimpleNamespace(boxes=[]) for _ in images])
            with patch('probe_symbol_detector_dev.YOLO',return_value=model):
                summary=probe_authored_synthetic(root,checkpoint,root/'probe',samples_per_class=1)
            self.assertEqual(len(summary),5)
            self.assertTrue(all(r['localized_and_classified']==0 for r in summary))
            report=json.loads((root/'probe/report.json').read_text())
            self.assertIsNone(report['independent_accuracy']);self.assertIsNone(report['real_page_accuracy'])

    def test_learning_dataset_preserves_head_and_separates_known_synthetic_labels(self):
        from types import SimpleNamespace
        from prepare_pec_reference import digest
        from prepare_authorized_pdf_detection import validate_training_sources
        with TemporaryDirectory() as folder:
            root=Path(folder);prepared=root/'prepared';prepared.mkdir()
            original=prepared/'original.pdf';original.write_bytes(b'reference-fixture')
            source_hash=digest(original)
            (prepared/'manifest.json').write_text('{}');preparation_hash=digest(prepared/'manifest.json')
            (prepared/'source-authorization.json').write_text(json.dumps({'user_statement':'Use the specified legends for training',
                'project_group_id':'reference-fixture','rights_evidence':'user_request_not_independent_license_verification'}))
            cleaned=root/'cleaned';cleaned.mkdir();rows=[]
            labels=['Circuit home-run notation','Smoke detector','Pull box','Push button','Fire alarm control panel']
            classes=[{'id':i,'label':labels[i] if i<5 else f'preserved-class-{i}','samples':9} for i in range(80)]
            for index,identity in enumerate(['1.26','1.36.5','1.23','1.27','1.36.2']):
                name=f'reference-{index}.png';im=Image.new('RGB',(40,40),'white')
                ImageDraw.Draw(im).rectangle((10,10,30,30),outline='black',width=2);im.save(cleaned/name);im.close()
                rows.append({'filename':name,'reference_id':identity,'glyph_sha256':digest(cleaned/name),
                    'mapped_model_class_ids':[index],'annotation_layer':'symbols','human_review_claim':False,
                    'production_approval':False,'variant':'as_shown'})
            registry={'prepared_directory':str(prepared),'references':rows,'unmapped_point_reference_entries':['1.20.5']}
            (cleaned/'manifest.json').write_text(json.dumps(registry));registry_hash=digest(cleaned/'manifest.json')
            parent=root/'parent.json';parent.write_text(json.dumps({'classes':classes}));parent_hash=digest(parent)
            checkpoint=root/'local.pt';checkpoint.write_bytes(b'local-fixture');checkpoint_hash=digest(checkpoint)
            model=SimpleNamespace(names={r['id']:r['label'] for r in classes})
            with patch.multiple('prepare_pec_reference',CLEANED_SHA256=registry_hash,PARENT_DATASET_SHA256=parent_hash,
                                PARENT_CHECKPOINT_SHA256=checkpoint_hash,PREPARED_SHA256=preparation_hash,SOURCE_SHA256=source_hash), \
                    patch('ultralytics.YOLO',return_value=model):
                result=prepare_learning_check(cleaned,parent,checkpoint,root/'out',examples=4)
                self.assertEqual(result['synthetic_images'],20);self.assertEqual(result['numeric_head_classes'],80)
                with self.assertRaises(FileExistsError):prepare_learning_check(cleaned,parent,checkpoint,root/'out')
                (cleaned/rows[0]['filename']).write_bytes(b'altered')
                with self.assertRaises(ValueError):prepare_learning_check(cleaned,parent,checkpoint,root/'tampered')
                self.assertFalse((root/'tampered').exists())
            data=json.loads((root/'out/manifest.json').read_text())
            self.assertTrue(data['diagnostic_only']);self.assertFalse(data['all_eligible_entries'])
            self.assertEqual(data['reviewed_targets'],[]);self.assertFalse(data['production_approval'])
            self.assertEqual(data['unmapped_point_reference_entries'],['1.20.5'])
            self.assertIn(source_hash,validate_training_sources(root/'out',data))
            self.assertEqual([r['label'] for r in data['classes']],[r['label'] for r in classes])
            for row in data['authored_legend_synthetic_images']:
                label=root/'out/labels/train'/f"{row['image_id']}.txt"
                values=label.read_text().split()
                self.assertEqual(int(values[0]),row['class_id']);self.assertEqual(digest(label),row['label_sha256'])
                self.assertTrue(all(0<float(v)<1 for v in values[1:]));self.assertFalse(row['human_review_claim'])

    def test_requested_66_identities_and_wiring_are_not_devices(self):
        rows=entries(); self.assertEqual(len(rows),66)
        expected={f'1.{i}' for i in [14,15,16]+list(range(22,36))}
        for prefix,count in [('1.20',20),('1.21',11),('1.36',6),('1.37',12)]:
            expected.update(f'{prefix}.{i}' for i in range(1,count+1))
        self.assertEqual({r['reference_id'] for r in rows},expected)
        self.assertEqual(sum(r['annotation_layer']=='wiring' for r in rows),12)
        self.assertTrue(all(r['model_class_id'] is None and r['human_review_claim'] is False for r in rows))
        lamp=next(r for r in rows if r['reference_id']=='1.20.5')
        self.assertEqual(lamp['proposed_label'],'Fluorescent Lamp')  # No guessed wattage.
        self.assertEqual(lamp['authored_variants'],['ceiling','wall'])

    def test_crops_stay_on_explicit_first_two_pages(self):
        for row in entries():
            x1,y1,x2,y2=row['bbox_pdf_top_left_points']
            self.assertIn(row['page_number'],[1,2])
            self.assertTrue(0<=x1<x2<=750 and 0<=y1<y2<=971.03998)

    def test_changed_reference_rejected_and_no_approval_created(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); source=root/'wrong.pdf'; source.write_bytes(fixture_pdf())
            with self.assertRaises(ValueError): build(source,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__': unittest.main()
