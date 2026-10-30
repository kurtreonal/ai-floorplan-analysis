const stages = [
  ['Planning', ['draft', 'uploaded']], ['Analysis', ['processing', 'needs_review']],
  ['Design', ['layout_ready', 'routing_ready']], ['Estimates & reports', ['estimated', 'report_ready']],
]
export function ProjectOverview({ projects }) {
  const counts = stages.map(([label, statuses]) => ({ label, count: projects.filter(x => statuses.includes(x.status)).length }))
  const max = Math.max(1, ...counts.map(x => x.count))
  const months = Array.from({ length: 6 }, (_, i) => { const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - 5 + i); return d })
  const activity = months.map(d => ({ label: d.toLocaleDateString(undefined, { month: 'short' }), count: projects.filter(p => { const date = new Date(p.created_at); return date.getMonth() === d.getMonth() && date.getFullYear() === d.getFullYear() }).length }))
  const peak = Math.max(1, ...activity.map(x => x.count))
  return <section className="workflow-overview" aria-label="Project dashboard">
    <article className="workflow-panel"><h2>Project progress</h2><p>Current stage across your available projects.</p>
      <div className="workflow-bars">{counts.map(x => <div key={x.label}><span>{x.label}</span><span className="workflow-track"><span style={{ width: `${100 * x.count / max}%` }}/></span><strong>{x.count}</strong></div>)}</div>
    </article>
    <article className="workflow-panel"><h2>New projects</h2><p>Projects created over the last six months.</p>
      <div className="workflow-columns">{activity.map((x, i) => <div key={i}><strong>{x.count}</strong><span style={{ height: `${Math.max(2, 78 * x.count / peak)}px` }}/><small>{x.label}</small></div>)}</div>
    </article>
  </section>
}
