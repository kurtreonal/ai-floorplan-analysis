import unittest
from copy import deepcopy
from PIL import Image
from prepare_switch_replay import checked_targets, context_views


class SwitchReplayTests(unittest.TestCase):
    def evidence(self):
        return {'human_review_claim':False,'production_approval':False,
            'missing_annotation_policy':'ignore_unreviewed_not_empty_background',
            'annotation_origin':'assistant_visual_under_user_development_authorization',
            'user_statement':'Delegated local development annotation',
            'source_sha256':'a'*64,'source_image_sha256':'b'*64,'page_number':7,
            'project_group_id':'related-project','targets':[{'id':'switch01','class_id':62,
            'label':'One gang device switch','box':[100,120,140,160],
            'source_legend_entry':'source:L04','meaning_evidence':'Source legend S/Sa'}]}

    def classes(self):
        rows=[{'id':i,'label':str(i),'legend_entry':f'original:{i}'} for i in range(80)]
        rows[62]['label']='One gang device switch';rows[63]['label']='Two gang device switch'
        rows[64]['label']='Three gang device switch'
        return rows

    def test_source_alias_and_original_head_identity_survive_without_fake_approval(self):
        target=checked_targets(self.evidence(),self.classes(),800,800)[0]
        self.assertEqual(target['legend_entry'],'original:62')
        self.assertEqual(target['source_legend_entry'],'source:L04')
        self.assertEqual(target['pdf_sha256'],'a'*64)
        self.assertEqual(target['source_sha256'],'b'*64)
        self.assertEqual(target['split'],'train');self.assertFalse(target['human_review_claim'])
        self.assertEqual(target['project_group_id'],'related-project')

    def test_unresolved_subtypes_forged_review_bad_boxes_and_duplicate_records_rejected(self):
        for change in ({'class_id':66},{'box':[-1,120,140,160]},{'box':[100,120,900,160]},
                       {'box':[100,120,float('nan'),160]},{'id':'../outside'},
                       {'label':'Three way device switch'},{'source_legend_entry':''},{'meaning_evidence':''}):
            evidence=self.evidence();evidence['targets'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                checked_targets(evidence,self.classes(),800,800)
        for change in ({'human_review_claim':True},{'production_approval':True},
                       {'missing_annotation_policy':'empty_background'}):
            evidence=self.evidence();evidence.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                checked_targets(evidence,self.classes(),800,800)
        evidence=self.evidence();evidence['targets']*=2
        with self.assertRaises(ValueError):checked_targets(evidence,self.classes(),800,800)

    def test_both_tile_phases_vary_and_neighbor_classes_stay_supervised(self):
        targets=[{'record_id':'one','class_id':62,'source_box':[380,380,410,410]},
                 {'record_id':'lamp','class_id':56,'source_box':[415,380,430,410]}]
        with Image.new('RGB',(800,800),'white') as image:
            views=list(context_views(image,targets,targets[:1],(1,)))
        self.assertEqual(len(views),9)
        self.assertEqual(len({tuple(v[4]) for v in views}),9)
        for tile,lines,ids,scale,origin,focus in views:
            self.assertEqual(ids,['one','lamp'])
            self.assertEqual([int(line.split()[0]) for line in lines],[62,56])
            self.assertEqual(tile.size,(256,256));tile.close()
        self.assertEqual(len({v[4][0] for v in views}),3)
        self.assertEqual(len({v[4][1] for v in views}),3)

    def test_scaled_views_are_isotropic_and_do_not_relabel_circuit_suffixes(self):
        target={'record_id':'two','class_id':63,'source_box':[360,360,400,380]}
        with Image.new('RGB',(800,800),'white') as image:
            for tile,lines,ids,scale,origin,focus in context_views(image,[target],[target],(.5,.75,1)):
                values=lines[0].split()
                self.assertEqual(values[0],'63');self.assertEqual(ids,['two'])
                self.assertAlmostEqual(float(values[3])/float(values[4]),2,places=5)
                tile.close()
