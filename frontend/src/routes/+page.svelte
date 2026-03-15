<svelte:head>
  <title>Koala — AI Act Governance Assistant</title>
  <meta
    name="description"
    content="Koala is an AI governance assistant for teams that build AI. Ask grounded questions about the EU AI Act, manage your AI system catalog, and understand obligations with clear, role-aware guidance."
  />
</svelte:head>

<script lang="ts">
  const workflow = [
    {
      title: 'Chat',
      description: 'Ask grounded questions about obligations, prohibitions, and documentation duties under the EU AI Act.'
    },
    {
      title: 'Catalog',
      description: 'Register AI systems with clear descriptions so answers are contextual and defensible.'
    },
    {
      title: 'AI Setup',
      description: 'Configure your assistant and decide how evidence, sources, and roles are applied.'
    },
    {
      title: 'KPIs',
      description: 'Track portfolio coverage, risk distribution, and systems that still need analysis.'
    },
    {
      title: 'Help',
      description: 'Plain-language definitions for context, sources, and snapshots with links to guidance.'
    }
  ];

  const features = [
    'EU AI Act only, with amendments presented as updates to the Act',
    'Risk tier explanations grounded in the regulation and its annexes',
    'Catalog-driven answers that reflect the role you are reviewing as',
    'Copyable answers and citations for internal governance notes',
    'Offline-friendly demo that shows the workflow without technical setup'
  ];

  const riskLevels = [
    {
      title: 'Prohibited',
      description: 'Practices banned under Article 5, such as manipulative or exploitative uses.'
    },
    {
      title: 'High Risk',
      description: 'Systems listed in Annex III or those in regulated domains with strict obligations.'
    },
    {
      title: 'Limited Risk',
      description: 'Transparency obligations apply, including disclosures for certain AI interactions.'
    },
    {
      title: 'Minimal Risk',
      description: 'No specific obligations beyond general principles and good practice.'
    },
    {
      title: 'General Purpose',
      description: 'GPAI obligations and model-level transparency requirements where applicable.'
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
        <span class="badge badge-muted">Amendments indexed · Digital Omnibus proposal</span>
        <span class="badge badge-outline">Demo is simulated</span>
      </div>
      <h1>Grounded AI Act answers for compliance teams who ship real AI.</h1>
      <p class="lede">
        Koala is an open-source governance assistant that helps compliance officers catalog AI systems, understand risk
        tiers, and ask practical questions about obligations under Regulation (EU) 2024/1689. This page introduces the
        product and links to a full-page interactive demo.
      </p>
      <div class="cta-row">
        <a class="button primary" href="https://github.com/monsieurr/koala" target="_blank" rel="noreferrer">
          View on GitHub
        </a>
        <a class="button ghost" href="/demo">Open the demo</a>
      </div>
      <p class="hero-note">
        Scope locked to the EU AI Act. Updates such as the Digital Omnibus proposal are presented as amendments, never
        as a separate regime.
      </p>
    </div>
    <div class="hero-card">
      <h2>What Koala does</h2>
      <ul class="feature-list">
        {#each features as feature}
          <li>{feature}</li>
        {/each}
      </ul>
    </div>
  </section>

  <section class="section" id="workflow">
    <div class="section-header">
      <h2>How it fits a compliance workflow</h2>
      <p>Each area supports a single task: understanding obligations and documenting them clearly.</p>
    </div>
    <div class="card-grid">
      {#each workflow as item}
        <article class="card">
          <h3>{item.title}</h3>
          <p>{item.description}</p>
        </article>
      {/each}
    </div>
  </section>

  <section class="section" id="demo">
    <div class="section-header">
      <h2>Interactive demo</h2>
      <p>Explore the full product flow in a standalone, interactive walkthrough.</p>
    </div>
    <div class="demo-cta">
      <div>
        <h3>Full-page walkthrough</h3>
        <p>
          The demo includes Chat, Catalog, AI Setup, and Help — with interactive controls and a realistic UI. It is
          simulated for the web, and the full RAG experience is available locally.
        </p>
      </div>
      <a class="button primary" href="/demo">Launch the demo</a>
    </div>
  </section>

  <section class="section" id="risk">
    <div class="section-header">
      <h2>AI Act risk levels, explained plainly</h2>
      <p>Koala highlights obligations by risk tier so compliance teams can focus quickly.</p>
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
          Clone Koala and run it locally for full RAG, PDF ingestion, and AI system analysis. The GitHub README includes
          setup steps and sample data.
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
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
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
  }

  .hero-card h2 {
    margin-top: 0;
  }

  .feature-list {
    list-style: disc;
    padding-left: 18px;
    margin: 12px 0 0;
    color: #4a392c;
    line-height: 1.6;
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
