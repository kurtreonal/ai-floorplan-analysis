"""Analysis completion is not electrical connectivity or designer approval."""
import json
from app.ai.floor_plan_interpretation.candidate import WiringRecoveryReport
from app.schemas.processing_job import SourceConnectivitySummary
from app.repositories.floor_plan_interpretation_repository import list_job_runs
from app.services.interpretation_page_outcome_service import list_page_outcomes


def summarize_connectivity(payloads, *, expected_pages):
    connected=unresolved=absent=unassessed=assessed_pages=0
    incomplete=False
    for payload in payloads:
        routes=payload.get('observed_routes',{})
        if not routes.get('recovery'):continue
        report=WiringRecoveryReport.model_validate(routes['recovery'])
        assessed_pages+=1
        connected+=sum(d.state=='observed_recovered' for d in report.devices)
        unresolved+=sum(d.state=='unresolved_observed' for d in report.devices)
        absent+=sum(d.state=='no_usable_observed_path' for d in report.devices)
        unassessed+=report.unassessed_devices
        incomplete |= bool(routes.get('truncated') or report.stop_reason=='resource_limit'
                           or any(p.failed_windows for p in report.passes))
    if not assessed_pages:return None  # Legacy response remains byte-shape compatible.
    missing=max(0,expected_pages-assessed_pages)
    total=connected+unresolved+absent+unassessed
    state='unavailable' if not total else 'unresolved' if unresolved+absent+unassessed+missing or incomplete else 'observed_recovered'
    return SourceConnectivitySummary(state=state,connected_devices=connected,
        unresolved_devices=unresolved,no_usable_path_devices=absent,unassessed_devices=unassessed,
        unassessed_pages=missing,search_incomplete=incomplete or bool(missing) or not total)


def job_connectivity_summary(session, *, job_id):
    runs=list_job_runs(session,job_id=job_id)
    if not runs:return None
    outcomes=list_page_outcomes(session,processing_job_id=job_id)
    selected=sum(row.selection_state=='selected' for row in outcomes)
    # Immutable candidates only. Reviews and generated paths cannot improve a
    # historical detector score or silently promote source recovery to approval.
    payloads=[]
    for run in runs:
        try:payloads.append(json.loads(run.candidate_json)['payload'])
        except (ValueError,KeyError,TypeError):continue
    try:return summarize_connectivity(payloads,expected_pages=selected or len(runs))
    except (ValueError,TypeError):return SourceConnectivitySummary(state='unavailable',connected_devices=0,
        unresolved_devices=0,no_usable_path_devices=0,unassessed_devices=0,
        unassessed_pages=selected or len(runs),search_incomplete=True)
