import { Component, Fragment } from 'react'

import { getProjectHref } from '../../routes/projectRoutes.js'
import './viewer3d.css'


export class Viewer3DErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false, attempt: 0 }
    this.retry = this.retry.bind(this)
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  retry() {
    this.setState((state) => ({ failed: false, attempt: state.attempt + 1 }))
  }

  render() {
    if (this.state.failed) {
      return (
        <section className="viewer-3d-error" aria-labelledby="viewer-3d-error-title">
          <h1 id="viewer-3d-error-title">{this.props.title || '3D view unavailable'}</h1>
          <p role="alert">The 3D view could not start safely. The rest of the application is still available.</p>
          <div className="viewer-3d-error-actions">
            <button className="btn btn-dark" type="button" onClick={this.retry}>Try viewer again</button>
            <a href={getProjectHref(this.props.projectId)}>Back to project</a>
          </div>
        </section>
      )
    }

    return <Fragment key={this.state.attempt}>{this.props.children}</Fragment>
  }
}
