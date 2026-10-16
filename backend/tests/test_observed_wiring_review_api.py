"""Synthetic machine wiring follows the real append-only review/save API."""
from tests import test_demo_interpretation_api as fixture
from app.ai.floor_plan_interpretation.candidate import (
    FloorPlanInterpretationPayload, ObservedRoutes, ObservedRouteSegment, PixelPoint,
)
from app.schemas.demo_interpretation import DemoGeneratedWiringReview


class ObservedWiringReviewApiTests(fixture.DemoInterpretationApiTests):
    def test_explicit_junction_review_reload_and_canonical_v5_preserve_shared_anchor(self):
        from copy import deepcopy
        from uuid import uuid4
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        payload=self._review_payload(complete=False,approved=False)
        payload['observed_wiring']=[dict(id='manual-wiring-0001',disposition='added',completeness='partial',elevation_meters=None,
            circuit_id='C1',points=[dict(x=10,y=50),dict(x=70,y=50),dict(x=150,y=50)],
            junction_attachments=[dict(junction_id='junction-0001',point_index=1)]),
            dict(id='manual-wiring-0002',disposition='added',completeness='partial',elevation_meters=None,circuit_id='C1',
            points=[dict(x=70,y=50),dict(x=70,y=130)],junction_attachments=[dict(junction_id='junction-0001',point_index=0)])]
        payload['observed_wiring'] += [dict(id=w.id,disposition='rejected',points=[p.model_dump() for p in w.points],
            completeness='partial',elevation_meters=None) for w in self.candidate.payload.observed_routes.segments]
        draft=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(draft.status_code,201,draft.text)
        self.assertEqual(self.client.get(path).json()['review']['observed_wiring'][0]['junction_attachments'],
            payload['observed_wiring'][0]['junction_attachments'])
        bad=deepcopy(payload);bad['expected_revision_number']=1
        bad['observed_wiring'][1]['points'][0]['x']+=1
        self.assertEqual(self.client.post(path+'/reviews',json=bad).status_code,422)
        payload.update(expected_revision_number=1,review_complete=True,approved_for_layout=True,
                       wall_thickness_meters=.15,wall_height_meters=3)
        for wire in payload['observed_wiring']:wire.update(completeness='complete',elevation_meters=2.8)
        approved=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(approved.status_code,201,approved.text)
        url=f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
        response=self.client.post(url,json=dict(candidate_run_id=self.candidate.provenance.candidate_run_id,
            review_revision_number=2,expected_layout_version_number=None,idempotency_key=str(uuid4())))
        self.assertEqual(response.status_code,201,response.text)
        saved=response.json()
        self.assertEqual(saved['extension']['extension_schema_version'],5)
        self.assertEqual(len(saved['geometry']['routes']),2)
        contacts=[d['junction_connections'][0] for d in saved['extension']['route_details']]
        self.assertEqual(contacts[0]['anchor'],contacts[1]['anchor'])
        self.assertEqual(contacts[0]['anchor'],dict(x=.7,y=.5,elevation_meters=2.8))
        self.assertEqual(self.client.get(path).json()['review']['revision_number'],2)

    def test_initial_source_contacts_survive_move_reload_and_canonical_connection_save(self):
        import json
        from hashlib import sha256
        from uuid import uuid4
        import cv2
        from sqlalchemy.orm import Session
        from app.models import FloorPlanInterpretationRun
        from app.ai.floor_plan_interpretation.device_contact_evidence import with_device_contact_evidence
        from app.ai.floor_plan_interpretation.candidate import InferenceParameter
        original=self.candidate
        image=fixture.synthetic_plan()
        cv2.line(image,(124,150),(266,150),(0,0,0),2)
        value=original.payload.model_dump(mode='json')
        value['observed_routes']['segments'][0]['points']=[dict(x=127,y=150),dict(x=263,y=150)]
        value['observed_routes']['segments'][0]['line_style']='solid'
        evidence=with_device_contact_evidence(FloorPlanInterpretationPayload.model_validate(value),image)
        self.candidate=original.model_copy(update={'payload':evidence,'provenance':original.provenance.model_copy(update={
            'inference_parameters':(InferenceParameter(name='wiring-evidence-version',value='raw-source-device-port-evidence-v7'),)})})
        encoded=self.candidate.model_dump_json()
        with Session(self.engine) as session:
            run=session.get(FloorPlanInterpretationRun,self.ids['run'])
            prior=(run.candidate_json,run.candidate_sha256)
            run.candidate_json=encoded;run.candidate_sha256=sha256(encoded.encode()).hexdigest();session.commit()
        try:
            self._login();path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
            initial=self.client.get(path)
            self.assertEqual(initial.status_code,200,initial.text)
            detected=initial.json()['observed_wiring'][0]
            self.assertEqual(len(detected['device_attachments']),2)
            self.assertTrue(detected['source_evidence_required'])
            payload=self._review_payload(complete=False,approved=False)
            for symbol in payload['symbols']:
                symbol.update(disposition='accepted',symbol_legend_id=self.ids['legend'],mounting_height_meters=1.2)
            payload['observed_wiring']=[detected]
            saved=self.client.post(path+'/reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text)
            self.assertEqual(self.client.get(path).json()['review']['observed_wiring'][0]['device_attachments'],detected['device_attachments'])
            # Move the device and its SAME attached vertex, without another path.
            payload['expected_revision_number']=1
            payload['symbols'][0]['center']=dict(x=120,y=160)
            index=next(a['point_index'] for a in detected['device_attachments'] if a['symbol_id']==payload['symbols'][0]['id'])
            payload['observed_wiring'][0]['points'][index]=dict(x=120,y=160)
            payload['observed_wiring'][0].update(disposition='corrected',completeness='complete',elevation_meters=2.8)
            payload.update(review_complete=True,approved_for_layout=True,wall_thickness_meters=.15,wall_height_meters=3)
            saved=self.client.post(path+'/reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text)
            url=f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
            layout=self.client.post(url,json=dict(candidate_run_id=self.candidate.provenance.candidate_run_id,
                review_revision_number=2,expected_layout_version_number=None,idempotency_key=str(uuid4())))
            self.assertEqual(layout.status_code,201,layout.text)
            document=layout.json()
            self.assertEqual(document['extension']['extension_schema_version'],4)
            self.assertEqual(len(document['geometry']['routes']),3) # One observed run, two installation drops.
            self.assertEqual(len(document['extension']['route_details'][0]['device_connections']),2)
            self.assertEqual(self.client.get(path).json()['review']['observed_wiring'][0]['points'][index],dict(x=120,y=160))
        finally:
            self.candidate=original
            with Session(self.engine) as session:
                run=session.get(FloorPlanInterpretationRun,self.ids['run']);run.candidate_json,run.candidate_sha256=prior
                session.commit()

    def test_touching_endpoint_connects_on_save_reload_and_persists_detach_optout(self):
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        payload=self._review_payload()
        payload.update(review_complete=False,approved_for_layout=False)
        wire=payload['observed_wiring'][0];symbol=payload['symbols'][0]
        wire['disposition']='unresolved'
        wire['points'][0]=symbol['center'].copy()
        wire['device_attachments']=[]
        response=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        loaded=self.client.get(path).json()
        self.assertEqual(loaded['review']['observed_wiring'][0]['device_attachments'],
            [{'symbol_id':symbol['id'],'point_index':0}])
        self.assertIn('floor_elevation_meters',loaded['routing_context'])
        payload['expected_revision_number']=1
        wire['auto_connect_disabled_endpoints']=[0]
        response=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(response.status_code,201,response.text)
        detached=self.client.get(path).json()['review']['observed_wiring'][0]
        self.assertEqual(detached['device_attachments'],[])
        self.assertEqual(detached['auto_connect_disabled_endpoints'],[0])

    def test_late_older_job_does_not_replace_latest_proposals_or_saved_canonical(self):
        from hashlib import sha256
        from uuid import uuid4
        from sqlalchemy import delete
        from sqlalchemy.orm import Session
        from app.models import ProcessingJob, ProcessingArtifact, FloorPlanInterpretationRun, LayoutVersion
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        saved=self.client.post(path+'/reviews',json=self._review_payload())
        self.assertEqual(saved.status_code,201,saved.text)
        layout=self.client.post(f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={'candidate_run_id':self.candidate.provenance.candidate_run_id,'review_revision_number':1,
                  'expected_layout_version_number':None,'idempotency_key':str(uuid4())})
        self.assertEqual(layout.status_code,201,layout.text)
        with Session(self.engine) as session:
            original_layouts=[(v.id,v.geometry_document) for v in session.query(LayoutVersion).filter_by(floor_plan_id=self.ids['floor_plan'])]
            jobs=[ProcessingJob(floor_plan_id=self.ids['floor_plan'],job_type='floor_plan_analysis',status='completed',progress=100) for _ in range(2)]
            session.add_all(jobs); session.flush()
            job_ids=[j.id for j in jobs]
            artifact_ids=[]; run_ids=[]
            for job in reversed(jobs):  # Older submitted job completes LAST.
                marker=uuid4().hex
                artifact=ProcessingArtifact(processing_job_id=job.id,floor_plan_page_id=self.ids['page'],
                    artifact_kind='normalized_image',relative_path=f'normalized/{marker}.png',mime_type='image/png',
                    byte_size=128,sha256=self.candidate.provenance.source_artifact_sha256,pixel_width=400,pixel_height=300)
                session.add(artifact); session.flush(); artifact_ids.append(artifact.id)
                candidate=self.candidate.model_copy(update={'provenance':self.candidate.provenance.model_copy(update={
                    'candidate_run_id':marker,'processing_job_id':job.id,'source_artifact_id':artifact.id})})
                serialized=candidate.model_dump_json()
                run=FloorPlanInterpretationRun(candidate_run_id=marker,processing_job_id=job.id,
                    floor_plan_id=self.ids['floor_plan'],floor_plan_page_id=self.ids['page'],source_artifact_id=artifact.id,
                    provider='demo_cv_baseline',candidate_json=serialized,candidate_sha256=sha256(serialized.encode()).hexdigest())
                session.add(run); session.flush(); run_ids.append(run.id)
            session.commit()
        try:
            result=self.client.get(path)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['processing_job_id'],job_ids[-1])
            with Session(self.engine) as session:
                self.assertEqual([(v.id,v.geometry_document) for v in session.query(LayoutVersion).filter_by(floor_plan_id=self.ids['floor_plan'])],original_layouts)
        finally:
            with Session(self.engine) as session:
                session.execute(delete(FloorPlanInterpretationRun).where(FloorPlanInterpretationRun.id.in_(run_ids)))
                session.execute(delete(ProcessingArtifact).where(ProcessingArtifact.id.in_(artifact_ids)))
                session.execute(delete(ProcessingJob).where(ProcessingJob.id.in_(job_ids)))
                session.commit()

    def test_explicit_attachment_save_move_detach_and_single_canonical_drop(self):
        from uuid import uuid4
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        payload=self._review_payload()
        symbol=payload['symbols'][0]
        symbol.update(mounting_height_meters=1.2,mounting_wall_id=payload['walls'][0]['id'])
        wall=payload['walls'][0]
        symbol['center']={axis:(wall['start'][axis]+wall['end'][axis])/2 for axis in ('x','y')}
        wire=payload['observed_wiring'][0]
        wire.update(disposition='corrected',points=[symbol['center'].copy(),{'x':300,'y':150}],
                    elevation_meters=2.8,device_attachments=[{'symbol_id':symbol['id'],'point_index':0}])
        saved=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        loaded=self.client.get(path).json()['review']
        self.assertEqual(loaded['observed_wiring'][0]['device_attachments'],wire['device_attachments'])
        layout_path=f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout"
        layout=self.client.post(layout_path,json={'candidate_run_id':self.candidate.provenance.candidate_run_id,
            'review_revision_number':1,'expected_layout_version_number':None,'idempotency_key':str(uuid4())})
        self.assertEqual(layout.status_code,201,layout.text)
        value=layout.json()
        self.assertEqual(len(value['geometry']['routes']),1)
        self.assertEqual(len(value['geometry']['routes'][0]['points']),3)
        self.assertEqual(value['extension']['extension_schema_version'],3)
        mount=value['extension']['symbol_details'][0]['installation']
        self.assertEqual(value['geometry']['routes'][0]['points'][0]['elevation_meters'],mount['elevation_meters'])
        self.assertEqual(mount['wall_id'],1)
        # A changed device must change its attached endpoint, not merely lie nearby.
        payload.update(expected_revision_number=1,review_complete=False,approved_for_layout=False)
        symbol['center']={'x':115,'y':155}
        bad=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(bad.status_code,422,bad.text)
        wire['points'][0]=symbol['center'].copy()
        moved=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(moved.status_code,201,moved.text)
        payload['expected_revision_number']=2
        wire['device_attachments']=[]
        detached=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(detached.status_code,201,detached.text)
        self.assertEqual(self.client.get(path).json()['review']['observed_wiring'][0]['device_attachments'],[])

    def test_reanalysis_inherits_manual_reference_without_inventing_a_saved_or_approved_review(self):
        from hashlib import sha256
        from uuid import uuid4
        from sqlalchemy import delete
        from sqlalchemy.orm import Session
        from app.models import (
            FloorPlanInterpretationRun, FloorPlanInterpretationReview,
            ProcessingArtifact, ProcessingJob,
        )
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation"
        payload=self._review_payload(complete=False,approved=False)
        for wall in payload['walls']: wall['disposition']='rejected'
        payload['walls'].append(dict(id='manual-wall-0001',disposition='added',
            start={'x':10.25,'y':15.75},end={'x':100.5,'y':15.75}))
        payload['observed_wiring'].append(dict(id='manual-wiring-0001',disposition='added',
            points=[{'x':20.125,'y':30.25},{'x':80.375,'y':30.25}],
            completeness='partial',elevation_meters=None))
        payload['generated_wiring']=[]
        saved=self.client.post(path+'/reviews',json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        before=saved.json()['review']
        marker=uuid4().hex
        with Session(self.engine) as session:
            job=ProcessingJob(floor_plan_id=self.ids['floor_plan'],job_type='floor_plan_analysis',
                              status='completed',progress=100)
            session.add(job); session.flush()
            artifact=ProcessingArtifact(processing_job_id=job.id,
                floor_plan_page_id=self.ids['page'],artifact_kind='normalized_image',
                relative_path=f'normalized/reanalysis-{marker}.png',mime_type='image/png',
                byte_size=128,sha256=self.candidate.provenance.source_artifact_sha256,
                pixel_width=400,pixel_height=300)
            session.add(artifact); session.flush()
            candidate=self.candidate.model_copy(update={'provenance':self.candidate.provenance.model_copy(
                update={'candidate_run_id':marker,'processing_job_id':job.id,
                        'source_artifact_id':artifact.id})})
            serialized=candidate.model_dump_json()
            run=FloorPlanInterpretationRun(candidate_run_id=marker,processing_job_id=job.id,
                floor_plan_id=self.ids['floor_plan'],floor_plan_page_id=self.ids['page'],
                source_artifact_id=artifact.id,provider='demo_cv_baseline',
                candidate_sha256=sha256(serialized.encode()).hexdigest(),candidate_json=serialized)
            session.add(run); session.commit()
            new_run_id=run.id; new_job_id=job.id; new_artifact_id=artifact.id
        try:
            loaded=self.client.get(path)
            self.assertEqual(loaded.status_code,200,loaded.text)
            data=loaded.json()
            self.assertIsNone(data['review'])
            self.assertEqual(data['draft_walls'],before['walls'])
            self.assertEqual(data['observed_wiring'][1:],before['observed_wiring'][1:])
            self.assertEqual(data['observed_wiring'][0]['disposition'],'rejected')
            self.assertEqual(data['generated_wiring'],[])
            self.assertEqual(data['candidate'],candidate.model_dump(mode='json'))
            # Save/reload on the new run preserves the reference and creates only
            # an ordinary unfinished revision, not a fake inherited approval.
            payload.update(candidate_run_id=marker,walls=data['draft_walls'],
                           observed_wiring=data['observed_wiring'])
            saved=self.client.post(path+'/reviews',json=payload)
            self.assertEqual(saved.status_code,201,saved.text)
            self.assertFalse(saved.json()['review']['approved_for_layout'])
            self.assertEqual(self.client.get(path).json()['observed_wiring'],data['observed_wiring'])
            history=self.client.get(path+f"?processing_job_id={self.ids['job']}").json()
            self.assertEqual(history['review'],before)
            self._login('other')
            self.assertEqual(self.client.get(path).status_code,404)
        finally:
            with Session(self.engine) as session:
                session.execute(delete(FloorPlanInterpretationReview).where(
                    FloorPlanInterpretationReview.interpretation_run_id==new_run_id))
                session.execute(delete(FloorPlanInterpretationRun).where(
                    FloorPlanInterpretationRun.id==new_run_id))
                session.execute(delete(ProcessingArtifact).where(ProcessingArtifact.id==new_artifact_id))
                session.execute(delete(ProcessingJob).where(ProcessingJob.id==new_job_id))
                session.commit()

    def test_dashed_catalog_type_is_saved_and_shown_in_bom_without_final_quantities(self):
        from sqlalchemy.orm import Session
        from app.models import SymbolLegend
        self._login()
        with Session(self.engine) as session:
            legend=SymbolLegend(class_id=17990,name='Raceway conduit concealed under floor [pdf-test:p1:L10]',is_active=True)
            session.add(legend)
            session.commit()
            legend_id=legend.id
        try:
            payload=self._review_payload(complete=False,approved=False)
            payload['observed_wiring'][0].update(disposition='unresolved',line_style='dashed',
                wiring_legend_id=legend_id,wiring_legend_name='forged client name')
            original=self.candidate.model_dump_json()
            saved=self.client.post(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews",json=payload)
            self.assertEqual(saved.status_code,201,saved.text)
            wire=saved.json()['review']['observed_wiring'][0]
            self.assertEqual(wire['installation_method'],'concealed_under_floor')
            self.assertIn('Raceway conduit concealed under floor',wire['wiring_legend_name'])
            self.assertIsNone(wire['elevation_meters'])
            result=self.client.get(f"/api/projects/{self.ids['project']}/bom")
            self.assertEqual(result.status_code,200,result.text)
            row=result.json()['wiring_types'][0]
            self.assertEqual(row['wiring_legend_id'],legend_id)
            self.assertEqual(row['status'],'draft_unmeasured')
            self.assertIsNone(row['quantity_meters'])
            self.assertEqual(result.json()['components'],[])
            self.assertEqual(self.candidate.model_dump_json(),original)
            self._login('other')
            self.assertEqual(self.client.get(f"/api/projects/{self.ids['project']}/bom").status_code,404)
        finally:
            with Session(self.engine) as session:
                session.delete(session.get(SymbolLegend,legend_id))
                session.commit()

    def test_disconnected_branches_remain_unresolved_on_normal_save_and_reload(self):
        self._login()
        path=f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload=self._review_payload(complete=False,approved=False)
        payload["walls"]=[]
        payload["symbols"]=[{"id":f"manual-symbol-{i:04d}","disposition":"unresolved",
            "center":{"x":x,"y":150},"symbol_legend_id":self.ids["legend"]}
            for i,x in enumerate((110,130,280,300),1)]
        payload["generated_wiring"]=[]
        saved=self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        data=saved.json()
        wires=data["review"]["generated_wiring"]
        self.assertEqual(wires,[])
        self.assertFalse(data["review"]["review_complete"])
        self.assertFalse(data["review"]["approved_for_layout"])
        payload.update(expected_revision_number=1,generated_wiring=wires)
        saved=self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        loaded=self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.json()["review"]["generated_wiring"],wires)
        self.assertEqual(len(loaded.json()["candidate"]["payload"]["observed_routes"]["segments"]),1)

    def test_manual_mapped_device_does_not_invent_wiring_without_explicit_connection(self):
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload(complete=False,approved=False)
        payload["symbols"][0]["disposition"]="unresolved"
        payload["symbols"].append({"id":"manual-symbol-0001","disposition":"unresolved",
            "center":{"x":150,"y":150},"symbol_legend_id":self.ids["legend"]})
        payload["generated_wiring"]=[]
        original=self.candidate.model_dump_json()
        saved=self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        data=saved.json()
        wires=data["review"]["generated_wiring"]
        self.assertEqual(wires,[])
        self.assertEqual(data["generated_wiring"],wires)
        self.assertFalse(data["review"]["review_complete"])
        self.assertFalse(data["review"]["approved_for_layout"])
        self.assertEqual(data["review"]["symbols"][-1]["disposition"],"unresolved")
        self.assertIsNotNone(data["review"]["symbols"][-1]["class_name"])
        loaded=self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.json()["review"]["generated_wiring"],wires)
        self.assertEqual(self.candidate.model_dump_json(),original)
        # A second ordinary save retains exactly the prior route, including removal.
        payload["expected_revision_number"]=1
        payload["generated_wiring"]=[]
        saved=self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        self.assertEqual(saved.json()["review"]["generated_wiring"],[DemoGeneratedWiringReview.model_validate(w).model_dump() for w in payload["generated_wiring"]])

    def test_generated_paths_save_without_confirmation_and_never_become_observed_quantities(self):
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload(complete=False, approved=False)
        payload["generated_wiring"] = [{
            "id":"manual-route-0001", "disposition":"unresolved", "algorithm":"astar",
            "source_device_id":payload["symbols"][0]["id"], "target_id":"segment-0001",
            "target_kind":"visible_trace", "points":[{"x":20,"y":20},{"x":20,"y":30}],
            "completeness":"partial", "elevation_meters":None,
        }]
        saved = self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        loaded = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.status_code,200,loaded.text)
        self.assertEqual(loaded.json()["review"]["generated_wiring"],[DemoGeneratedWiringReview.model_validate(w).model_dump() for w in payload["generated_wiring"]])
        self.assertFalse(loaded.json()["review"]["review_complete"])
        self.assertEqual(len(loaded.json()["candidate"]["payload"]["observed_routes"]["segments"]),1)
        # Even a client marking generated geometry complete cannot launder it
        # into observed routes or cost quantities through measured layout save.
        payload.update(expected_revision_number=1,review_complete=True,approved_for_layout=True,
                       wall_thickness_meters=.15,wall_height_meters=3.)
        payload["generated_wiring"][0].update(disposition="added",completeness="complete",elevation_meters=2.8)
        saved = self.client.post(path,json=payload)
        self.assertEqual(saved.status_code,201,saved.text)
        from uuid import uuid4
        layout = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={"candidate_run_id":self.candidate.provenance.candidate_run_id,"review_revision_number":2,
                  "expected_layout_version_number":None,"idempotency_key":str(uuid4())})
        self.assertEqual(layout.status_code,201,layout.text)
        self.assertEqual(layout.json()["geometry"]["routes"],[])

    def test_generated_draft_rejects_foreign_anchors_and_outside_points(self):
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload(complete=False,approved=False)
        wire = {"id":"manual-route-0001","disposition":"unresolved","algorithm":"astar",
                "source_device_id":"symbol-9999","target_id":"segment-0001","target_kind":"visible_trace",
                "points":[{"x":20,"y":20},{"x":20,"y":30}],"completeness":"partial"}
        payload["generated_wiring"]=[wire]
        self.assertEqual(self.client.post(path,json=payload).status_code,422)
        wire["source_device_id"]=payload["symbols"][0]["id"]
        wire["points"][1]["x"]=401
        self.assertEqual(self.client.post(path,json=payload).status_code,422)

    @staticmethod
    def candidate_payload():
        base = fixture.DemoInterpretationApiTests.candidate_payload()
        routes = ObservedRoutes(state="partial", segments=(ObservedRouteSegment(
            id="segment-0001", points=(PixelPoint(x=20, y=30), PixelPoint(x=80, y=90)),
            evidence_refs=("region:region-0001",), ambiguity="ambiguous",
        ),))
        values = base.model_dump(mode="json")
        values["document_state"] = "partial"
        values["observed_routes"] = routes.model_dump(mode="json")
        return FloorPlanInterpretationPayload.model_validate(values)

    def _review_payload(self, *args, **kwargs):
        payload = super()._review_payload(*args, **kwargs)
        payload["observed_wiring"] = [{
            "id": "segment-0001", "disposition": "rejected",
            "points": [{"x": 20., "y": 30.}, {"x": 80., "y": 90.}],
            "completeness": "complete", "elevation_meters": None,
        }]
        return payload

    def test_observed_wiring_revision_save_reload_and_elevation_gate(self):
        # The inherited test replaces the wiring collection with a manual route;
        # exercise actual machine identity coverage separately instead.
        self._login()
        path = f"/api/floor-plans/{self.ids['floor_plan']}/interpretation/reviews"
        payload = self._review_payload()
        wire = payload["observed_wiring"][0]
        wire.update(disposition="corrected", elevation_meters=2.8)
        wire["points"][1]["x"] = 100.
        saved = self.client.post(path, json=payload)
        self.assertEqual(saved.status_code, 201, saved.text)
        loaded = self.client.get(f"/api/floor-plans/{self.ids['floor_plan']}/interpretation")
        self.assertEqual(loaded.status_code, 200, loaded.text)
        self.assertIn('segment-0001', loaded.text)
        payload["expected_revision_number"] = 1
        payload["observed_wiring"] = []
        rejected = self.client.post(path, json=payload)
        self.assertEqual(rejected.status_code, 422, rejected.text)
        self.assertEqual(rejected.json()["detail"]["error"]["code"], "REVIEW_INCOMPLETE")
        from uuid import uuid4
        saved_layout = self.client.post(
            f"/api/projects/{self.ids['project']}/floors/{self.ids['floor']}/floor-plans/{self.ids['floor_plan']}/interpretation/layout",
            json={"candidate_run_id": self.candidate.provenance.candidate_run_id,
                  "review_revision_number": 1, "expected_layout_version_number": None,
                  "idempotency_key": str(uuid4())},
        )
        self.assertEqual(saved_layout.status_code, 201, saved_layout.text)
        self.assertEqual(saved_layout.json()["geometry"]["routes"][0]["points"][1]["x"], 1.)
        self.assertEqual(saved_layout.json()["extension"]["route_details"][0]["route_kind"], "observed")
