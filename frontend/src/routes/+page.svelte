<svelte:head>
  <title>Koala : AI Act Governance Assistant</title>
  <meta
    name="description"
    content="Koala is for compliance teams who need fast, citable answers under the EU AI Act. It turns your AI system inventory into obligations you can defend."
  />
</svelte:head>

<script lang="ts">
  const workflowSteps = [
    {
      title: '1. Start with the catalog',
      body: 'Describe the AI system in plain language. If you cannot explain it clearly, you cannot defend it.'
    },
    {
      title: '2. Ask obligation questions',
      body: 'Koala maps that description to the AI Act and returns the specific duties that apply to your role.'
    },
    {
      title: '3. Document and act',
      body: 'Copy the citations into your governance notes and move the system toward compliance with confidence.'
    }
  ];

  const riskLevels = [
    {
      title: 'Prohibited',
      description: 'If it manipulates or exploits people, it is banned under Article 5. Stop here.'
    },
    {
      title: 'High Risk',
      description: 'If it appears in Annex III, you must treat it like a regulated product with full obligations.'
    },
    {
      title: 'Limited Risk',
      description: 'Transparency still applies. Users must know when they are interacting with AI.'
    },
    {
      title: 'Minimal Risk',
      description: 'No extra duties, but you still need to justify why you classify it as minimal.'
    },
    {
      title: 'General Purpose',
      description: 'Model-level duties apply even if you are not the final deployer.'
    }
  ];
</script>

<main class="page">
  <header class="topbar">
    <div class="brand">
      <span class="brand-icon">🐨</span>
      <div>
        <p class="brand-kicker">Koala</p>
        <p class="brand-subtitle">AI Act Governance Assistant</p>
      </div>
    </div>
    <nav class="top-links">
      <a href="#overview">Overview</a>
      <a href="#workflow">Workflow</a>
      <a href="/demo">Demo</a>
      <a href="#risk">Risk levels</a>
      <a href="#get-started">Get started</a>
    </nav>
  </header>

  <section class="hero" id="overview">
    <div class="hero-content">
      <div class="badge-row">
        <span class="badge">EU AI Act · In force</span>
        <span class="badge badge-muted">Indexed: COM(2025) 836 proposal</span>
        <span class="badge badge-outline">Demo is simulated</span>
      </div>
      <h1>Turn your AI system list into obligations you can defend.</h1>
      <p class="lede">
        Koala is built for compliance officers who need real answers under Regulation (EU) 2024/1689. It links your AI
        system catalog to the exact articles that apply, so you can respond to audit and legal requests with citations,
        not guesswork.
      </p>
      <div class="cta-row">
        <a class="button primary" href="https://github.com/monsieurr/koala" target="_blank" rel="noreferrer">
          View on GitHub
        </a>
        <a class="button ghost" href="/demo">Open the demo</a>
      </div>
      <p class="hero-note">
        Scope is EU AI Act only. Omnibus updates are treated as amendments, never as a separate regime.
      </p>
    </div>
    <div class="hero-card">
      <h2>Why Koala exists</h2>
      <p>
        Most AI compliance tools answer in abstractions. Koala starts with a system description and ends with a clear
        list of duties you can actually act on.
      </p>
      <p>
        The public demo is scripted for speed. The full product runs locally with citations, ingestion, and RAG.
      </p>
      <div class="hero-claims">
        <span>Catalog-first workflow</span>
        <span>Citations over summaries</span>
        <span>Built for compliance officers</span>
      </div>
    </div>
  </section>

  <section class="section" id="workflow">
    <div class="section-header">
      <h2>A workflow that matches how compliance teams operate</h2>
      <p>Short, opinionated, and designed to create an audit trail.</p>
    </div>
    <ol class="workflow-list">
      {#each workflowSteps as step}
        <li>
          <h3>{step.title}</h3>
          <p>{step.body}</p>
        </li>
      {/each}
    </ol>
  </section>

  <section class="section" id="demo">
    <div class="section-header">
      <h2>Interactive demo</h2>
      <p>See the full product flow on a dedicated page. No backend required.</p>
    </div>
    <div class="demo-cta">
      <div>
        <h3>Full-page walkthrough</h3>
        <p>
          The demo includes Chat, Catalog, KPIs, AI Setup, and Help. It is a guided simulation that shows the UX without
          any infrastructure setup.
        </p>
      </div>
      <a class="button primary" href="/demo">Launch the demo</a>
    </div>
  </section>

  <section class="section" id="risk">
    <div class="section-header">
      <h2>Risk levels, without the fog</h2>
      <p>Koala forces a decision: is it in Annex III, or not? Everything else follows from that.</p>
    </div>
    <div class="card-grid">
      {#each riskLevels as level}
        <article class="card muted">
          <h3>{level.title}</h3>
          <p>{level.description}</p>
        </article>
      {/each}
    </div>
  </section>

  <section class="section" id="get-started">
    <div class="cta-panel">
      <div>
        <h2>Want the real product experience?</h2>
        <p>
          Run Koala locally for full RAG, PDF ingestion, and AI system analysis. The GitHub README includes setup steps
          and sample data. The full app is served at <code>/app</code> in local mode.
        </p>
      </div>
      <a class="button primary" href="https://github.com/monsieurr/koala" target="_blank" rel="noreferrer">
        Open the repository
      </a>
    </div>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
    background: #f5eee4;
    color: #2f241b;
    font-family: 'Inter', system-ui, sans-serif;
  }

  h1,
  h2,
  h3,
  .brand-kicker {
    font-family: 'Satoshi', 'Inter', sans-serif;
  }

  .page {
    min-height: 100vh;
    padding: 28px 36px 64px;
    background: radial-gradient(circle at top left, #f9f4ec 0%, #f5eee4 40%, #efe3d6 100%);
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 8px 32px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-icon {
    font-size: 32px;
  }

  .brand-kicker {
    margin: 0;
    font-weight: 700;
    font-size: 18px;
  }

  .brand-subtitle {
    margin: 0;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b5b4d;
  }

  .top-links {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
  }

  .top-links a {
    text-decoration: none;
    color: #3d2f25;
    font-weight: 500;
    font-size: 14px;
  }

  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
    gap: 32px;
    align-items: start;
    margin-bottom: 48px;
  }

  .hero-content h1 {
    font-size: clamp(32px, 4vw, 48px);
    margin: 16px 0;
  }

  .lede {
    font-size: 18px;
    line-height: 1.6;
    margin: 0 0 24px;
    color: #44362b;
  }

  .hero-note {
    margin-top: 18px;
    font-size: 14px;
    color: #6b5b4d;
  }

  .badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .badge {
    padding: 6px 12px;
    border-radius: 999px;
    background: #eadccf;
    font-size: 12px;
    font-weight: 600;
    color: #4a392c;
  }

  .badge-muted {
    background: #f0e8df;
  }

  .badge-outline {
    background: transparent;
    border: 1px solid #c8b6a6;
  }

  .cta-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 10px 18px;
    border-radius: 12px;
    text-decoration: none;
    font-weight: 600;
    font-size: 14px;
    border: 1px solid transparent;
  }

  .button.primary {
    background: #6a4a32;
    color: #fffaf5;
    box-shadow: 0 10px 20px rgba(80, 54, 36, 0.25);
  }

  .button.ghost {
    border-color: #c8b6a6;
    color: #4a392c;
    background: #f8f2ea;
  }

  .hero-card {
    background: #fffaf5;
    border-radius: 20px;
    padding: 24px;
    box-shadow: 0 20px 40px rgba(40, 28, 18, 0.08);
    display: grid;
    gap: 16px;
  }

  .hero-card h2 {
    margin: 0;
  }

  .hero-claims {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .hero-claims span {
    padding: 6px 12px;
    border-radius: 999px;
    background: #f1e6da;
    font-size: 12px;
    font-weight: 600;
    color: #5d4c3f;
  }

  .section {
    margin: 48px 0;
  }

  .section-header h2 {
    margin: 0 0 8px;
  }

  .section-header p {
    margin: 0 0 24px;
    color: #5d4c3f;
  }

  .workflow-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 16px;
  }

  .workflow-list li {
    background: #fffaf5;
    border-radius: 16px;
    padding: 18px;
    border: 1px solid #eadccf;
  }

  .workflow-list h3 {
    margin: 0 0 6px;
  }

  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
  }

  .card {
    background: #fff7f0;
    border-radius: 16px;
    padding: 18px;
    border: 1px solid #eadccf;
  }

  .card.muted {
    background: #f7efe7;
  }

  .demo-cta {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    background: #fffaf5;
    border-radius: 20px;
    padding: 24px;
    border: 1px solid #eadccf;
  }

  .demo-cta h3 {
    margin: 0 0 8px;
  }

  .cta-panel {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    background: #fff7f0;
    border: 1px solid #eadccf;
    border-radius: 20px;
    padding: 24px;
  }

  @media (max-width: 900px) {
    .hero {
      grid-template-columns: 1fr;
    }

    .demo-cta,
    .cta-panel {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
