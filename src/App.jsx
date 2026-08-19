const pipelineSteps = [
  {
    title: 'Floor plan input',
    desc: 'Upload a digital blueprint or a photo of a hand-drawn plan.',
    tag: 'JPG · PNG · PDF',
  },
  {
    title: 'AI image recognition',
    desc: 'OpenCV preprocessing, grayscale and noise removal, then a Hough line transform detects every wall.',
    tag: 'OpenCV',
  },
  {
    title: 'Symbol detection',
    desc: 'YOLOv8, trained on a Roboflow dataset, classifies outlets, switches, lights and data ports.',
    tag: 'YOLOv8',
  },
  {
    title: 'Layout generation',
    desc: 'Konva.js renders an editable 2D canvas; Three.js builds the matching 3D walls.',
    tag: 'Konva · Three.js',
  },
  {
    title: 'Spatial routing',
    desc: 'An A* pathfinding algorithm routes wire runs around walls and totals the length in metres.',
    tag: 'A* search',
  },
  {
    title: 'Cost estimation',
    desc: 'Wire lengths and device counts price against a live materials database.',
    tag: 'SQL pricing',
  },
]

const features = [
  {
    title: '2D / 3D toggle',
    desc: 'Drag walls and devices on a precise 2D canvas, then flip to a lit 3D walkthrough with one click — same file, two views.',
    spec: 'Room(24.98m²)',
    icon: `
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="30" height="30" rx="2" stroke="#8FD4E4" stroke-width="1.4"/>
        <path d="M2 22h12v10H2z" stroke="#FF6A3D" stroke-width="1.4"/>
        <path d="M9 2v20M2 12h30" stroke="#8FD4E4" stroke-width="1"/>
      </svg>
    `,
  },
  {
    title: 'Editable symbols',
    desc: 'Every outlet, switch and light the AI places is a real object — correct, move or relabel any of them by hand.',
    spec: 'Outlets · switches · lights · data',
    icon: `
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
        <circle cx="17" cy="17" r="15" stroke="#8FD4E4" stroke-width="1.4"/>
        <path d="M9 17h16M17 9v16" stroke="#FF6A3D" stroke-width="1.4"/>
        <circle cx="17" cy="17" r="3" fill="#FF6A3D"/>
      </svg>
    `,
  },
  {
    title: 'Bill of materials',
    desc: 'Wire length, device count and total cost, exported as a PDF report you can send straight to a supplier.',
    spec: 'Auto-priced · PDF export',
    icon: `
      <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden="true">
        <path d="M6 3h16l7 7v21H6z" stroke="#8FD4E4" stroke-width="1.4"/>
        <path d="M22 3v7h7" stroke="#8FD4E4" stroke-width="1.4"/>
        <path d="M11 16h12M11 21h12M11 26h7" stroke="#FF6A3D" stroke-width="1.4"/>
      </svg>
    `,
  },
]

const footerColumns = [
  { title: 'PRODUCT', links: ['How it works', 'Features', 'Pricing'] },
  { title: 'COMPANY', links: ['About', 'Contact', 'Careers'] },
  { title: 'RESOURCES', links: ['Documentation', 'Support', 'Status'] },
]

function App() {
  return (
    <div className="ved-app">
      <header className="site-header">
        <div className="nav-wrap">
          <details className="nav-menu">
            <summary aria-label="Open navigation menu">
              <span aria-hidden="true" />
              <span aria-hidden="true" />
              <span aria-hidden="true" />
            </summary>
            <nav className="nav-menu-links" aria-label="Tablet navigation">
              <a href="#pipeline">How it works</a>
              <a href="#features">Features</a>
              <a href="#cta">Pricing</a>
              <a href="#cta">Docs</a>
            </nav>
          </details>

          <Logo />

          <nav className="nav-links" aria-label="Main navigation">
            <a href="#pipeline">How it works</a>
            <a href="#features">Features</a>
            <a href="#cta">Pricing</a>
            <a href="#cta">Docs</a>
          </nav>

          <div className="nav-cta">
            <a href="#" className="btn btn-ghost">Sign in</a>
            <a href="#cta" className="btn btn-accent">Get started</a>
          </div>
        </div>
      </header>

      <main>
        <section className="hero-section">
          <div className="hero-inner">
            <div className="hero-copy">
              <div className="eyebrow mono">AI-POWERED FLOOR PLAN &amp; WIRING DESIGN</div>
              <h1>
                Plan, analyze,
                <br />
                and <em>visualize</em>
                <br />
                your wiring.
              </h1>
              <p className="lead">
                Upload a floor plan or draw one from scratch. VED detects outlets, switches and lights, routes every wire run, and hands you a 2D/3D layout with a full cost estimate — in minutes, not days.
              </p>

              <div className="hero-ctas">
                <a href="#cta" className="btn btn-accent btn-large">Create a floor plan</a>
                <a href="#cta" className="btn btn-ghost btn-large">Upload a floor plan →</a>
              </div>

              <div className="hero-note mono">
                <span>YOLOv8 symbol detection</span>
                <span>A* wire routing</span>
                <span>PDF bill of materials</span>
              </div>
            </div>

            <div className="blueprint-card" aria-label="Floor plan blueprint preview">
              <div className="blueprint-head">
                <span>
                  FIG. 01 — <b>RESIDENTIAL UNIT</b>
                </span>
                <span>SCALE 1:50</span>
              </div>

              <svg className="draw-svg" viewBox="0 0 420 300" role="img" aria-label="Residential unit blueprint illustration">
                <path className="outline" d="M30,40 H260 V130 H390 V260 H120 V190 H30 Z" />
                <path className="outline partition" d="M120,130 V190" />
                <path className="route route-a" d="M55,60 L55,150 L200,150 L200,220 L350,220" />
                <path className="route route-b" d="M240,60 L240,150 L350,150" />
                <circle className="node node-1" cx="55" cy="60" r="5" />
                <circle className="node node-2" cx="200" cy="150" r="5" />
                <circle className="node node-3" cx="350" cy="220" r="5" />
                <circle className="node node-4" cx="240" cy="60" r="5" />
                <circle className="node node-5" cx="350" cy="150" r="5" />
                <text x="140" y="35">5 m</text>
                <text x="18" y="105" transform="rotate(-90 18 105)">5 m</text>
                <text x="150" y="175">ROOM · 24.98 m²</text>
                <text x="300" y="245">KITCHEN · 12.40 m²</text>
              </svg>
            </div>
          </div>
        </section>

        <section className="pipeline-section" id="pipeline">
          <div className="wrap">
            <div className="section-head">
              <div className="eyebrow mono eyebrow-accent">HOW VED BUILDS YOUR LAYOUT</div>
              <h2>From photo to wiring plan in six passes</h2>
              <p>Every plan moves through the same pipeline, whether you sketch it by hand or upload a scanned blueprint.</p>
            </div>

            <div className="pipeline-track">
              {pipelineSteps.map((step, index) => (
                <div key={step.title} className="module">
                  <div className={`num mono ${index === 5 ? 'active' : ''}`}>
                    {String(index + 1).padStart(2, '0')}
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.desc}</p>
                  <span className="tag mono">{step.tag}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="features-section" id="features">
          <div className="wrap">
            <div className="section-head section-head-light">
              <div className="eyebrow mono">WHAT YOU GET</div>
              <h2>One plan, viewed the way you need it</h2>
              <p>Switch between an editable 2D drawing, a walk-through 3D render, and a report you can hand to a contractor.</p>
            </div>

            <div className="feat-grid">
              {features.map((feature) => (
                <article key={feature.title} className="feat-card">
                  <div className="feat-icon" dangerouslySetInnerHTML={{ __html: feature.icon }} />
                  <h3>{feature.title}</h3>
                  <p>{feature.desc}</p>
                  <span className="spec mono">{feature.spec}</span>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="cta-section" id="cta">
          <div className="wrap">
            <div className="cta-box">
              <span className="mono">START A NEW PLAN</span>
              <h2>Draw your first layout, free</h2>
              <p>No CAD experience required. Start from a blank canvas or upload the plan you already have.</p>
              <div className="cta-buttons">
                <a href="#" className="btn btn-outline-dark">Create a floor plan</a>
                <a href="#" className="btn btn-dark">Upload a floor plan</a>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="wrap">
          <div className="foot-top">
            <div className="foot-cols">
              {footerColumns.map((column) => (
                <div key={column.title} className="foot-col">
                  <h4>{column.title}</h4>
                  {column.links.map((link) => (
                    <a key={link} href="#">{link}</a>
                  ))}
                </div>
              ))}
            </div>

            <FooterBrand />
          </div>

          <div className="foot-bottom mono">
            <span>© 2026 VED. All rights reserved.</span>
            <span>Sample design — generated from VED wireframe</span>
          </div>
        </div>
      </footer>
    </div>
  )
}

import vedLogo from './assets/ved-logo.png'

function Logo() {
  return (
    <div className="logo" aria-label="VED Electrical Services logo">
      <div className="brand-lockup">
        <img src={vedLogo} alt="VED Electrical Services" className="brand-logo" />
        <span className="brand-divider" aria-hidden="true" />
        <div className="brand-text">
          <span>VED ELECTRICAL</span>
          <span>SERVICES</span>
        </div>
      </div>
    </div>
  )
}

function FooterBrand() {
  return (
    <div className="footer-brand" aria-label="VED Electrical Services logo">
      <img src={vedLogo} alt="VED Electrical Services" />
      <span className="footer-brand-divider" aria-hidden="true" />
      <span className="footer-brand-text">VED ELECTRICAL SERVICES</span>
    </div>
  )
}

export default App
