<svelte:head>
  <title>Koala Demo — Full Workflow</title>
  <meta
    name="description"
    content="Full-page Koala demo with Chat, Catalog, KPIs, AI Setup, and Help. Scripted responses show the EU AI Act workflow without a backend."
  />
</svelte:head>

<script lang="ts">
  const demoTabs = [
    { id: 'chat', label: 'Chat' },
    { id: 'catalog', label: 'Catalog' },
    { id: 'kpis', label: 'KPIs' },
    { id: 'setup', label: 'AI Setup' },
    { id: 'help', label: 'Help' }
  ] as const;

  type DemoTab = (typeof demoTabs)[number]['id'];

  const demoCatalogSeed = [
    {
      id: 'face-entry',
      name: 'Office entry face scanner',
      type: 'Biometric identification',
      status: 'High risk',
      catalog: 'Default'
    },
    {
      id: 'candidate-screening',
      name: 'Candidate screening classifier',
      type: 'Employment screening',
      status: 'High risk',
      catalog: 'Default'
    },
    {
      id: 'support-chatbot',
      name: 'Customer support chatbot',
      type: 'Customer assistance',
      status: 'Limited risk',
      catalog: 'Default'
    }
  ];

  const catalogStatuses = ['Unassessed', 'High risk', 'Limited risk', 'Minimal risk'];

  const demoConversations = [
    {
      id: 'facial-entry',
      title: 'Office entry facial recognition',
      subtitle: 'High-risk assessment',
      role: 'Deployer',
      system: 'Office entry facial recognition',
      question: 'Is our office entry face scanner high-risk? What must we do before deployment?',
      answer:
        'Likely high-risk because it is biometric identification in a workplace. Before deployment you must run risk management (Art. 9), document data governance (Art. 10), keep logs (Art. 12), and ensure human oversight (Art. 14). Registration may be required (Art. 60). [1]',
      sources: 'Annex III, Articles 9–14, Article 60.'
    },
    {
      id: 'candidate-screening',
      title: 'Candidate screening AI',
      subtitle: 'Documentation obligations',
      role: 'Provider',
      system: 'Candidate screening classifier',
      question: 'What documentation obligations apply to a hiring system?',
      answer:
        'Employment screening is in Annex III. As the Provider, you must complete conformity assessment, maintain technical documentation, and provide deployer instructions. Post-market monitoring is not optional. [1]',
      sources: 'Annex III, Articles 11, 19, 61.'
    },
    {
      id: 'support-chatbot',
      title: 'Customer support chatbot',
      subtitle: 'Transparency requirements',
      role: 'Deployer',
      system: 'Customer support chatbot',
      question: 'What transparency obligations apply to a customer support chatbot?',
      answer:
        'Tell users they are speaking to AI and how to reach a human. If the bot produces synthetic content, label it. [1]',
      sources: 'Article 50.'
    }
  ];

  const suggestedQuestions = demoConversations.map((item) => item.question);

  const demoSetupSections = ['Provider', 'Model', 'Retrieval', 'Costs', 'Privacy'];

  const demoHelpTopics = ['Context', 'Source filters', 'Index snapshot', 'Catalog', 'AI Setup'];

  const demoProviders = [
    {
      id: 'custom',
      label: 'Custom API (OpenAI-compatible)',
      model: 'gpt-4.1-mini',
      apiBase: 'https://api.your-provider.com/v1'
    },
    {
      id: 'claude',
      label: 'Claude-compatible',
      model: 'claude-sonnet-4-0',
      apiBase: 'https://api.anthropic.com'
    },
    {
      id: 'gemini',
      label: 'Gemini-compatible',
      model: 'gemini-2.5-pro',
      apiBase: 'https://generativelanguage.googleapis.com/v1beta'
    }
  ];

  const helpItems = [
    {
      id: 'context',
      title: 'Context',
      body:
        'If context is blank, answers are generic. Put the system description and your role here first.'
    },
    {
      id: 'sources',
      title: 'Source filters',
      body:
        'Filters decide which AI Act sources are allowed. Use them to stay aligned with the version you are citing.'
    },
    {
      id: 'snapshot',
      title: 'Index snapshot',
      body:
        'The snapshot date is the evidence base for every answer. If it is outdated, your answer is outdated.'
    },
    {
      id: 'catalog',
      title: 'Catalog',
      body:
        'If it is not in the catalog, it is not governable. Start there before asking questions.'
    },
    {
      id: 'setup',
      title: 'AI Setup',
      body:
        'AI Setup chooses model and retrieval depth. In this demo it is simulated; locally it is real.'
    }
  ];

  let demoTab: DemoTab = 'chat';
  let activeDemoId = demoConversations[0].id;
  let demoInput = demoConversations[0].question;
  let demoQuestion = demoConversations[0].question;
  let demoAnswer = demoConversations[0].answer;
  let demoSources = demoConversations[0].sources;
  let demoRole = demoConversations[0].role;
  let demoSystem = demoConversations[0].system;
  let demoCopied = false;
  let demoCatalog = [...demoCatalogSeed];
  let showCatalogForm = false;
  let newSystemName = '';
  let newSystemType = '';
  let newSystemStatus = catalogStatuses[0];
  let selectedProvider = demoProviders[0];
  let setupModel = selectedProvider.model;
  let setupApiBase = selectedProvider.apiBase;
  let setupMaxTokens = 800;
  let setupChunks = 5;
  let setupCostInput = 4;
  let setupCostOutput = 12;
  let openHelpId = helpItems[0].id;
  let demoEstimatedCost = '0.00';

  let copyTimeout: ReturnType<typeof setTimeout> | null = null;

  $: demoEstimatedCost = ((setupCostInput + setupCostOutput) * (setupMaxTokens / 1_000_000)).toFixed(4);
  $: totalSystems = demoCatalog.length;
  $: highRiskCount = demoCatalog.filter((item) => item.status === 'High risk').length;
  $: limitedRiskCount = demoCatalog.filter((item) => item.status === 'Limited risk').length;
  $: minimalRiskCount = demoCatalog.filter((item) => item.status === 'Minimal risk').length;
  $: unassessedCount = demoCatalog.filter((item) => item.status === 'Unassessed').length;
  $: coverageScore = Math.round(((totalSystems - unassessedCount) / Math.max(totalSystems, 1)) * 100);

  const fallbackAnswer =
    'This demo only answers the suggested questions. Run Koala locally for real queries, citations, and analysis.';

  const fallbackSources = 'Demo response only.';

  function applyDemo(item: (typeof demoConversations)[number]) {
    demoQuestion = item.question;
    demoAnswer = item.answer;
    demoSources = item.sources;
    demoRole = item.role;
    demoSystem = item.system;
  }

  function selectDemo(item: (typeof demoConversations)[number]) {
    activeDemoId = item.id;
    demoInput = item.question;
    applyDemo(item);
  }

  function handleAsk() {
    const trimmed = demoInput.trim();
    if (!trimmed) {
      return;
    }
    const match = demoConversations.find(
      (item) => item.question.toLowerCase() === trimmed.toLowerCase()
    );
    if (match) {
      selectDemo(match);
      return;
    }
    demoQuestion = trimmed;
    demoAnswer = fallbackAnswer;
    demoSources = fallbackSources;
  }

  async function handleCopy() {
    const text = demoAnswer;
    if (!text) {
      return;
    }
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // ignore copy errors for demo
      }
    }
    demoCopied = true;
    if (copyTimeout) {
      clearTimeout(copyTimeout);
    }
    copyTimeout = setTimeout(() => {
      demoCopied = false;
    }, 1400);
  }

  function pickSuggestion(question: string) {
    demoInput = question;
    handleAsk();
  }

  function openCatalogForm() {
    showCatalogForm = true;
    newSystemName = '';
    newSystemType = '';
    newSystemStatus = catalogStatuses[0];
  }

  function addCatalogSystem() {
    if (!newSystemName.trim()) {
      return;
    }
    demoCatalog = [
      {
        id: `${Date.now()}`,
        name: newSystemName.trim(),
        type: newSystemType.trim() || 'AI system',
        status: newSystemStatus,
        catalog: 'Default'
      },
      ...demoCatalog
    ];
    showCatalogForm = false;
  }

  function selectProvider(providerId: string) {
    const provider = demoProviders.find((item) => item.id === providerId);
    if (!provider) {
      return;
    }
    selectedProvider = provider;
    setupModel = provider.model;
    setupApiBase = provider.apiBase;
  }

  function toggleHelp(id: string) {
    openHelpId = openHelpId === id ? '' : id;
  }
</script>

<main class="page demo-page">
  <header class="topbar">
    <div class="brand">
      <span class="brand-icon">🐨</span>
      <div>
        <p class="brand-kicker">Koala</p>
        <p class="brand-subtitle">AI Act Governance Assistant</p>
      </div>
    </div>
    <nav class="top-links">
      <a href="/">Overview</a>
      <a href="https://github.com/monsieurr/koala" target="_blank" rel="noreferrer">GitHub</a>
    </nav>
  </header>

  <section class="hero demo-hero">
    <div class="hero-content">
      <div class="badge-row">
        <span class="badge">EU AI Act · In force</span>
        <span class="badge badge-muted">Indexed: COM(2025) 836 proposal</span>
        <span class="badge badge-outline">Scripted demo</span>
      </div>
      <h1>Interactive Koala demo</h1>
      <p class="lede">
        This full-page walkthrough shows how Koala handles Chat, Catalog, KPIs, AI Setup, and Help. Responses are
        scripted to keep the demo fast and reliable. The real engine runs locally.
      </p>
      <div class="cta-row">
        <a class="button ghost" href="/">Back to overview</a>
        <a class="button primary" href="https://github.com/monsieurr/koala" target="_blank" rel="noreferrer">
          Run locally
        </a>
      </div>
    </div>
    <div class="hero-card">
      <h2>What you can test here</h2>
      <ul class="feature-list">
        <li>Switch between Chat, Catalog, KPIs, AI Setup, and Help</li>
        <li>Add a catalog entry and watch the KPIs update</li>
        <li>Adjust retrieval depth and cost assumptions</li>
        <li>Copy an answer as a governance note</li>
      </ul>
    </div>
  </section>

  <section class="section demo" id="demo">
    <div class="demo-tabs" role="tablist" aria-label="Demo views">
      {#each demoTabs as tab}
        <button
          type="button"
          class:active={demoTab === tab.id}
          on:click={() => (demoTab = tab.id)}
          aria-pressed={demoTab === tab.id}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    <div class="demo-shell">
      <aside class="demo-panel demo-history">
        <div class="panel-header">
          <span>
            {#if demoTab === 'chat'}
              History
            {:else if demoTab === 'catalog'}
              Catalog list
            {:else if demoTab === 'kpis'}
              KPI snapshot
            {:else if demoTab === 'setup'}
              Setup sections
            {:else}
              Help topics
            {/if}
          </span>
          <span class="pill">
            {#if demoTab === 'chat'}
              {demoConversations.length}
            {:else if demoTab === 'catalog'}
              {demoCatalog.length}
            {:else if demoTab === 'kpis'}
              4
            {:else if demoTab === 'setup'}
              {demoSetupSections.length}
            {:else}
              {demoHelpTopics.length}
            {/if}
          </span>
        </div>
        <div class="demo-list">
          {#if demoTab === 'chat'}
            {#each demoConversations as item}
              <button
                class={`demo-item ${item.id === activeDemoId ? 'active' : ''}`}
                type="button"
                on:click={() => selectDemo(item)}
                aria-pressed={item.id === activeDemoId}
              >
                <p>{item.title}</p>
                <span>{item.subtitle}</span>
              </button>
            {/each}
          {:else if demoTab === 'catalog'}
            {#each demoCatalog as item}
              <div class="demo-item catalog-item">
                <p>{item.name}</p>
                <span>{item.type}</span>
                <span class={`status-pill ${item.status.toLowerCase().replace(' ', '-')}`}>{item.status}</span>
              </div>
            {/each}
          {:else if demoTab === 'kpis'}
            <div class="demo-item catalog-item">
              <p>Coverage score</p>
              <span>{coverageScore}%</span>
            </div>
            <div class="demo-item catalog-item">
              <p>High-risk systems</p>
              <span>{highRiskCount}</span>
            </div>
            <div class="demo-item catalog-item">
              <p>Unassessed</p>
              <span>{unassessedCount}</span>
            </div>
            <div class="demo-item catalog-item">
              <p>Ready for audit</p>
              <span>{Math.max(totalSystems - unassessedCount, 0)}</span>
            </div>
          {:else if demoTab === 'setup'}
            {#each demoSetupSections as section}
              <div class="demo-item catalog-item">
                <p>{section}</p>
                <span>Adjust settings and model selection</span>
              </div>
            {/each}
          {:else}
            {#each demoHelpTopics as topic}
              <div class="demo-item catalog-item">
                <p>{topic}</p>
                <span>Guidance and definitions</span>
              </div>
            {/each}
          {/if}
        </div>
      </aside>

      {#if demoTab === 'chat'}
        <section class="demo-panel demo-chat">
          <div class="panel-header">
            <span>Chat</span>
            <span class="badge badge-outline">Scripted</span>
          </div>
          <div class="chat-bubble user">{demoQuestion}</div>
          <div class="chat-bubble assistant">
            {demoAnswer}
            <button class="copy" type="button" on:click={handleCopy}>
              {demoCopied ? 'Copied' : 'Copy answer'}
            </button>
          </div>
          <div class="chat-bubble assistant note">Sources cited: {demoSources}</div>
          <div class="suggested">
            {#each suggestedQuestions as question}
              <button type="button" on:click={() => pickSuggestion(question)}>{question}</button>
            {/each}
          </div>
          <p class="demo-note">This demo answers the suggested questions only.</p>
          <div class="chat-input">
            <input
              type="text"
              bind:value={demoInput}
              placeholder="Ask a compliance question…"
              aria-label="Ask a compliance question"
            />
            <button type="button" on:click={handleAsk}>Ask</button>
          </div>
        </section>
      {:else if demoTab === 'catalog'}
        <section class="demo-panel demo-catalog">
          <div class="panel-header">
            <span>Catalog</span>
            <span class="badge badge-outline">Simulated</span>
          </div>
          <div class="catalog-toolbar">
            <button class="button tiny" type="button" on:click={openCatalogForm}>New system</button>
            <span class="catalog-count">{demoCatalog.length} systems</span>
          </div>
          {#if showCatalogForm}
            <div class="catalog-form">
              <label>
                System name
                <input type="text" bind:value={newSystemName} placeholder="e.g. Branch access face scanner" />
              </label>
              <label>
                Type
                <input type="text" bind:value={newSystemType} placeholder="e.g. biometric identification" />
              </label>
              <label>
                Status
                <select bind:value={newSystemStatus}>
                  {#each catalogStatuses as status}
                    <option value={status}>{status}</option>
                  {/each}
                </select>
              </label>
              <div class="catalog-actions">
                <button class="button ghost tiny" type="button" on:click={() => (showCatalogForm = false)}>
                  Cancel
                </button>
                <button class="button tiny" type="button" on:click={addCatalogSystem}>Add system</button>
              </div>
            </div>
          {/if}
          <div class="catalog-list">
            {#each demoCatalog as item}
              <div class="catalog-row">
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.type}</span>
                </div>
                <span class={`status-pill ${item.status.toLowerCase().replace(' ', '-')}`}>{item.status}</span>
              </div>
            {/each}
          </div>
        </section>
      {:else if demoTab === 'kpis'}
        <section class="demo-panel demo-kpis">
          <div class="panel-header">
            <span>KPIs</span>
            <span class="badge badge-outline">Simulated</span>
          </div>
          <div class="kpi-grid">
            <div class="kpi-card">
              <span>Systems registered</span>
              <strong>{totalSystems}</strong>
            </div>
            <div class="kpi-card">
              <span>Coverage score</span>
              <strong>{coverageScore}%</strong>
            </div>
            <div class="kpi-card">
              <span>High-risk systems</span>
              <strong>{highRiskCount}</strong>
            </div>
            <div class="kpi-card">
              <span>Unassessed</span>
              <strong>{unassessedCount}</strong>
            </div>
          </div>
          <div class="kpi-breakdown">
            <h3>Risk distribution</h3>
            <div class="kpi-row">
              <span>High risk</span>
              <div class="kpi-bar"><span style={`width: ${(highRiskCount / Math.max(totalSystems, 1)) * 100}%`}></span></div>
              <strong>{highRiskCount}</strong>
            </div>
            <div class="kpi-row">
              <span>Limited risk</span>
              <div class="kpi-bar"><span style={`width: ${(limitedRiskCount / Math.max(totalSystems, 1)) * 100}%`}></span></div>
              <strong>{limitedRiskCount}</strong>
            </div>
            <div class="kpi-row">
              <span>Minimal risk</span>
              <div class="kpi-bar"><span style={`width: ${(minimalRiskCount / Math.max(totalSystems, 1)) * 100}%`}></span></div>
              <strong>{minimalRiskCount}</strong>
            </div>
            <div class="kpi-row">
              <span>Unassessed</span>
              <div class="kpi-bar"><span style={`width: ${(unassessedCount / Math.max(totalSystems, 1)) * 100}%`}></span></div>
              <strong>{unassessedCount}</strong>
            </div>
          </div>
        </section>
      {:else if demoTab === 'setup'}
        <section class="demo-panel demo-setup">
          <div class="panel-header">
            <span>AI Setup</span>
            <span class="badge badge-outline">Simulated</span>
          </div>
          <div class="setup-group">
            <label>Provider</label>
            <div class="provider-chips">
              {#each demoProviders as providerOption}
                <button
                  type="button"
                  class:active={providerOption.id === selectedProvider.id}
                  on:click={() => selectProvider(providerOption.id)}
                >
                  {providerOption.label}
                </button>
              {/each}
            </div>
          </div>
          <div class="setup-group">
            <label>Model ID</label>
            <input type="text" bind:value={setupModel} />
          </div>
          <div class="setup-group">
            <label>API base URL</label>
            <input type="text" bind:value={setupApiBase} />
          </div>
          <div class="setup-group">
            <label>API key</label>
            <input type="password" value="••••••••••••••••" readonly />
          </div>
          <div class="setup-group slider-group">
            <label>Retrieved chunks</label>
            <div class="slider-row">
              <input type="range" min="3" max="7" bind:value={setupChunks} />
              <span>{setupChunks}</span>
            </div>
          </div>
          <div class="setup-group slider-group">
            <label>Max output tokens</label>
            <div class="slider-row">
              <input type="range" min="400" max="1200" step="50" bind:value={setupMaxTokens} />
              <span>{setupMaxTokens}</span>
            </div>
          </div>
          <div class="setup-group cost-group">
            <label>Estimated cost per 1M tokens</label>
            <div class="cost-row">
              <div>
                <span>Input</span>
                <input type="number" min="0" step="0.5" bind:value={setupCostInput} />
              </div>
              <div>
                <span>Output</span>
                <input type="number" min="0" step="0.5" bind:value={setupCostOutput} />
              </div>
            </div>
            <p class="cost-note">Estimated per-response cost: ${demoEstimatedCost}</p>
          </div>
        </section>
      {:else}
        <section class="demo-panel demo-help">
          <div class="panel-header">
            <span>Help</span>
            <span class="badge badge-outline">Simulated</span>
          </div>
          <div class="help-list">
            {#each helpItems as item}
              <button
                class="help-item"
                type="button"
                on:click={() => toggleHelp(item.id)}
                aria-expanded={openHelpId === item.id}
              >
                <span>{item.title}</span>
                <span>{openHelpId === item.id ? '−' : '+'}</span>
              </button>
              {#if openHelpId === item.id}
                <div class="help-body">{item.body}</div>
              {/if}
            {/each}
          </div>
        </section>
      {/if}

      <aside class="demo-panel demo-context">
        <div class="panel-header">
          <span>
            {#if demoTab === 'chat'}
              Context
            {:else if demoTab === 'catalog'}
              Catalog summary
            {:else if demoTab === 'kpis'}
              KPI summary
            {:else if demoTab === 'setup'}
              Setup summary
            {:else}
              Help summary
            {/if}
          </span>
          <span class="badge">EU AI Act · In force</span>
        </div>
        {#if demoTab === 'chat'}
          <div class="context-row">
            <span>You are reviewing as</span>
            <strong>{demoRole}</strong>
          </div>
          <div class="context-row">
            <span>System focus</span>
            <strong>{demoSystem}</strong>
          </div>
          <div class="context-row">
            <span>Sources</span>
            <strong>AI Act + Omnibus amendment notes</strong>
          </div>
        {:else if demoTab === 'catalog'}
          <div class="context-row">
            <span>Total systems</span>
            <strong>{totalSystems}</strong>
          </div>
          <div class="context-row">
            <span>High risk</span>
            <strong>{highRiskCount}</strong>
          </div>
          <div class="context-row">
            <span>Unassessed</span>
            <strong>{unassessedCount}</strong>
          </div>
        {:else if demoTab === 'kpis'}
          <div class="context-row">
            <span>Coverage score</span>
            <strong>{coverageScore}%</strong>
          </div>
          <div class="context-row">
            <span>Ready for audit</span>
            <strong>{Math.max(totalSystems - unassessedCount, 0)}</strong>
          </div>
          <div class="context-row">
            <span>Next action</span>
            <strong>Assess remaining systems</strong>
          </div>
        {:else if demoTab === 'setup'}
          <div class="context-row">
            <span>Provider</span>
            <strong>{selectedProvider.label}</strong>
          </div>
          <div class="context-row">
            <span>Retrieved chunks</span>
            <strong>{setupChunks}</strong>
          </div>
          <div class="context-row">
            <span>Max output tokens</span>
            <strong>{setupMaxTokens}</strong>
          </div>
          <div class="context-row">
            <span>Privacy note</span>
            <strong>Keys stay on your device in the demo</strong>
          </div>
        {:else}
          <div class="context-row">
            <span>Need more help?</span>
            <strong>See the GitHub README for full guidance.</strong>
          </div>
          <div class="context-row">
            <span>Scope</span>
            <strong>EU AI Act only</strong>
          </div>
          <div class="context-row">
            <span>Last indexed</span>
            <strong>Digital Omnibus proposal (COM(2025) 836)</strong>
          </div>
        {/if}
      </aside>
    </div>
    <p class="demo-disclaimer">
      This demo is a scripted mock. No data leaves your browser, and no backend is called.
    </p>
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

  .demo-page {
    padding-bottom: 80px;
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
    margin-bottom: 36px;
  }

  .hero-content h1 {
    font-size: clamp(32px, 4vw, 46px);
    margin: 16px 0;
  }

  .lede {
    font-size: 18px;
    line-height: 1.6;
    margin: 0 0 24px;
    color: #44362b;
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

  .button.tiny {
    padding: 6px 12px;
    font-size: 12px;
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
    margin: 36px 0;
  }

  .demo-tabs {
    display: inline-flex;
    gap: 8px;
    background: #f7efe7;
    padding: 6px;
    border-radius: 999px;
    border: 1px solid #e0d0c1;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }

  .demo-tabs button {
    border: none;
    background: transparent;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 12px;
    cursor: pointer;
    color: #5d4c3f;
    font-weight: 600;
  }

  .demo-tabs button.active {
    background: #6a4a32;
    color: #fffaf5;
  }

  .demo-tabs button:focus-visible {
    outline: 2px solid #6a4a32;
    outline-offset: 2px;
  }

  .demo-shell {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr) 260px;
    gap: 16px;
    background: #f1e6da;
    border-radius: 24px;
    padding: 18px;
    border: 1px solid #d8c8b8;
    min-height: 560px;
  }

  .demo-panel {
    background: #fffaf5;
    border-radius: 16px;
    padding: 14px;
    border: 1px solid #e6d6c7;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 13px;
    color: #6b5b4d;
  }

  .pill {
    background: #eadccf;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
  }

  .demo-list {
    display: grid;
    gap: 10px;
  }

  .demo-item {
    padding: 10px 12px;
    border-radius: 12px;
    background: #f7efe7;
    border: 1px solid transparent;
    text-align: left;
    width: 100%;
    cursor: pointer;
    font: inherit;
  }

  .demo-item.catalog-item {
    display: grid;
    gap: 4px;
    cursor: default;
  }

  .demo-item.active {
    border-color: #c8b6a6;
    background: #fff;
  }

  .demo-item:focus-visible {
    outline: 2px solid #6a4a32;
    outline-offset: 2px;
  }

  .demo-chat,
  .demo-catalog,
  .demo-setup,
  .demo-help,
  .demo-kpis {
    gap: 16px;
  }

  .chat-bubble {
    padding: 12px 14px;
    border-radius: 14px;
    background: #f7efe7;
    font-size: 14px;
    line-height: 1.5;
  }

  .chat-bubble.user {
    background: #e9d6c3;
    align-self: flex-end;
  }

  .chat-bubble.assistant {
    background: #fff;
    border: 1px solid #eadccf;
  }

  .chat-bubble.note {
    background: transparent;
    border: none;
    color: #6b5b4d;
    font-size: 12px;
    padding: 0;
  }

  .copy {
    margin-top: 10px;
    border: none;
    background: #6a4a32;
    color: #fffaf5;
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .suggested {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .suggested button {
    background: #f7efe7;
    border: 1px solid #e0d0c1;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .suggested button:focus-visible {
    outline: 2px solid #6a4a32;
    outline-offset: 2px;
  }

  .demo-note {
    margin: 0;
    font-size: 12px;
    color: #6b5b4d;
  }

  .chat-input {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #eadccf;
    border-radius: 12px;
    padding: 10px 12px;
    color: #8b7a6b;
    background: #fffaf5;
    gap: 12px;
  }

  .chat-input input {
    border: none;
    background: transparent;
    font: inherit;
    flex: 1;
    color: #2f241b;
  }

  .chat-input input:focus {
    outline: none;
  }

  .chat-input button {
    background: #6a4a32;
    color: #fffaf5;
    border: none;
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .catalog-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .catalog-count {
    font-size: 12px;
    color: #6b5b4d;
  }

  .catalog-form {
    display: grid;
    gap: 10px;
    background: #f7efe7;
    border-radius: 14px;
    padding: 12px;
    border: 1px solid #eadccf;
  }

  .catalog-form label {
    display: grid;
    gap: 6px;
    font-size: 12px;
    color: #5d4c3f;
  }

  .catalog-form input,
  .catalog-form select {
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid #d8c8b8;
    font: inherit;
    background: #fffaf5;
  }

  .catalog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }

  .catalog-list {
    display: grid;
    gap: 10px;
  }

  .catalog-row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    background: #fffaf5;
    border: 1px solid #eadccf;
    border-radius: 12px;
    padding: 10px 12px;
  }

  .catalog-row strong {
    display: block;
  }

  .catalog-row span {
    font-size: 12px;
    color: #6b5b4d;
  }

  .status-pill {
    align-self: center;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    background: #efe3d6;
    color: #6b5b4d;
  }

  .status-pill.high-risk {
    background: #e8cbb1;
    color: #6a4a32;
  }

  .status-pill.limited-risk {
    background: #f0d9c7;
    color: #6a4a32;
  }

  .status-pill.minimal-risk {
    background: #f4e9df;
    color: #6b5b4d;
  }

  .status-pill.unassessed {
    background: #f1ede6;
    color: #6b5b4d;
  }

  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }

  .kpi-card {
    background: #f7efe7;
    border-radius: 14px;
    padding: 12px;
    border: 1px solid #eadccf;
    display: grid;
    gap: 8px;
    font-size: 12px;
    color: #5d4c3f;
  }

  .kpi-card strong {
    font-size: 20px;
    color: #2f241b;
  }

  .kpi-breakdown {
    background: #fffaf5;
    border: 1px solid #eadccf;
    border-radius: 14px;
    padding: 12px;
    display: grid;
    gap: 10px;
  }

  .kpi-breakdown h3 {
    margin: 0;
  }

  .kpi-row {
    display: grid;
    grid-template-columns: 90px 1fr 40px;
    gap: 10px;
    align-items: center;
    font-size: 12px;
    color: #6b5b4d;
  }

  .kpi-bar {
    background: #f1e6da;
    border-radius: 999px;
    height: 8px;
    overflow: hidden;
  }

  .kpi-bar span {
    display: block;
    height: 100%;
    background: #6a4a32;
  }

  .setup-group {
    display: grid;
    gap: 8px;
    font-size: 12px;
    color: #5d4c3f;
  }

  .setup-group input {
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid #d8c8b8;
    font: inherit;
    background: #fffaf5;
    color: #2f241b;
  }

  .provider-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .provider-chips button {
    border: 1px solid #e0d0c1;
    background: #f7efe7;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    cursor: pointer;
  }

  .provider-chips button.active {
    background: #6a4a32;
    color: #fffaf5;
    border-color: #6a4a32;
  }

  .slider-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .slider-row input[type='range'] {
    flex: 1;
    accent-color: #6a4a32;
  }

  .cost-group {
    background: #f7efe7;
    border-radius: 12px;
    padding: 12px;
    border: 1px solid #eadccf;
  }

  .cost-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
  }

  .cost-row span {
    display: block;
    margin-bottom: 6px;
    color: #6b5b4d;
  }

  .cost-note {
    margin: 10px 0 0;
    font-size: 12px;
    color: #6b5b4d;
  }

  .help-list {
    display: grid;
    gap: 10px;
  }

  .help-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border: 1px solid #e0d0c1;
    background: #f7efe7;
    border-radius: 12px;
    padding: 10px 12px;
    font-size: 13px;
    cursor: pointer;
  }

  .help-item:focus-visible {
    outline: 2px solid #6a4a32;
    outline-offset: 2px;
  }

  .help-body {
    margin-top: -4px;
    padding: 10px 12px;
    border-radius: 12px;
    background: #fffaf5;
    border: 1px solid #eadccf;
    font-size: 12px;
    color: #5d4c3f;
  }

  .context-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
    color: #5d4c3f;
  }

  .context-row strong {
    color: #2f241b;
  }

  .demo-disclaimer {
    margin-top: 16px;
    font-size: 13px;
    color: #6b5b4d;
  }

  @media (max-width: 980px) {
    .hero {
      grid-template-columns: 1fr;
    }

    .demo-shell {
      grid-template-columns: 1fr;
      min-height: auto;
    }
  }

  @media (max-width: 720px) {
    .page {
      padding: 20px 18px 56px;
    }

    .topbar {
      flex-direction: column;
      align-items: flex-start;
    }

    .demo-shell {
      padding: 14px;
      border-radius: 18px;
    }

    .demo-tabs {
      width: 100%;
      justify-content: space-between;
    }

    .hero-content h1 {
      font-size: 32px;
    }

    .chat-input {
      flex-direction: column;
      align-items: stretch;
    }

    .chat-input button {
      width: 100%;
    }

    .catalog-row {
      flex-direction: column;
      align-items: flex-start;
    }
  }
</style>
