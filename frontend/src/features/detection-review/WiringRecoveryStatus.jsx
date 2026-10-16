const reasons={ambiguous_contact:'Overlapping ports: no unique source attachment.',partial_source_evidence:'Nearby ink remains unresolved; it is not a usable wire connection.',
  no_supported_path_after_search:'No supported observed path found. This does not establish that wiring is absent.',resource_limit:'Recovery reached its configured limit; source wiring remains unresolved.',
  missing_symbol_bounds:'No usable symbol bounds; source port cannot be inspected.',outside_plan_scope:'Device lies outside a recognized plan view; no cross-view connection inferred.',recovery_method_failed:'A recovery method failed; missing wiring remains unresolved.'}
export function WiringRecoveryStatus({report,presentations={}}) {
  if(!report)return null
  const unresolved=report.devices.filter(d=>d.state!=='observed_recovered')
  return <details><summary>Source recovery · {report.devices.length-unresolved.length} connected · {unresolved.length+(report.unassessed_devices || 0)} unresolved</summary>
    <p>Analysis-time source audit; later canvas edits may differ. Proposals are not human approval. Stop: {report.stop_reason.replaceAll('_',' ')}. Generated routes remain separate.</p>
    {report.devices.length===0 && <p>No devices could be audited. This is not proof of absent devices or wiring.</p>}
    {report.unassessed_devices>0 && <p>{report.unassessed_devices} devices exceeded the audit budget and remain unassessed.</p>}
    <ul>{report.passes.map(p=><li key={p.method}>{p.method.replaceAll('_',' ')}: {p.windows} windows, {p.added_paths} added paths, {p.added_contacts} added contacts.{p.failed_windows>0 && <> {p.failed_windows} windows failed; prior source evidence was retained.</>}</li>)}</ul>
    <ul>{unresolved.map(d=><li key={d.symbol_id}>{presentations[d.symbol_id]?.label || d.symbol_id}: {reasons[d.reason]}</li>)}</ul>
  </details>
}
