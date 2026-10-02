from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from PIL import Image
from prepare_symbol_quality_experiment import build, digest, recovery_window, tile_positions


class QualityDatasetTests(TestCase):
    def test_recovered_placement_uses_real_inference_window_without_clipping(self):
        box = [433.2, 1047.9, 470.6, 1085.3]
        x, y, alignment = recovery_window(1552, 3264, box)
        self.assertIn((x, y), tile_positions(1552, 3264, dual_phase=True))
        self.assertEqual(alignment, 'native_inference_window')
        self.assertTrue(x <= box[0] < box[2] <= x+256)
        self.assertTrue(y <= box[1] < box[3] <= y+256)

    def test_seam_fallback_keeps_entire_target_and_records_limitation(self):
        box = [170, 170, 420, 420]
        x, y, alignment = recovery_window(800, 800, box)
        self.assertEqual(alignment, 'centered_fallback_no_full_native_window')
        self.assertTrue(x <= box[0] < box[2] <= x+256)
        self.assertTrue(y <= box[1] < box[3] <= y+256)

    def fixture(self, root):
        base=root/'base'; source=root/'source'; source.mkdir()
        for folder in ('images/train','labels/train'): (base/folder).mkdir(parents=True)
        Image.new('RGB',(256,256),'white').save(source/'sheet-08.jpg')
        Image.new('RGB',(256,256),'white').save(base/'images/train/a.png')
        (base/'labels/train/a.txt').write_text('0 .5 .5 .1 .1\n')
        (base/'data.yaml').write_text('path: old\ntrain: images/train\nval: images/train\nnc: 1\nnames:\n  0: Light\n')
        manifest={'required_loss':'positive_and_reviewed_box_only','all_eligible_entries':True,
                  'classes':[{'id':0,'legend_entry':'L1','label':'Light','samples':1}],
                  'reviewed_targets':[{'record_id':'old','class_id':0}], 'images':[]}
        (base/'manifest.json').write_text(json.dumps(manifest))
        row={'id':'new','sheet_id':'sheet-08','source_sha256':digest(source/'sheet-08.jpg'),
             'legend_entry':'L1','bbox':[100,100,120,120],'split':'train','group':'3'}
        recovered=root/'recovered.json'; recovered.write_text(json.dumps({'records':[row]}))
        review=root/'review.json'; data={'reviewer':'assistant_visual_inspection','scope':'local_development_only',
              'sheets':[{'sheet_id':'sheet-08','source_sha256':row['source_sha256'],
                         'meaning':'grid bubble','regions':[[.02,.02,.12,.12]]}]}
        review.write_text(json.dumps(data))
        checkpoint=root/'base.pt'; checkpoint.write_bytes(b'fixture only')
        return base,recovered,review,source,checkpoint

    def test_preserves_class_ids_positives_sources_and_versions_negative_evidence(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); args=self.fixture(root); before=digest(args[3]/'sheet-08.jpg')
            result=build(*args,root/'output')
            self.assertEqual(result['recovered_placements'],1)
            self.assertEqual(result['synthetic_negative_images'],4)
            manifest=json.loads((root/'output/manifest.json').read_text())
            self.assertEqual(manifest['classes'][0]['id'],0)
            self.assertEqual(manifest['reviewed_background_images'][0]['reviewer'],'assistant_visual_inspection')
            self.assertEqual(digest(args[3]/'sheet-08.jpg'),before)
            self.assertEqual((root/'output/labels/train/a.txt').read_text(),(args[0]/'labels/train/a.txt').read_text())
            with self.assertRaises(FileExistsError): build(*args,root/'output')

    def test_negative_cannot_overlap_positive_and_changed_source_fails(self):
        with TemporaryDirectory() as folder:
            root=Path(folder); args=self.fixture(root)
            review=json.loads(args[2].read_text()); altered=deepcopy(review)
            altered['sheets'][0]['regions']=[[.3,.3,.5,.5]]
            args[2].write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'overlaps'): build(*args,root/'conflict')
            args[2].write_text(json.dumps(review)); (args[3]/'sheet-08.jpg').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'): build(*args,root/'changed')
