import { useEffect, useState } from 'react'
import { workflowRequest } from '../../api/clientWorkflow.js'
import { Button } from '../../components/ui/button.jsx'

export function AdminActivity() {
  const [rows, setRows] = useState([]), [error, setError] = useState(''), [revision, setRevision] = useState(0)
  useEffect(() => { const c = new AbortController(); workflowRequest('/admin/activity', { signal: c.signal }).then(setRows).catch(e => { if (e.name !== 'AbortError') setError(e.message) }); return () => c.abort() }, [revision])
  return <section className="workflow-panel"><header className="account-section-heading"><div><h2>Activity log</h2><p>Account removals, saved drafts and administrative changes. Project history is preserved.</p></div><Button variant="outline" onClick={() => setRevision(x => x + 1)}>Refresh</Button></header>{error && <p role="alert">{error}</p>}<div className="studio-table-scroll"><table className="studio-project-table"><thead><tr><th>When</th><th>Action</th><th>Record</th><th>Details</th><th>By</th></tr></thead><tbody>{rows.map(x => <tr key={x.id}><td>{new Date(x.created_at + (x.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString()}</td><td>{x.action.replaceAll('_', ' ')}</td><td>{x.target_type} #{x.target_id}</td><td>{x.summary}</td><td>User #{x.actor_id}</td></tr>)}</tbody></table></div>{!rows.length && <p>No recorded changes yet.</p>}</section>
}
