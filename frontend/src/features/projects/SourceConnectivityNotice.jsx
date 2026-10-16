export function SourceConnectivityNotice({summary}) {
  if(!summary)return null
  return <p className="plan-row-notice" role="status" aria-label="Source connectivity">
    {summary.state==='unavailable' ? 'Source connectivity not established.' : <>{summary.connected_devices} devices with source-supported contacts · {summary.unresolved_devices + summary.no_usable_path_devices + summary.unassessed_devices} unresolved.</>}
    {summary.search_incomplete && <> Search incomplete{summary.unassessed_pages>0 ? ` · ${summary.unassessed_pages} pages unassessed` : ''}.</>}
    {' '}Generated routes are separate proposals; source contacts are not human approval.
  </p>
}
