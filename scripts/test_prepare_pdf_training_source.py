import hashlib
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter

from prepare_pdf_training_source import prepare, render_size
from collect_ph_electrical_sources import bounded_pdf, collect, inspect_pages, official_url
from inspect_public_electrical_pages import inspect, extract_reference_regions


class PDFTrainingSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=48)
        writer.add_blank_page(width=72, height=48)
        with self.source.open('wb') as stream:
            writer.write(stream)
        self.before = self.source.read_bytes()
        self.permission = self.root / 'permission.json'
        self.write_permission()
        self.output = self.root / 'prepared'

    def write_permission(self, **changes):
        self.permission.write_text(json.dumps({
            'source_sha256': hashlib.sha256(self.before).hexdigest(),
            'authorization_kind': 'user_attested_source_permission',
            'user_statement': 'Use this source for local training',
            'allowed_purposes': ['reference_grounding', 'training'],
            'project_group_id': 'related-project', **changes}), encoding='utf-8')

    def regions(self, box=(10, 5, 20, 15), identity='L01'):
        path = self.root / 'regions.json'
        path.write_text(json.dumps([{'page_number': 2, 'region_id': identity,
                                    'bbox_pdf_top_left_points': box,
                                    'proposed_label': 'Authored legend',
                                    'review_state': 'user_reviewed', 'training_eligible': True}]), encoding='utf-8')
        return path

    def test_explicit_page_crop_transform_hashes_and_original_preserved(self):
        result = prepare(self.source, self.output, self.permission, [2], dpi=144,
                         regions_path=self.regions())
        self.assertEqual(self.source.read_bytes(), self.before)
        self.assertEqual((self.output / 'original.pdf').read_bytes(), self.before)
        page = result['pages'][0]
        self.assertEqual(page['page_number'], 2)
        self.assertTrue(page['source_page_id'].endswith(':page:2'))
        self.assertEqual((page['width'], page['height']), (144, 96))
        self.assertEqual(page['pdf_points_to_image'], [2, 0, 0, 0, 2, 0])
        region = result['regions'][0]
        self.assertEqual(region['bbox_source_pixels'], [20, 10, 40, 30])
        self.assertEqual(region['source_image_sha256'], page['image_sha256'])
        self.assertEqual(region['crop_sha256'], hashlib.sha256((self.output / 'L01.png').read_bytes()).hexdigest())
        with Image.open(self.output / 'L01.png') as crop:
            self.assertEqual(crop.size, (20, 20))
        self.assertFalse(result['training_ready'])
        self.assertEqual(result['reviewed_detection_targets'], 0)
        self.assertFalse(region['training_eligible'])
        self.assertEqual(region['review_state'], 'assistant_proposed')
        self.assertEqual(page['text_extraction_state'], 'unavailable')

    def test_existing_revision_not_overwritten(self):
        prepare(self.source, self.output, self.permission, [1], dpi=72)
        before = (self.output / 'manifest.json').read_bytes()
        with self.assertRaises(FileExistsError):
            prepare(self.source, self.output, self.permission, [2])
        self.assertEqual((self.output / 'manifest.json').read_bytes(), before)

    def test_permission_bound_to_exact_source(self):
        self.write_permission(source_sha256='0' * 64)
        with self.assertRaises(ValueError):
            prepare(self.source, self.output, self.permission, [1])
        self.assertFalse(self.output.exists())

    def test_invalid_or_implicit_pages_rejected(self):
        for pages in ([], [0], [3], [True], [1, 1]):
            with self.subTest(pages=pages), self.assertRaises(ValueError):
                prepare(self.source, self.output, self.permission, pages)
        self.assertFalse(self.output.exists())

    def test_allocation_limit_checked_before_render(self):
        with patch('prepare_pdf_training_source.render_size', side_effect=ValueError('bounded')):
            with self.assertRaises(ValueError):
                prepare(self.source, self.output, self.permission, [1])
        self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError):
            render_size((20000, 20000), 300)

    def test_invalid_crops_rejected_before_output(self):
        for box, identity in [((-1, 0, 10, 10), 'L01'), ((0, 0, 73, 10), 'L01'),
                              ((0, 0, float('nan'), 10), 'L01'), ((0, 0, 10, 10), '../escape'),
                              ((0, 0, 10, 10), 'page-002')]:
            with self.subTest(box=box, identity=identity), self.assertRaises(ValueError):
                prepare(self.source, self.output, self.permission, [2], regions_path=self.regions(box, identity))
        self.assertFalse(self.output.exists())

    def test_pages_share_training_group_not_independent_evaluation(self):
        result = prepare(self.source, self.output, self.permission, [1, 2], dpi=72)
        self.assertEqual(result['split'], 'train')
        self.assertEqual(result['project_group_id'], 'related-project')
        self.assertEqual(result['project_relationships_to_existing_corpus'], 'unverified_not_scored')
        self.assertEqual(result['missing_annotation_policy'], 'ignore_unreviewed_not_empty_background')


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


if __name__ == '__main__':
    unittest.main()
