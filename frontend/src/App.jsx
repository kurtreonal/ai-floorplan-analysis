import vedLogo from './assets/ved-logo.png'
import { AUTH_ENABLED } from './api/auth.js'
import { ProtectedAppPage } from './features/auth/ProtectedAppPage.jsx'
import { SignInPage } from './features/auth/SignInPage.jsx'
import { useAuthSession } from './features/auth/useAuthSession.js'
import { useHashRoute } from './routes/useHashRoute.js'


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

function LandingPage({ authEnabled, session }) {
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
            {authEnabled && (
              <a href={session.status === 'authenticated' ? '#/app' : '#/signin'} className="btn btn-ghost">
                {session.status === 'authenticated' ? 'Open app' : 'Sign in'}
              </a>
            )}
            <a href={authEnabled ? '#/app' : '#cta'} className="btn btn-accent">Get started</a>
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
                Upload a floor plan or draw one from scratch. VED detects outlets, switches and lights, routes every wire run, and hands you a 2D/3D layout with a full cost estimate.
              </p>

              <div className="hero-ctas">
                <a href={authEnabled ? '#/app' : '#cta'} className="btn btn-accent btn-large">Create a floor plan</a>
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

              <svg className="draw-svg" viewBox="0 0 520 360" role="img" aria-label="Residential unit blueprint illustration">
                <path className="outline" d="M45,42 H475 V310 H45 Z M210,42 V180 M345,42 V180 M45,180 H164 M198,180 H299 M333,180 H429 M463,180 H475 M175,202 V310 M390,202 V310 M45,202 H132 M166,202 H175 M390,202 H399 M433,202 H475 M45,310 H253 M311,310 H475 M247,310 V348 H317 V310" />
                <path className="outline detail" d="M95,42 H125 M260,42 H290 M390,42 H420 M45,104 H45 M475,104 V140 M45,235 V270 M475,230 V265 M75,310 H115 M205,310 H245 M335,310 H375" />
                <path className="outline door" d="M198,180 V146 A34,34 0 0 0 164,180 M333,180 V146 A34,34 0 0 0 299,180 M463,180 V146 A34,34 0 0 0 429,180 M166,202 V236 A34,34 0 0 1 132,202 M253,310 V281 A29,29 0 0 1 282,310 M311,310 V281 A29,29 0 0 0 282,310 M399,202 V236 A34,34 0 0 0 433,202" />
                <path className="route route-a" d="M128,108 V191 H282" />
                <path className="route route-b" d="M282,108 V255" />
                <path className="route route-c" d="M110,255 H128 V191" />
                <path className="route route-c" d="M410,191 H282" />
                <path className="route route-c" d="M410,108 V191" />
                <path className="route route-c" d="M432,255 H410 V191" />
                <g className="junction-boxes" aria-label="Lighting junction boxes">
                  <rect className="junction-box" x="122" y="185" width="12" height="12" rx="2" />
                  <rect className="junction-box" x="276" y="185" width="12" height="12" rx="2" />
                  <rect className="junction-box" x="404" y="185" width="12" height="12" rx="2" />
                </g>
                <circle className="node node-1" cx="128" cy="108" r="5" />
                <circle className="node node-2" cx="282" cy="108" r="5" />
                <circle className="node node-3" cx="410" cy="108" r="5" />
                <circle className="node node-4" cx="110" cy="255" r="5" />
                <circle className="node node-5" cx="282" cy="255" r="5" />
                <circle className="node node-6" cx="432" cy="255" r="5" />
                <text x="238" y="27">11.50 m</text>
                <text x="17" y="190" transform="rotate(-90 17 190)">9.00 m</text>
                <text x="128" y="82" textAnchor="middle">MASTER BEDROOM</text>
                <text x="128" y="98" textAnchor="middle">4.00 m × 4.00 m</text>
                <text x="277" y="82" textAnchor="middle">BEDROOM 1</text>
                <text x="277" y="98" textAnchor="middle">4.00 m × 3.50 m</text>
                <text x="410" y="82" textAnchor="middle">BEDROOM 2</text>
                <text x="410" y="98" textAnchor="middle">4.00 m × 3.50 m</text>
                <text x="110" y="235" textAnchor="middle">KITCHEN</text>
                <text x="110" y="251" textAnchor="middle">3.00 m × 3.80 m</text>
                <text x="282" y="235" textAnchor="middle">LIVING ROOM</text>
                <text x="282" y="251" textAnchor="middle">5.00 m × 3.80 m</text>
                <text x="432" y="235" textAnchor="middle">CR</text>
                <text x="432" y="251" textAnchor="middle">2.00 m × 2.50 m</text>
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
                <a href={authEnabled ? '#/app' : '#cta'} className="btn btn-outline-dark">Create a floor plan</a>
                <a href={authEnabled ? '#/app' : '#cta'} className="btn btn-dark">Upload a floor plan</a>
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

function Logo() {
  return (
    <div className="logo" aria-label="VED Electrical Services logo">
      <div className="brand-lockup">
        <img src={vedLogo} alt="VED Electrical Services" className="brand-logo" />
      </div>
    </div>
  )
}

function FooterBrand() {
  return (
    <div className="footer-brand" aria-label="VED Electrical Services logo">
      <img src={vedLogo} alt="VED Electrical Services" />
    </div>
  )
}

function App() {
  const route = useHashRoute()
  const session = useAuthSession({ enabled: AUTH_ENABLED })

  if (AUTH_ENABLED && route === '/signin') {
    return <SignInPage session={session} />
  }

  if (AUTH_ENABLED && route === '/app') {
    return <ProtectedAppPage session={session} />
  }

  return <LandingPage authEnabled={AUTH_ENABLED} session={session} />
}

export default App
