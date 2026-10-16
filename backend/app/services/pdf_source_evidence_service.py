"""Immutable, hash-bound JSON sidecar, without altering the PNG artifact contract."""
from hashlib import sha256
import json
from uuid import uuid4

from app.ai.floor_plan_interpretation.candidate import InferenceParameter
from app.ai.floor_plan_interpretation.pdf_evidence import extract_pdf_evidence, PdfEvidenceError, VERSION
from app.ai.floor_plan_interpretation.pdf_views import propose_pdf_views, view_summary, VERSION as VIEW_VERSION
from app.ai.floor_plan_interpretation.scoped_analysis import VERSION as PIPELINE_VERSION
from app.core.config import get_processed_directory, get_upload_directory
from app.services.source_identity import resolve_stored_original


def prepare_pdf_source_evidence(*, floor_plan, source_manifest, page, artifact, settings):
    source=resolve_stored_original(get_upload_directory(settings),floor_plan.storage_path)
    if (source.stat().st_size!=floor_plan.file_size
            or sha256(source.read_bytes()).hexdigest()!=source_manifest.original_sha256):
        raise PdfEvidenceError('ORIGINAL_INTEGRITY_FAILED')
    evidence=extract_pdf_evidence(source,page_number=page.page_number,
        width=artifact.record.pixel_width,height=artifact.record.pixel_height)
    if evidence['source_sha256']!=source_manifest.original_sha256:
        raise PdfEvidenceError('ORIGINAL_INTEGRITY_FAILED')
    views=propose_pdf_views(evidence)
    evidence['view_proposals']=view_summary(views)
    root=get_processed_directory(settings).resolve(strict=True)
    directory=root/'pdf-source-evidence'/uuid4().hex
    directory.mkdir(parents=True,exist_ok=False)
    if not directory.resolve(strict=True).is_relative_to(root):
        raise PdfEvidenceError('PDF_EVIDENCE_UNSAFE_OUTPUT')
    destination=directory/'evidence.json'
    with destination.open('x',encoding='utf-8') as stream:
        json.dump(evidence,stream,separators=(',',':'),ensure_ascii=True)
    digest=sha256(destination.read_bytes()).hexdigest()
    parameters=(
        InferenceParameter(name='pdf-evidence-version',value=VERSION),
        InferenceParameter(name='pdf-parser-runtime',value=json.dumps(evidence['parser_runtime'],separators=(',',':'))),
        InferenceParameter(name='pdf-evidence-sha256',value=digest),
        InferenceParameter(name='pdf-evidence-reference',value=destination.relative_to(root).as_posix()),
        InferenceParameter(name='pdf-view-configuration',value=VIEW_VERSION),
        InferenceParameter(name='source-view-pipeline-version',value=PIPELINE_VERSION),
        InferenceParameter(name='pdf-source-capability',value=evidence['capability']),
        InferenceParameter(name='pdf-source-rotation-degrees',value=str(evidence['rotation'])),
        InferenceParameter(name='source-view-regions',value=json.dumps([
            {key:view[key] for key in ('label','region','state')}
            for view in view_summary(views)],separators=(',',':'))),
    )
    return evidence,views,parameters
