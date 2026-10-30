import { useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'

export function DraftSubmission({projectId, floorPlanId, revision, designer, onSave}) {
  const [status, setStatus] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const path = `/projects/${projectId}/floor-plans/${floorPlanId}/submission`
  useEffect(() => { const c = new AbortController(); workflowRequest(path, {signal:c.signal}).then(setStatus).catch(e => {if (!c.signal.aborted) setError(e.message)}); return () => c.abort() }, [path, revision])
  async function submit() {
    setBusy(true); setError('')
    try {
      const saved = await onSave()
      if (!saved) return
      setStatus(await workflowRequest(path, {method:'POST',body:{candidate_run_id:saved.candidate_run_id,revision_number:saved.review.revision_number}}))
    } catch(e) {setError(e.message)} finally {setBusy(false)}
  }
  return <div className="studio-draft-submission">
    {designer && <Button variant="outline" size="sm" disabled={busy} onClick={submit}>{busy?'Submitting…':'Save & submit to Admin'}</Button>}
    {status?.status && status.status!=='not_submitted' && <span role="status">Draft {status.status === 'returned'?'returned for changes':status.status} · revision {status.revision_number}</span>}
    {status?.message && ['returned','approved'].includes(status.status) && <details><summary>Admin comment</summary><p style={{whiteSpace:'pre-wrap',maxWidth:600}}>{status.message}</p></details>}
    {error && <span role="alert">{error}</span>}
  </div>
}
