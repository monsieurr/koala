<script lang="ts">
  import { fly } from 'svelte/transition';
  import { onMount, tick } from 'svelte';
  import { browser } from '$app/environment';

  import {
    analyzeSystems as postAnalyzeSystems,
    deleteSystem as removeSystem,
    exportSystems as fetchSystemsExport,
    importSystems as postSystemsImport,
    fetchConfig,
    fetchHealth,
    fetchOllamaModels,
    fetchSources,
    fetchSystems,
    postQuery,
    pullOllamaModel,
    updateSystem,
    upsertSystem
  } from '$lib/api';
  import {
    buildConversationTitle,
    createConversation,
    loadActiveConversationId,
    loadConversations,
    saveActiveConversationId,
    saveConversations
  } from '$lib/conversations';
  import {
    buildDemoSystem,
    isDemoMode,
    loadDemoSystems,
    saveDemoSystems,
    updateDemoSystem
  } from '$lib/demo';
  import { renderMarkdown } from '$lib/markdown';
  import { detectSuggestedSystem, type SuggestedSystemDraft } from '$lib/system-suggestion';
  import type {
    AISystem,
    AppConfig,
    ChatMessage,
    Conversation,
    HealthResponse,
    OllamaModel,
    ProviderOption,
    QueryResponse,
    SourceSummary,
    UserRole
  } from '$lib/types';

  const DEFAULT_PROVIDER_OPTIONS: ProviderOption[] = [
    {
      id: 'ollama',
      label: 'Local (Ollama)',
      requires_api_key: false,
      default_model: 'llama3.1:8b',
      default_base_url: 'http://localhost:11434'
    },
    {
      id: 'openai',
      label: 'OpenAI (GPT)',
      requires_api_key: true,
      default_model: 'gpt-4.1-mini',
      default_base_url: null
    },
    {
      id: 'anthropic',
      label: 'Anthropic (Claude)',
      requires_api_key: true,
      default_model: 'claude-sonnet-4-0',
      default_base_url: null
    },
    {
      id: 'gemini',
      label: 'Google (Gemini)',
      requires_api_key: true,
      default_model: 'gemini-2.5-pro',
      default_base_url: null
    },
    {
      id: 'mistral',
      label: 'Mistral API',
      requires_api_key: true,
      default_model: 'mistral-small-latest',
      default_base_url: null
    },
    {
      id: 'openai_compatible',
      label: 'Custom API (OpenAI-compatible)',
      requires_api_key: true,
      default_model: 'custom-model',
      default_base_url: ''
    }
  ];


  const MODEL_PRESETS: Record<string, string[]> = {
    ollama: ['llama3.1:8b', 'mistral:7b-instruct', 'gemma2:9b', 'qwen2.5:14b'],
    openai: ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o', 'gpt-4o-mini'],
    anthropic: ['claude-sonnet-4-0', 'claude-opus-4-0', 'claude-3-5-sonnet-latest'],
    gemini: ['gemini-2.5-pro', 'gemini-2.5-flash'],
    mistral: ['mistral-small-latest', 'mistral-large-latest'],
    openai_compatible: ['custom-model']
  };
  const PROVIDER_HINTS: Array<{ name: string; models: string; note?: string }> = [
    { name: 'OpenAI (GPT)', models: 'gpt-4.1, gpt-4.1-mini' },
    { name: 'Anthropic (Claude)', models: 'claude-sonnet-4-0, claude-opus-4-0' },
    { name: 'Google (Gemini)', models: 'gemini-2.5-pro, gemini-2.5-flash' },
    { name: 'Mistral', models: 'mistral-small-latest' },
    { name: 'Cohere', models: 'command-a-03-2025', note: 'Select Custom API if using an OpenAI-compatible proxy.' },
    { name: 'DeepSeek', models: 'deepseek-chat, deepseek-reasoner', note: 'Custom API base URL: https://api.deepseek.com' },
    { name: 'xAI (Grok)', models: 'grok-3, grok-3-fast', note: 'Custom API base URL: https://api.x.ai/v1' },
    { name: 'Kimi (Moonshot)', models: 'kimi-k2-thinking', note: 'Use the model ID shown in your Moonshot console.' },
    {
      name: 'Meta Llama (hosted)',
      models: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
      note: 'Use a hosted provider that exposes OpenAI-compatible endpoints.'
    }
  ];

  const PROJECT_GITHUB_URL = 'https://github.com/monsieurr/koala';
  const DEMO_MODE = isDemoMode();
  const EXAMPLE_QUESTIONS = [
    'Can we scan employees’ faces for office entry, and what AI Act obligations apply to the deployer?',
    'Is our résumé screening tool considered high risk under the AI Act?',
    'What transparency duties apply to a customer support chatbot?',
    'Do we need a conformity assessment for a credit scoring model?',
    'Are emotion recognition tools in the workplace prohibited?',
    'What documentation must we keep for a high-risk AI system?',
    'How should we handle human oversight requirements for automated decisions?',
    'What obligations apply to importers versus deployers?',
    'Does a general-purpose AI model trigger additional obligations?',
    'Which AI Act articles cover biometric identification in public spaces?'
  ];
  const DEFAULT_CATALOG = 'Default';
  const ALL_CATALOG = '__all__';
  const ALL_CATALOG_LABEL = 'All catalogs';
  const SUGGESTED_QUESTIONS = [
    'What are my documentation obligations as a Deployer?',
    'Which practices are prohibited under Article 5?',
    'What does high-risk classification mean for my system?',
    'What transparency obligations apply to me?'
  ];
  const ACT_BADGE = 'EU AI Act · In force';
  const AMENDMENT_LABEL = 'Digital Omnibus on AI proposal';
  const AMENDMENT_PUBLISHED = '19 Nov 2025';
  const AMENDMENT_UPDATED = '19 Jan 2026';
  const ACT_SOURCE_MATCHERS = [/ai act/i, /2024\/?1689/i];
  const AMENDMENT_MATCHERS = [/omnibus/i, /COM\(2025\)\s*836/i, /2025\s*\/\s*0359/i];
  const ANSWER_MODE_LABELS: Record<string, string> = {
    generated: 'AI answer',
    sources_only: 'Sources-only',
    not_found: 'No sources found',
    error: 'Unavailable'
  };

  const ROLE_OPTIONS: Array<{ value: UserRole; label: string }> = [
    { value: 'provider', label: 'Provider' },
    { value: 'deployer', label: 'Deployer' },
    { value: 'distributor', label: 'Distributor' },
    { value: 'importer', label: 'Importer' },
    { value: 'authorized_representative', label: 'Authorized representative' },
    { value: 'affected_person', label: 'Affected person' },
    { value: 'user', label: 'End user' },
    { value: 'other', label: 'Other' }
  ];

  let config: AppConfig | null = null;
  let health: HealthResponse | null = null;
  let sources: SourceSummary[] = [];
  let actSources: SourceSummary[] = [];
  let amendmentSources: SourceSummary[] = [];
  let hasAmendmentSources = false;
  let systems: AISystem[] = [];
  let conversations: Conversation[] = [];
  let activeConversationId = '';
  let centerView: 'chat' | 'catalog' | 'kpis' | 'setup' | 'help' = 'chat';

  let showHistoryPanel = true;
  let showControlsPanel = true;

  let ollamaModels: OllamaModel[] = [];

  let loading = true;
  let refreshing = false;
  let submitting = false;
  let savingSystem = false;
  let importingSystems = false;
  let systemAnalyzing = false;
  let analyzingSystemIds: string[] = [];
  let statusMessage = '';
  let statusKind: 'connection' | 'action' | '' = '';
  let preparingAssistant = false;
  let notice = '';
  let openConversationMenuId = '';
  let conversationMenuStyle = '';
  let conversationMenuAnchor: HTMLElement | null = null;
  let conversationMenuEl: HTMLElement | null = null;
  let systemFormEl: HTMLDivElement | null = null;
  let renameInput: HTMLInputElement | null = null;
  let lastFocusedElement: HTMLElement | null = null;
  let renameDialogOpen = false;
  let renameConversationId = '';
  let renameDraft = '';

  let question = '';
  let questionInput: HTMLTextAreaElement | null = null;
  let provider = 'ollama';
  let model = 'llama3.1:8b';
  let customModel = '';
  let apiBase = 'http://localhost:11434';
  let apiKey = '';
  let useCustomKey = false;
  let maxOutputTokens = 900;
  let outputTokenLimit = 0;
  let estimatedInputTokens = 0;
  let estimatedTotalTokens = 0;
  let inputCostPerMillion = '';
  let outputCostPerMillion = '';
  let inputCostRate = 0;
  let outputCostRate = 0;
  let estimatedInputCost = 0;
  let estimatedOutputCost = 0;
  let estimatedTotalCost = 0;
  let sessionInputTokens = 0;
  let sessionOutputTokens = 0;
  let sessionInputCost = 0;
  let sessionOutputCost = 0;
  let sessionTotalCost = 0;
  let copiedMessageId = '';
  let topK = 5;
  let userRole: UserRole = 'deployer';

  let selectedSources: string[] = [];
  let selectedLanguages: string[] = [];
  let selectedSystemIds: string[] = [];
  let activeSystemId = '';
  let activeCatalog = ALL_CATALOG;
  let resolvedCatalog = ALL_CATALOG;
  let visibleSystems: AISystem[] = [];
  let hasAppliedSourceDefaults = false;

  let systemName = '';
  let systemDescription = '';
  let systemType = '';
  let systemCatalog = DEFAULT_CATALOG;
  let editingSystemId = '';
  let showSystemForm = false;

  let workspaceTitle = '';
  let hasMultipleCatalogs = false;

  let suggestedSystem: SuggestedSystemDraft | null = null;
  let analysisConfirmation:
    | {
        ids: string[];
        duplicates: AISystem[];
      }
    | null = null;

  let hasAppliedConfigDefaults = false;
  let lastOllamaLookupKey = '';

  $: providerOptions = config?.provider_options ?? DEFAULT_PROVIDER_OPTIONS;
  $: availableLanguages = Array.from(new Set(sources.flatMap((source) => source.languages))).sort();
  $: activeProvider = providerOptions.find((option) => option.id === provider) ?? null;
  $: activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;
  $: openConversation = conversations.find((conversation) => conversation.id === openConversationMenuId) ?? null;
  $: currentMessages = activeConversation?.messages ?? [];
  $: resolvedModel = customModel.trim() || model;
  $: modelChoices = uniqueModelNames(
    provider === 'ollama'
      ? [
          ...ollamaModels.map((item) => item.name),
          ...(MODEL_PRESETS[provider] ?? []),
          activeProvider?.default_model ?? '',
          customModel.trim()
        ]
      : [...(MODEL_PRESETS[provider] ?? []), activeProvider?.default_model ?? '', customModel.trim()]
  );
  $: ollamaInstalledNames = ollamaModels.map((item) => item.name);
  $: ollamaModelInstalled = provider !== 'ollama' || ollamaInstalledNames.includes(resolvedModel);
  $: providerRequiresKey = activeProvider?.requires_api_key ?? false;
  $: showApiBaseField = useCustomKey && provider === 'openai_compatible';
  $: sourceCountFromHealth = getIndexedDocumentCount(health);
  $: activeSystem = systems.find((system) => system.id === activeSystemId) ?? null;
  $: catalogOptions = buildCatalogOptions(systems);
  $: if (activeCatalog !== ALL_CATALOG && !catalogOptions.includes(activeCatalog)) {
    activeCatalog = ALL_CATALOG;
  }
  $: resolvedCatalog = catalogOptions.includes(activeCatalog) ? activeCatalog : ALL_CATALOG;
  $: visibleSystems =
    resolvedCatalog === ALL_CATALOG
      ? systems
      : systems.filter((system) => normalizeCatalog(system.catalog) === normalizeCatalog(resolvedCatalog));
  $: hasMultipleCatalogs = catalogOptions.length > 1;
  $: hasSystemSelection = selectedSystemIds.length > 0;
  $: pendingSystemIds = visibleSystems
    .filter((system) => system.analysis_status !== 'analyzed' || !system.level_of_risk)
    .map((system) => system.id);
  $: exampleQuestion = pickExampleQuestion(activeConversationId);
  $: kpiSnapshot = buildKpiSnapshot(systems, sources, health, availableLanguages);
  $: workspaceTitle = buildWorkspaceTitle(centerView, activeConversation);
  $: healthIndicatorLabel =
    health?.status === 'ok' ? 'System ready' : 'Some sources currently unavailable';
  $: healthIndicatorHealthy = health?.status === 'ok';
  $: actSources = sources.filter((source) => ACT_SOURCE_MATCHERS.some((matcher) => matcher.test(source.source)));
  $: amendmentSources = sources.filter((source) => AMENDMENT_MATCHERS.some((matcher) => matcher.test(source.source)));
  $: hasAmendmentSources = amendmentSources.length > 0;
  $: if (centerView !== 'chat' && openConversationMenuId) {
    closeConversationMenu();
  }
  $: if (sources.length > 0 && !hasAppliedSourceDefaults) {
    if (selectedSources.length === 0) {
      const defaults = uniqueIds([
        ...actSources.map((source) => source.source),
        ...amendmentSources.map((source) => source.source)
      ]);
      selectedSources = defaults.length > 0 ? defaults : sources.map((source) => source.source);
    }
    hasAppliedSourceDefaults = true;
  }
  $: if (DEMO_MODE && provider === 'ollama') {
    provider = 'openai';
  }
  $: outputTokenLimit = Number.isFinite(Number(maxOutputTokens)) ? Math.max(0, Number(maxOutputTokens)) : 0;
  $: estimatedInputTokens = estimateTokens(buildEstimateInput());
  $: estimatedTotalTokens = estimatedInputTokens + outputTokenLimit;
  $: inputCostRate = parseCost(inputCostPerMillion);
  $: outputCostRate = parseCost(outputCostPerMillion);
  $: estimatedInputCost = estimateCost(estimatedInputTokens, inputCostRate);
  $: estimatedOutputCost = estimateCost(outputTokenLimit, outputCostRate);
  $: estimatedTotalCost = estimatedInputCost + estimatedOutputCost;
  $: sessionInputCost = estimateCost(sessionInputTokens, inputCostRate);
  $: sessionOutputCost = estimateCost(sessionOutputTokens, outputCostRate);
  $: sessionTotalCost = sessionInputCost + sessionOutputCost;

  $: if (activeProvider && provider === 'ollama' && !apiBase) {
    apiBase = activeProvider.default_base_url ?? 'http://localhost:11434';
  }

  $: if (activeProvider && provider !== 'ollama' && provider !== 'openai_compatible') {
    apiBase = '';
  }

  $: if (!customModel) {
    const preferredModel = activeProvider?.default_model ?? modelChoices[0] ?? '';
    if (preferredModel && (!model || !modelChoices.includes(model))) {
      model = preferredModel;
    }
  }

  $: if (browser) {
    const lookupKey = provider === 'ollama' ? apiBase.trim() : '';
    if (lookupKey && lookupKey !== lastOllamaLookupKey) {
      lastOllamaLookupKey = lookupKey;
      void loadOllamaModels(true);
    }
    if (!lookupKey && lastOllamaLookupKey) {
      lastOllamaLookupKey = '';
      ollamaModels = [];
    }
  }

  onMount(() => {
    hydrateConversations();
    void loadAppState();

    const handleDismiss = () => closeConversationMenu();
    window.addEventListener('resize', handleDismiss);
    window.addEventListener('scroll', handleDismiss, true);
    return () => {
      window.removeEventListener('resize', handleDismiss);
      window.removeEventListener('scroll', handleDismiss, true);
    };
  });

  function hydrateConversations() {
    const storedConversations = sortConversations(loadConversations());
    const storedActiveConversationId = loadActiveConversationId();

    if (storedConversations.length === 0) {
      const conversation = createConversation();
      conversations = [conversation];
      activeConversationId = conversation.id;
      persistConversationState();
      return;
    }

    conversations = storedConversations;
    activeConversationId =
      storedActiveConversationId && storedConversations.some((item) => item.id === storedActiveConversationId)
        ? storedActiveConversationId
        : storedConversations[0].id;
    persistConversationState();
  }

  async function loadAppState() {
    const isInitialLoad = loading;
    if (!isInitialLoad) {
      refreshing = true;
    }

    const systemsPromise = DEMO_MODE ? Promise.resolve(loadDemoSystems()) : fetchSystems();
    const [configResult, sourcesResult, healthResult, systemsResult] = await Promise.allSettled([
      fetchConfig(),
      fetchSources(),
      fetchHealth(),
      systemsPromise
    ]);

    const issues: string[] = [];

    if (configResult.status === 'fulfilled') {
      config = configResult.value;
      if (!hasAppliedConfigDefaults) {
        topK = config.default_top_k;
        provider = config.default_provider;
        model = config.default_model;
        apiBase = config.default_api_base ?? '';
        hasAppliedConfigDefaults = true;
      }
    } else if (!config) {
      issues.push('config');
    }

    if (sourcesResult.status === 'fulfilled') {
      sources = sourcesResult.value;
    } else if (!sources.length) {
      issues.push('sources');
    }

    if (healthResult.status === 'fulfilled') {
      health = healthResult.value;
    } else if (!health) {
      issues.push('health');
    }

    if (systemsResult.status === 'fulfilled') {
      syncSystems(systemsResult.value);
    } else if (!systems.length && !DEMO_MODE) {
      issues.push('systems');
    }

    if (provider === 'ollama') {
      await loadOllamaModels(true);
    }

    if (issues.length > 0) {
      setStatus('System warming up : some features unavailable.', 'connection');
    } else {
      clearStatus('connection');
    }
    loading = false;
    refreshing = false;
  }

  async function loadOllamaModels(silent = false) {
    if (!browser || provider !== 'ollama') {
      return;
    }
    try {
      const response = await fetchOllamaModels(apiBase || undefined);
      ollamaModels = response.models;
    } catch (caught) {
      ollamaModels = [];
      if (!silent) {
        setStatus('We could not reach the assistant. Please retry.', 'connection');
      }
    }
  }

  function setStatus(message: string, kind: 'connection' | 'action' = 'action') {
    if (statusKind === 'connection' && kind === 'action') {
      return;
    }
    statusMessage = message;
    statusKind = message ? kind : '';
  }

  function clearStatus(kind?: 'connection' | 'action') {
    if (!kind || statusKind === kind) {
      statusMessage = '';
      statusKind = '';
    }
  }

  function uniqueModelNames(values: string[]): string[] {
    const normalized = values.map((value) => value.trim()).filter(Boolean);
    return Array.from(new Set(normalized));
  }

  function estimateTokens(text: string): number {
    if (!text) {
      return 0;
    }
    return Math.max(1, Math.ceil(text.length / 4));
  }

  function parseCost(value: string): number {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
  }

  function estimateCost(tokens: number, ratePerMillion: number): number {
    if (!tokens || !ratePerMillion) {
      return 0;
    }
    return (tokens / 1_000_000) * ratePerMillion;
  }

  function formatCost(value: number): string {
    if (!value || !Number.isFinite(value)) {
      return '0';
    }
    const fixed = value.toFixed(4);
    return fixed.replace(/0+$/, '').replace(/\.$/, '');
  }

  function buildEstimateInputFor(
    questionText: string,
    role: UserRole,
    system: AISystem | null
  ): string {
    const parts: string[] = [];
    const trimmedQuestion = questionText.trim();
    if (trimmedQuestion) {
      parts.push(trimmedQuestion);
    }
    if (role) {
      parts.push(`Role: ${role}`);
    }
    if (system) {
      parts.push(system.name);
      parts.push(system.description);
    }
    return parts.filter(Boolean).join(' ');
  }

  function buildEstimateInput(): string {
    return buildEstimateInputFor(question, userRole, activeSystem);
  }

  function resetSessionUsage() {
    sessionInputTokens = 0;
    sessionOutputTokens = 0;
  }

  function buildCopyText(message: ChatMessage): string {
    const header = message.role === 'user' ? 'Question' : 'Answer';
    let text = `${header}:\n${message.content.trim()}`;
    if (message.citations && message.citations.length > 0) {
      const citationsText = message.citations
        .map(
          (citation) =>
            `${citation.label} (pp. ${citation.page_start}-${citation.page_end}): ${citation.excerpt}`
        )
        .join('\n');
      text += `\n\nSources:\n${citationsText}`;
    }
    return text.trim();
  }

  async function copyMessage(message: ChatMessage) {
    const payload = buildCopyText(message);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(payload);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = payload;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        textarea.remove();
      }
      copiedMessageId = message.id;
      window.setTimeout(() => {
        if (copiedMessageId === message.id) {
          copiedMessageId = '';
        }
      }, 1600);
    } catch (error) {
      setStatus('We could not copy that message. Please try again.');
    }
  }

  function sortConversations(items: Conversation[]): Conversation[] {
    return [...items].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  }

  function persistConversationState() {
    saveConversations(conversations);
    saveActiveConversationId(activeConversationId);
  }

  function useSuggestedQuestion(value: string) {
    question = value;
    requestAnimationFrame(() => questionInput?.focus());
  }

  function handleCustomKeyToggle(nextValue: boolean) {
    useCustomKey = nextValue;
    if (!useCustomKey) {
      apiKey = '';
    }
  }

  function createNewConversation() {
    const conversation = createConversation();
    conversations = sortConversations([conversation, ...conversations]);
    activeConversationId = conversation.id;
    centerView = 'chat';
    question = '';
    clearStatus('action');
    notice = '';
    suggestedSystem = null;
    persistConversationState();
  }

  function selectConversation(conversationId: string) {
    activeConversationId = conversationId;
    centerView = 'chat';
    clearStatus('action');
    notice = '';
    openConversationMenuId = '';
    persistConversationState();
  }

  function deleteConversation(conversationId: string) {
    const remaining = conversations.filter((conversation) => conversation.id !== conversationId);
    if (remaining.length === 0) {
      const replacement = createConversation();
      conversations = [replacement];
      activeConversationId = replacement.id;
    } else {
      conversations = sortConversations(remaining);
      if (activeConversationId === conversationId) {
        activeConversationId = conversations[0].id;
      }
    }
    persistConversationState();
  }

  async function toggleConversationMenu(conversationId: string, event?: MouseEvent) {
    if (openConversationMenuId === conversationId) {
      closeConversationMenu();
      return;
    }
    if (event?.currentTarget instanceof HTMLElement) {
      conversationMenuAnchor = event.currentTarget;
      const rect = event.currentTarget.getBoundingClientRect();
      const menuWidth = 176;
      const menuHeight = 96;
      const padding = 10;
      const openAbove = rect.top > menuHeight + padding * 2;
      const topCandidate = openAbove ? rect.top - menuHeight - padding : rect.bottom + padding;
      const leftCandidate = rect.right - menuWidth;
      const top = Math.min(
        window.innerHeight - menuHeight - padding,
        Math.max(padding, topCandidate)
      );
      const left = Math.min(
        window.innerWidth - menuWidth - padding,
        Math.max(padding, leftCandidate)
      );
      conversationMenuStyle = `top:${Math.round(top)}px; left:${Math.round(left)}px;`;
    }
    openConversationMenuId = conversationId;
    await tick();
    const firstItem = conversationMenuEl?.querySelector<HTMLElement>('button');
    firstItem?.focus();
  }

  async function openRenameDialog(conversationId: string) {
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation) {
      return;
    }
    storeLastFocus();
    renameConversationId = conversationId;
    renameDraft = conversation.title;
    renameDialogOpen = true;
    openConversationMenuId = '';
    await tick();
    renameInput?.focus();
  }

  function submitRenameDialog() {
    if (!renameDialogOpen || !renameConversationId) {
      return;
    }
    const nextTitle = renameDraft.trim();
    if (!nextTitle) {
      return;
    }
    updateConversation(renameConversationId, (item) => ({
      ...item,
      title: nextTitle,
      updatedAt: new Date().toISOString()
    }));
    closeRenameDialog();
  }

  function closeRenameDialog() {
    renameDialogOpen = false;
    renameConversationId = '';
    renameDraft = '';
    const restoreTarget = lastFocusedElement;
    lastFocusedElement = null;
    restoreTarget?.focus();
  }

  function closeConversationMenu() {
    openConversationMenuId = '';
    conversationMenuStyle = '';
    conversationMenuAnchor = null;
  }

  function handleWindowClick(event: MouseEvent) {
    if (!openConversationMenuId) {
      return;
    }
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }
    if (conversationMenuEl?.contains(target) || conversationMenuAnchor?.contains(target)) {
      return;
    }
    closeConversationMenu();
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (showSystemForm) {
        clearSystemForm();
        return;
      }
      if (renameDialogOpen) {
        closeRenameDialog();
        return;
      }
      if (openConversationMenuId) {
        closeConversationMenu();
      }
    }
  }

  function storeLastFocus() {
    lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }

  async function focusSystemForm() {
    await tick();
    const focusTarget = systemFormEl?.querySelector<HTMLElement>('input, textarea, select, button');
    focusTarget?.focus();
  }

  function ensureActiveConversation(): string {
    if (activeConversationId && conversations.some((conversation) => conversation.id === activeConversationId)) {
      return activeConversationId;
    }
    createNewConversation();
    return activeConversationId;
  }

  function updateConversation(conversationId: string, updater: (conversation: Conversation) => Conversation) {
    conversations = sortConversations(
      conversations.map((conversation) =>
        conversation.id === conversationId ? updater(conversation) : conversation
      )
    );
    persistConversationState();
  }

  function replaceConversationMessage(conversationId: string, messageId: string, nextMessage: ChatMessage) {
    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      updatedAt: new Date().toISOString(),
      messages: conversation.messages.map((message) => (message.id === messageId ? nextMessage : message))
    }));
  }

  async function ensureAssistantReady(): Promise<boolean> {
    if (provider !== 'ollama' || ollamaModelInstalled) {
      return true;
    }
    const targetModel = resolvedModel.trim();
    if (!targetModel) {
      return true;
    }
    preparingAssistant = true;
    try {
      await pullOllamaModel(targetModel, apiBase || undefined);
      await loadOllamaModels(true);
      return true;
    } catch (caught) {
      setStatus('We could not prepare the assistant. Please try again.');
      return false;
    } finally {
      preparingAssistant = false;
    }
  }

  async function submitQuestion() {
    const trimmed = question.trim();
    if (!trimmed || submitting) {
      return;
    }
    const inputEstimate = estimateTokens(buildEstimateInputFor(trimmed, userRole, activeSystem));

    if (useCustomKey && providerRequiresKey && !apiKey.trim()) {
      const message = 'Add your API key or turn off "Use my API key" to continue.';
      setStatus(message);
      return;
    }

    const conversationId = ensureActiveConversation();
    const now = new Date().toISOString();
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed
    };
    const pendingMessageId = crypto.randomUUID();
    const pendingMessage: ChatMessage = {
      id: pendingMessageId,
      role: 'assistant',
      content: 'Searching indexed provisions and preparing an answer…',
      answerMode: 'loading',
      pending: true
    };

    updateConversation(conversationId, (conversation) => {
      const firstUserMessage = !conversation.messages.some((message) => message.role === 'user');
      return {
        ...conversation,
        title: firstUserMessage ? buildConversationTitle(trimmed) : conversation.title,
        updatedAt: now,
        messages: [...conversation.messages, userMessage, pendingMessage]
      };
    });

    question = '';
    submitting = true;
    clearStatus('action');
    notice = '';
    if (!activeSystem) {
      suggestedSystem = detectSuggestedSystem(trimmed, systems);
    }

    const ready = await ensureAssistantReady();
    if (!ready) {
      const errorMessage = 'We could not prepare the assistant. Please try again.';
      replaceConversationMessage(conversationId, pendingMessageId, {
        id: pendingMessageId,
        role: 'assistant',
        content: errorMessage,
        answerMode: 'error'
      });
      setStatus(errorMessage);
      submitting = false;
      return;
    }

    try {
          const modelOverride = useCustomKey
        ? {
            provider,
            model: resolvedModel,
            api_base: apiBase || undefined,
            api_key: apiKey || undefined,
            max_tokens: maxOutputTokens ? Number(maxOutputTokens) : undefined
          }
        : undefined;
      const response: QueryResponse = await postQuery({
        question: trimmed,
        sources: selectedSources.length ? selectedSources : undefined,
        languages: selectedLanguages.length ? selectedLanguages : undefined,
        top_k: topK,
        user_role: userRole,
        system: activeSystem
          ? {
              id: activeSystem.id,
              name: activeSystem.name,
              description: activeSystem.description,
              system_type: activeSystem.system_type,
              catalog: activeSystem.catalog ?? undefined,
              level_of_risk: activeSystem.level_of_risk ?? undefined,
              confidence: activeSystem.confidence ?? undefined
            }
          : undefined,
        model: modelOverride
      });

      replaceConversationMessage(conversationId, pendingMessageId, {
        id: pendingMessageId,
        role: 'assistant',
        content: response.answer,
        citations: response.citations,
        confidence: response.confidence,
        lowConfidence: response.low_confidence,
        warning: response.warning,
        answerMode: response.answer_mode
      });
      const outputEstimate = estimateTokens(response.answer);
      sessionInputTokens += inputEstimate;
      sessionOutputTokens += outputEstimate;
      await refreshHealth();
    } catch (caught) {
      const message = 'We could not complete that request. Please try again.';
      replaceConversationMessage(conversationId, pendingMessageId, {
        id: pendingMessageId,
        role: 'assistant',
        content: message,
        answerMode: 'error'
      });
      setStatus(message);
    } finally {
      submitting = false;
    }
  }

  async function refreshHealth() {
    try {
      health = await fetchHealth();
      clearStatus('connection');
    } catch (caught) {
      setStatus('We could not refresh the system status. Please retry.', 'connection');
    }
  }

  async function submitSystem() {
    if (!systemName.trim() || !systemDescription.trim() || !systemType.trim() || savingSystem) {
      return;
    }

    const catalogValue = normalizeCatalog(systemCatalog);
    savingSystem = true;
    clearStatus('action');
    notice = '';
    try {
      if (DEMO_MODE) {
        const payload = {
          name: systemName.trim(),
          description: systemDescription.trim(),
          system_type: systemType.trim(),
          catalog: catalogValue
        };
        if (editingSystemId) {
          const existing = systems.find((system) => system.id === editingSystemId);
          const updated = existing ? updateDemoSystem(existing, payload) : buildDemoSystem(payload);
          syncSystems(mergeSystems(systems, [updated]));
          activeSystemId = updated.id;
          selectedSystemIds = uniqueIds([updated.id, ...selectedSystemIds]);
          notice = `Updated ${updated.name}. Analysis was reset if the description or type changed.`;
        } else {
          const created = buildDemoSystem(payload);
          syncSystems(mergeSystems(systems, [created]));
          activeSystemId = created.id;
          selectedSystemIds = uniqueIds([created.id, ...selectedSystemIds]);
          notice = `Added ${created.name} to the AI systems catalog.`;
        }
      } else if (editingSystemId) {
        const system = await updateSystem(editingSystemId, {
          name: systemName.trim(),
          description: systemDescription.trim(),
          system_type: systemType.trim(),
          catalog: catalogValue
        });
        syncSystems(mergeSystems(systems, [system]));
        activeSystemId = system.id;
        selectedSystemIds = uniqueIds([system.id, ...selectedSystemIds]);
        notice = `Updated ${system.name}. Analysis was reset if the description or type changed.`;
      } else {
        const response = await upsertSystem({
          name: systemName.trim(),
          description: systemDescription.trim(),
          system_type: systemType.trim(),
          catalog: catalogValue
        });
        syncSystems(mergeSystems(systems, [response.system]));
        activeSystemId = response.system.id;
        selectedSystemIds = uniqueIds([response.system.id, ...selectedSystemIds]);
        notice = response.created
          ? `Added ${response.system.name} to the AI systems catalog.`
          : `Updated ${response.system.name}. Existing analysis was reset if the description changed.`;
      }
      clearSystemForm();
      suggestedSystem = null;
    } catch (caught) {
      setStatus('We could not save that system. Please try again.');
    } finally {
      savingSystem = false;
    }
  }

  async function addSuggestedSystem() {
    if (!suggestedSystem) {
      return;
    }
    editingSystemId = '';
    systemName = suggestedSystem.name;
    systemDescription = suggestedSystem.description;
    systemType = suggestedSystem.system_type;
    systemCatalog = resolvedCatalog === ALL_CATALOG ? DEFAULT_CATALOG : resolvedCatalog;
    showSystemForm = false;
    await submitSystem();
  }

  async function deleteSystemRecord(systemId: string) {
    clearStatus('action');
    notice = '';
    try {
      if (DEMO_MODE) {
        syncSystems(systems.filter((system) => system.id !== systemId));
        if (editingSystemId === systemId) {
          clearSystemForm();
        }
        if (activeSystemId === systemId) {
          activeSystemId = '';
        }
        notice = 'AI system removed from the catalog.';
      } else {
        await removeSystem(systemId);
        syncSystems(systems.filter((system) => system.id !== systemId));
        if (editingSystemId === systemId) {
          clearSystemForm();
        }
        if (activeSystemId === systemId) {
          activeSystemId = '';
        }
        notice = 'AI system removed from the catalog.';
      }
    } catch (caught) {
      setStatus('We could not remove that system. Please try again.');
    }
  }

  async function exportSystemsCatalog() {
    clearStatus('action');
    notice = '';
    try {
      const payload = DEMO_MODE ? systems : await fetchSystemsExport();
      const serialized = JSON.stringify(payload, null, 2);
      const blob = new Blob([serialized], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      const dateLabel = new Date().toISOString().slice(0, 10);
      anchor.href = url;
      anchor.download = `ai-systems-${dateLabel}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      notice = `Exported ${payload.length} AI system${payload.length === 1 ? '' : 's'} to JSON.`;
    } catch (caught) {
      setStatus('We could not export the catalog. Please try again.');
    }
  }

  async function importSystemsCatalog() {
    if (importingSystems) {
      return;
    }
    importingSystems = true;
    clearStatus('action');
    notice = '';

    const file = await promptForFile();
    if (!file) {
      importingSystems = false;
      return;
    }

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const importedSystems = Array.isArray(parsed) ? parsed : parsed?.systems;
      if (!Array.isArray(importedSystems) || importedSystems.length === 0) {
        throw new Error('Import file did not contain an AI systems array.');
      }
      if (DEMO_MODE) {
        const merged = mergeSystems(systems, importedSystems);
        syncSystems(merged);
        notice = `Imported ${importedSystems.length} AI system${importedSystems.length === 1 ? '' : 's'} into this browser.`;
      } else {
        const response = await postSystemsImport({ systems: importedSystems, mode: 'merge' });
        syncSystems(await fetchSystems());
        notice = `Imported ${response.imported} new system${response.imported === 1 ? '' : 's'} and updated ${response.updated} existing system${response.updated === 1 ? '' : 's'}.`;
      }
    } catch (caught) {
      setStatus('We could not import that file. Please try again.');
    } finally {
      importingSystems = false;
    }
  }

  function promptForFile(): Promise<File | null> {
    return new Promise((resolve) => {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'application/json';
      input.onchange = () => resolve(input.files?.[0] ?? null);
      input.click();
    });
  }

  function applyCatalogFilter(nextCatalog: string) {
    activeCatalog = nextCatalog;
    selectedSystemIds = [];
    if (!editingSystemId) {
      systemCatalog = nextCatalog === ALL_CATALOG ? DEFAULT_CATALOG : nextCatalog;
    }
  }

  function openNewSystemForm() {
    closeConversationMenu();
    storeLastFocus();
    showSystemForm = true;
    editingSystemId = '';
    systemName = '';
    systemDescription = '';
    systemType = '';
    systemCatalog = resolvedCatalog === ALL_CATALOG ? DEFAULT_CATALOG : resolvedCatalog;
    clearStatus('action');
    notice = '';
    void focusSystemForm();
  }

  function toggleSystemSelection(systemId: string) {
    selectedSystemIds = toggleItem(systemId, selectedSystemIds);
  }

  function analyzeSelectedSystems() {
    requestSystemAnalysis(selectedSystemIds);
  }

  function analyzePendingSystems() {
    requestSystemAnalysis(pendingSystemIds);
  }

  function analyzeSingleSystem(systemId: string) {
    requestSystemAnalysis([systemId]);
  }

  function requestSystemAnalysis(systemIds: string[]) {
    const ids = uniqueIds(systemIds);
    if (!ids.length) {
      setStatus('Select at least one AI system to analyze.');
      return;
    }
    const duplicates = ids
      .map((systemId) => systems.find((system) => system.id === systemId) ?? null)
      .filter(
        (system): system is AISystem =>
          system !== null && system.analysis_status === 'analyzed' && Boolean(system.level_of_risk)
      );
    if (duplicates.length) {
      analysisConfirmation = { ids, duplicates };
      return;
    }
    void runSystemAnalysis(ids, false);
  }

  async function runSystemAnalysis(systemIds: string[], force: boolean) {
    const ids = uniqueIds(systemIds);
    if (!ids.length) {
      notice = 'Everything selected is already analyzed.';
      return;
    }

    if (DEMO_MODE) {
      setStatus(
        'Demo mode: analysis is disabled here. Your catalog is stored locally in this browser only. For full analysis, download Koala from GitHub and run it locally.'
      );
      return;
    }

    if (useCustomKey && providerRequiresKey && !apiKey.trim()) {
      setStatus('Add your API key or turn off "Use my API key" to analyze systems.');
      return;
    }

    systemAnalyzing = true;
    analyzingSystemIds = ids;
    analysisConfirmation = null;
    clearStatus('action');
    notice = '';
    try {
      const modelOverride = useCustomKey
        ? {
            provider,
            model: resolvedModel,
            api_base: apiBase || undefined,
            api_key: apiKey || undefined,
            max_tokens: maxOutputTokens ? Number(maxOutputTokens) : undefined
          }
        : undefined;
      const response = await postAnalyzeSystems({
        system_ids: ids,
        force,
        user_role: userRole,
        model: modelOverride
      });
      syncSystems(mergeSystems(systems, [...response.analyzed, ...response.skipped]));
      if (response.failures.length > 0) {
        setStatus('Some systems could not be analyzed. Please try again.');
      }
      if (response.analyzed.length > 0) {
        notice = `Analysis completed for ${response.analyzed.length} AI system${response.analyzed.length === 1 ? '' : 's'}.`;
      } else if (response.skipped.length > 0) {
        notice = 'Skipped AI systems that already had stored analysis.';
      } else {
        notice = 'No AI systems were analyzed.';
      }
    } catch (caught) {
      setStatus('We could not complete the analysis. Please try again.');
    } finally {
      systemAnalyzing = false;
      analyzingSystemIds = [];
    }
  }

  function confirmSkipAnalyzed() {
    if (!analysisConfirmation) {
      return;
    }
    const duplicateIds = new Set(analysisConfirmation.duplicates.map((system) => system.id));
    void runSystemAnalysis(
      analysisConfirmation.ids.filter((systemId) => !duplicateIds.has(systemId)),
      false
    );
  }

  function confirmReanalyzeAll() {
    if (!analysisConfirmation) {
      return;
    }
    void runSystemAnalysis(analysisConfirmation.ids, true);
  }

  function cancelAnalysisConfirmation() {
    analysisConfirmation = null;
  }

  function syncSystems(nextSystems: AISystem[]) {
    systems = [...nextSystems];
    if (activeSystemId && !systems.some((system) => system.id === activeSystemId)) {
      activeSystemId = '';
    }
    selectedSystemIds = selectedSystemIds.filter((systemId) =>
      systems.some((system) => system.id === systemId)
    );
    if (suggestedSystem && systems.some((system) => normalizeText(system.name) === normalizeText(suggestedSystem.name))) {
      suggestedSystem = null;
    }
    if (DEMO_MODE) {
      saveDemoSystems(systems);
    }
  }

  function mergeSystems(current: AISystem[], incoming: AISystem[]): AISystem[] {
    const merged = new Map(current.map((system) => [system.id, system]));
    for (const system of incoming) {
      merged.set(system.id, system);
    }
    return Array.from(merged.values()).sort((left, right) => right.updated_at.localeCompare(left.updated_at));
  }

  function uniqueIds(values: string[]): string[] {
    return Array.from(new Set(values.filter(Boolean)));
  }

  function toggleItem(value: string, current: string[]): string[] {
    return current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
  }

  function isProviderDisabled(option: ProviderOption): boolean {
    return DEMO_MODE && option.id === 'ollama';
  }

  function toggleSource(value: string) {
    selectedSources = toggleItem(value, selectedSources);
  }

  function toggleLanguage(value: string) {
    selectedLanguages = toggleItem(value, selectedLanguages);
  }

  function resetFilters() {
    selectedLanguages = [];
    const defaults = uniqueIds([
      ...actSources.map((source) => source.source),
      ...amendmentSources.map((source) => source.source)
    ]);
    selectedSources = defaults.length > 0 ? defaults : sources.map((source) => source.source);
  }

  function conversationPreview(conversation: Conversation): string {
    const lastMessage = [...conversation.messages]
      .reverse()
      .find((message) => message.content.trim().length > 0);
    if (!lastMessage) {
      return 'No messages yet.';
    }
    const normalized = lastMessage.content.replace(/\s+/g, ' ').trim();
    return normalized.length > 96 ? `${normalized.slice(0, 96)}…` : normalized;
  }

  function formatConversationTime(timestamp: string): string {
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(timestamp));
  }

  function formatSystemTime(timestamp: string | null | undefined): string {
    if (!timestamp) {
      return 'Never';
    }
    return new Intl.DateTimeFormat(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(timestamp));
  }

  function getIndexedDocumentCount(payload: HealthResponse | null): number {
    const count = Number(payload?.store?.document_count ?? 0);
    return Number.isFinite(count) ? count : 0;
  }

  function renderMessage(content: string): string {
    return renderMarkdown(content);
  }

  function formatRiskLevel(value: string | null | undefined): string {
    if (!value) {
      return 'Not analyzed';
    }
    return value
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function normalizeText(value: string): string {
    return value.trim().toLowerCase();
  }

  function normalizeCatalog(value?: string | null): string {
    const cleaned = (value ?? '').trim();
    return cleaned || DEFAULT_CATALOG;
  }


  function buildCatalogOptions(systemsList: AISystem[]): string[] {
    const options = new Set<string>([DEFAULT_CATALOG]);
    for (const system of systemsList) {
      options.add(normalizeCatalog(system.catalog));
    }
    return Array.from(options).sort((a, b) => a.localeCompare(b));
  }

  function buildWorkspaceTitle(view: typeof centerView, conversation: Conversation | null): string {
    if (view === 'chat') {
      return conversation?.title ?? 'New conversation';
    }
    if (view === 'catalog') {
      return 'Catalog';
    }
    if (view === 'kpis') {
      return 'KPIs';
    }
    if (view === 'setup') {
      return 'AI Setup';
    }
    return 'Help';
  }

  function pickExampleQuestion(conversationId: string): string {
    if (!conversationId) {
      return EXAMPLE_QUESTIONS[0];
    }
    let hash = 0;
    for (const char of conversationId) {
      hash = (hash * 31 + char.charCodeAt(0)) % EXAMPLE_QUESTIONS.length;
    }
    return EXAMPLE_QUESTIONS[Math.abs(hash) % EXAMPLE_QUESTIONS.length];
  }

  function formatAnswerMode(mode: string): string {
    return ANSWER_MODE_LABELS[mode] ?? mode.replace(/_/g, ' ');
  }

  function buildKpiSnapshot(
    systemsList: AISystem[],
    sourcesList: SourceSummary[],
    healthPayload: HealthResponse | null,
    languagesList: string[]
  ) {
    const indexedRecords = getIndexedDocumentCount(healthPayload);
    const analyzed = systemsList.filter((system) => system.analysis_status === 'analyzed');
    const analyzedCount = analyzed.length;
    const avgConfidence = analyzed.length
      ? Math.round(
          analyzed.reduce((sum, system) => sum + (system.confidence ?? 0), 0) / analyzed.length
        )
      : 0;
    const lastAnalysis =
      analyzed
        .map((system) => system.last_analyzed_at)
        .filter((value): value is string => Boolean(value))
        .sort()
        .at(-1) ?? null;
    return {
      indexedRecords,
      sourceCount: sourcesList.length,
      languageCount: languagesList.length,
      systemCount: systemsList.length,
      analyzedCount,
      avgConfidence,
      lastAnalysis
    };
  }

  function startEditingSystem(system: AISystem) {
    centerView = 'catalog';
    activeSystemId = system.id;
    storeLastFocus();
    editingSystemId = system.id;
    systemName = system.name;
    systemDescription = system.description;
    systemType = system.system_type;
    systemCatalog = normalizeCatalog(system.catalog);
    showSystemForm = true;
    notice = '';
    clearStatus('action');
    void focusSystemForm();
  }

  function clearSystemForm() {
    editingSystemId = '';
    systemName = '';
    systemDescription = '';
    systemType = '';
    systemCatalog = resolvedCatalog === ALL_CATALOG ? DEFAULT_CATALOG : resolvedCatalog;
    showSystemForm = false;
    const restoreTarget = lastFocusedElement;
    lastFocusedElement = null;
    restoreTarget?.focus();
  }

  function useSystemInChat(systemId: string) {
    activeSystemId = systemId;
    centerView = 'chat';
  }
</script>

<svelte:head>
  <title>Koala : AI Governance Assistant</title>
  <meta
    name="description"
    content="Open-source AI governance assistant for the EU AI Act and the Digital Omnibus on AI proposal."
  />
</svelte:head>

<svelte:window on:click={handleWindowClick} on:keydown={handleWindowKeydown} />

{#if loading}
  <main class="shell loading-shell">
    <section class="loading-card">
      <p class="eyebrow">Preparing workspace</p>
      <h1>Preparing your workspace</h1>
    </section>
  </main>
{:else}
  <main
    class="shell"
    class:history-hidden={!showHistoryPanel}
    class:controls-hidden={!showControlsPanel}
  >
    <div class="background-orb orb-a"></div>
    <div class="background-orb orb-b"></div>

    {#if showHistoryPanel}
      <aside class="panel history-panel">
        <div class="history-head">
          <div>
            <p class="eyebrow">History</p>
            <h2>Conversations</h2>
          </div>
          <span class="version-pill">{conversations.length}</span>
        </div>

        <div class="conversation-list" on:scroll={closeConversationMenu}>
          {#each conversations as conversation (conversation.id)}
            <article
              class:selected={conversation.id === activeConversationId}
              class="conversation-card"
              title={`Updated ${formatConversationTime(conversation.updatedAt)}`}
            >
              <button
                class="conversation-select"
                type="button"
                on:click={() => selectConversation(conversation.id)}
              >
                <div class="conversation-heading">
                  <strong>{conversation.title}</strong>
                </div>
                {#if conversation.messages.length > 0}
                  <p class="conversation-preview">{conversationPreview(conversation)}</p>
                {/if}
              </button>
              <div class="conversation-actions">
                <button
                  class="menu-button"
                  type="button"
                  on:click|stopPropagation={(event) => toggleConversationMenu(conversation.id, event)}
                  aria-label={`Open menu for ${conversation.title}`}
                >
                  ···
                </button>
              </div>
            </article>
          {/each}
        </div>
      </aside>
    {/if}

    <section class="panel chat-panel">
      <div class="workspace-bar">
        <div class="workspace-title">
          <div>
            <p class="eyebrow">🐨 Koala</p>
            <h2>{workspaceTitle}</h2>
          </div>
        </div>
        <div class="workspace-controls">
          <div class="view-tabs">
            <button
              class:active-tab={centerView === 'chat'}
              class="ghost-button"
              type="button"
              on:click={() => (centerView = 'chat')}
            >
              Chat
            </button>
            <button
              class:active-tab={centerView === 'catalog'}
              class="ghost-button"
              type="button"
              on:click={() => (centerView = 'catalog')}
            >
              Catalog
            </button>
            <button
              class:active-tab={centerView === 'kpis'}
              class="ghost-button"
              type="button"
              on:click={() => (centerView = 'kpis')}
            >
              KPIs
            </button>
            <button
              class:active-tab={centerView === 'setup'}
              class="ghost-button"
              type="button"
              on:click={() => (centerView = 'setup')}
            >
              AI Setup
            </button>
            <button
              class:active-tab={centerView === 'help'}
              class="ghost-button"
              type="button"
              on:click={() => (centerView = 'help')}
            >
              Help
            </button>
          </div>
          <div class="panel-toggle-row">
            <span class="health-indicator" title={healthIndicatorLabel}>
              <span class:healthy={healthIndicatorHealthy} class="health-dot"></span>
            </span>
            <button class="panel-toggle-button" type="button" on:click={() => (showHistoryPanel = !showHistoryPanel)}>
              {showHistoryPanel ? 'Hide history' : 'Show history'}
            </button>
            <button class="panel-toggle-button" type="button" on:click={() => (showControlsPanel = !showControlsPanel)}>
              {showControlsPanel ? 'Hide context' : 'Show context'}
            </button>
          </div>
        </div>
      </div>

      <div class="status-inline">
        <p class="muted">
          You are reviewing as: <strong>{ROLE_OPTIONS.find((option) => option.value === userRole)?.label}</strong>
          {#if activeSystem}
            · System focus: <strong>{activeSystem.name}</strong>
          {/if}
        </p>
        <div class="status-inline-right">
          <span class="act-badge">{ACT_BADGE}</span>
          {#if hasAmendmentSources}
            <span class="amendment-pill">
              Amendments indexed · {AMENDMENT_LABEL}
            </span>
          {/if}
        </div>
      </div>

      {#if statusMessage}
        <div class="status-pill-row">
          <span class="status-message-pill">{statusMessage}</span>
          {#if statusKind === 'connection'}
            <button class="ghost-button compact-ghost" type="button" on:click={loadAppState}>
              Retry connection
            </button>
          {/if}
        </div>
      {/if}

      {#if notice}
        <p class="notice-banner">{notice}</p>
      {/if}

      {#if centerView === 'chat'}
        <div class="chat-toolbar">
          <button class="submit-button compact-button" type="button" on:click={createNewConversation}>
            New chat
          </button>
        </div>

        {#if suggestedSystem}
          <section class="suggestion-card">
            <div>
              <p class="eyebrow">Detected System Mention</p>
              <strong>{suggestedSystem.name}</strong>
              <p class="muted">
                This conversation looks system-specific. Add it to the AI systems catalog so you can reuse it in future analysis.
              </p>
            </div>
            <div class="inline-actions">
              <button class="submit-button compact-button" type="button" on:click={addSuggestedSystem}>
                Add to catalog
              </button>
              <button class="ghost-button" type="button" on:click={() => (centerView = 'catalog')}>
                Review catalog
              </button>
            </div>
          </section>
        {/if}

        <div class="message-list">
          {#if currentMessages.length === 0}
            <article class="empty-state" in:fly={{ y: 10, duration: 300 }}>
              <h3>Suggested questions</h3>
              <p class="muted">Pick one to get started.</p>
              <div class="suggested-grid">
                {#each SUGGESTED_QUESTIONS as suggestion}
                  <button class="suggested-chip" type="button" on:click={() => useSuggestedQuestion(suggestion)}>
                    {suggestion}
                  </button>
                {/each}
              </div>
            </article>
          {/if}

          {#each currentMessages as message (message.id)}
            <article
              class:user={message.role === 'user'}
              class:assistant={message.role === 'assistant'}
              class:pending={message.pending}
              class="message-card"
              in:fly={{ y: 12, duration: 250 }}
            >
              <header class="message-head">
                <div class="message-title">
                  <span>{message.role === 'user' ? 'Question' : 'Answer'}</span>
                  {#if message.role === 'assistant' && message.answerMode}
                    <small>{formatAnswerMode(message.answerMode)}</small>
                  {/if}
                </div>
                <button
                  class="ghost-button compact-ghost copy-button"
                  type="button"
                  disabled={message.pending}
                  on:click={() => copyMessage(message)}
                >
                  {copiedMessageId === message.id ? 'Copied' : 'Copy'}
                </button>
              </header>

              <div class="message-body markdown-body">
                {#if message.pending}
                  <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                {/if}
                {@html renderMessage(message.content)}
              </div>

              {#if message.role === 'assistant' && typeof message.confidence === 'number'}
                <div class="confidence-row">
                  <span class:low={message.lowConfidence} class="confidence-pill">
                    Confidence {Math.round(message.confidence * 100)}%
                  </span>
                  {#if message.warning}
                    <span class="warning-text">{message.warning}</span>
                  {/if}
                </div>
              {/if}

              {#if message.citations && message.citations.length > 0}
                <div class="citation-list">
                  {#each message.citations as citation}
                    <article class="citation-card">
                      <div class="citation-head">
                        <strong>{citation.label}</strong>
                        <span>pp. {citation.page_start}-{citation.page_end}</span>
                      </div>
                      <p>{citation.excerpt}</p>
                    </article>
                  {/each}
                </div>
              {/if}
            </article>
          {/each}
        </div>

        <form class="composer" on:submit|preventDefault={submitQuestion}>
          <label class="composer-field">
            <span>Question</span>
            <textarea
              bind:value={question}
              bind:this={questionInput}
              rows="4"
              placeholder={`Ask a compliance question. Example: "${exampleQuestion}"`}
            ></textarea>
          </label>

          <div class="composer-actions">
            <div class="composer-meta">
              {#if preparingAssistant}
                <span class="preparing-label">Preparing…</span>
              {/if}
            </div>
            <button class="submit-button" type="submit" disabled={submitting || !question.trim()}>
              {submitting ? 'Working…' : 'Ask question'}
            </button>
          </div>
        </form>
      {:else if centerView === 'catalog'}
        <div class="workspace-screen catalog-screen">
          <section class="card catalog-entries">
            <div class="section-head section-head-split">
              <div>
                <h2>Catalog entries</h2>
                <span>
                  {visibleSystems.length === 0
                    ? resolvedCatalog === ALL_CATALOG
                      ? 'No systems registered yet'
                      : `No systems in ${resolvedCatalog}`
                    : resolvedCatalog === ALL_CATALOG
                      ? `${systems.length} total`
                      : `${visibleSystems.length} in ${resolvedCatalog} · ${systems.length} total`}
                </span>
              </div>
              <div class="inline-actions catalog-toolbar">
                {#if hasMultipleCatalogs}
                  <label class="select-field">
                    <span>
                      Viewing: {resolvedCatalog === ALL_CATALOG ? ALL_CATALOG_LABEL : resolvedCatalog}
                    </span>
                    <select bind:value={activeCatalog} on:change={() => applyCatalogFilter(activeCatalog)}>
                      <option value={ALL_CATALOG}>{ALL_CATALOG_LABEL}</option>
                      {#each catalogOptions as catalog}
                        <option value={catalog}>{catalog}</option>
                      {/each}
                    </select>
                  </label>
                {/if}
                <button class="submit-button compact-button" type="button" on:click={openNewSystemForm}>
                  New system
                </button>
                {#if !DEMO_MODE && visibleSystems.length > 0}
                  <button
                    class="ghost-button compact-ghost"
                    type="button"
                    on:click={analyzeSelectedSystems}
                    disabled={systemAnalyzing || !hasSystemSelection}
                  >
                    Analyze selected
                  </button>
                  {#if pendingSystemIds.length > 0}
                    <button
                      class="ghost-button compact-ghost"
                      type="button"
                      on:click={analyzePendingSystems}
                      disabled={systemAnalyzing}
                    >
                      Analyze pending
                    </button>
                  {/if}
                {/if}
                <div class="catalog-utility">
                  <button
                    class="text-button"
                    type="button"
                    on:click={exportSystemsCatalog}
                    disabled={systems.length === 0}
                  >
                    Export
                  </button>
                  <button class="text-button" type="button" on:click={importSystemsCatalog} disabled={importingSystems}>
                    {importingSystems ? 'Importing…' : 'Import'}
                  </button>
                </div>
              </div>
            </div>

            {#if DEMO_MODE}
              <article class="notice-banner">
                <strong>Demo mode</strong>
                <p>
                  Catalog entries are stored locally in this browser and will disappear if you clear site data. For the
                  full version with persistent storage and semantic retrieval, download or fork Koala from
                  <a href={PROJECT_GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a> and deploy it yourself.
                  This demo uses lightweight retrieval (BM25 only).
                </p>
              </article>
            {/if}

            {#if systemAnalyzing}
              <article class="loading-banner">
                <div class="typing-indicator compact-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <div>
                  <strong>Analysis running</strong>
                  <p>
                    Checking {analyzingSystemIds.length} system{analyzingSystemIds.length === 1 ? '' : 's'} with current settings.
                  </p>
                </div>
              </article>
            {/if}

            {#if analysisConfirmation}
              <article class="confirm-card">
                <strong>
                  {analysisConfirmation.duplicates.length} selected system{analysisConfirmation.duplicates.length === 1 ? '' : 's'} already have stored analysis.
                </strong>
                <p class="muted">
                  Choose whether to skip them or re-analyze everything with the current role and settings.
                </p>
                <div class="inline-actions">
                  <button class="ghost-button" type="button" on:click={confirmSkipAnalyzed}>
                    Skip analyzed
                  </button>
                  <button class="ghost-button compact-ghost" type="button" on:click={confirmReanalyzeAll}>
                    Re-analyze all
                  </button>
                  <button class="ghost-button" type="button" on:click={cancelAnalysisConfirmation}>
                    Cancel
                  </button>
                </div>
              </article>
            {/if}

            <div class="system-table-wrap" class:empty-state={visibleSystems.length === 0}>
              {#if visibleSystems.length === 0}
                <div class="catalog-empty">
                  <h3>Start your AI system catalog</h3>
                  <p class="muted">
                    Add the AI systems your organisation uses so every answer is grounded in real systems, roles, and obligations.
                  </p>
                  <button class="ghost-button" type="button" on:click={openNewSystemForm}>
                    Add your first AI system
                  </button>
                </div>
              {:else}
                <table class="system-table">
                  <thead>
                    <tr>
                      <th></th>
                      <th>Name</th>
                      <th>Catalog</th>
                      <th>Description</th>
                      <th>Type</th>
                      <th>Risk</th>
                      <th>Confidence</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each visibleSystems as system}
                      <tr class:selected-row={selectedSystemIds.includes(system.id)}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedSystemIds.includes(system.id)}
                            on:change={() => toggleSystemSelection(system.id)}
                            aria-label={`Select ${system.name}`}
                          />
                        </td>
                        <td>
                          <button class="link-button" type="button" on:click={() => useSystemInChat(system.id)}>
                            {system.name}
                          </button>
                          <small>{formatSystemTime(system.updated_at)}</small>
                        </td>
                        <td>
                          <span class="catalog-pill">{normalizeCatalog(system.catalog)}</span>
                        </td>
                        <td class="wrap-cell">{system.description}</td>
                        <td>{system.system_type}</td>
                        <td>
                          <span class:ready={Boolean(system.level_of_risk)} class="model-pill">
                            {analyzingSystemIds.includes(system.id) ? 'Analyzing…' : formatRiskLevel(system.level_of_risk)}
                          </span>
                        </td>
                        <td>{system.confidence ? `${system.confidence}%` : ':'}</td>
                        <td>
                          <div class="row-actions">
                            <button class="ghost-button compact-ghost" type="button" on:click={() => useSystemInChat(system.id)}>
                              Use in chat
                            </button>
                            <button class="ghost-button compact-ghost" type="button" on:click={() => startEditingSystem(system)}>
                              Edit
                            </button>
                            {#if !DEMO_MODE}
                              <button class="ghost-button compact-ghost" type="button" on:click={() => analyzeSingleSystem(system.id)}>
                                Analyze
                              </button>
                            {/if}
                            <button class="ghost-button compact-ghost" type="button" on:click={() => deleteSystemRecord(system.id)}>
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                      {#if system.analysis_summary || system.analysis_error}
                        <tr class="detail-row">
                          <td colspan="8">
                            {#if system.analysis_summary}
                              <p class="detail-copy">{system.analysis_summary}</p>
                            {/if}
                            {#if system.analysis_citations.length > 0}
                              <p class="detail-meta">Sources: {system.analysis_citations.join(', ')}</p>
                            {/if}
                            {#if system.analysis_error}
                              <p class="soft-error">Analysis unavailable : please retry.</p>
                            {/if}
                          </td>
                        </tr>
                      {/if}
                    {/each}
                  </tbody>
                </table>
              {/if}
            </div>
          </section>
        </div>
      {:else if centerView === 'kpis'}
        <div class="workspace-screen">
          <section class="card">
            <div class="section-head">
              <h2>KPIs</h2>
              <span>Snapshot</span>
            </div>
            <div class="kpi-grid">
              <article class="kpi-item">
                <span>Indexed records</span>
                <strong>{kpiSnapshot.indexedRecords}</strong>
              </article>
              <article class="kpi-item">
                <span>Sources</span>
                <strong>{kpiSnapshot.sourceCount}</strong>
              </article>
              <article class="kpi-item">
                <span>Languages</span>
                <strong>{kpiSnapshot.languageCount}</strong>
              </article>
              <article class="kpi-item">
                <span>Catalog entries</span>
                <strong>{kpiSnapshot.systemCount}</strong>
              </article>
              <article class="kpi-item">
                <span>Analyzed systems</span>
                <strong>{kpiSnapshot.analyzedCount}</strong>
              </article>
              <article class="kpi-item">
                <span>Avg. confidence</span>
                <strong>{kpiSnapshot.avgConfidence}%</strong>
              </article>
            </div>
          </section>
          <section class="card">
            <div class="section-head">
              <h2>Coverage</h2>
              <span>Analysis progress</span>
            </div>
            <p class="muted">
              {kpiSnapshot.analyzedCount} of {kpiSnapshot.systemCount} catalog entries analyzed.
              Last analysis: {formatSystemTime(kpiSnapshot.lastAnalysis)}
            </p>
          </section>
        </div>
      {:else if centerView === 'setup'}
        <div class="workspace-screen">
          <section class="card">
            <div class="section-head">
              <h2>Answer settings</h2>
              <span>Adjust the depth of supporting evidence</span>
            </div>

            <p class="muted">
              Koala prepares the assistant automatically. Use this control to decide how much supporting text is
              considered for each answer.
            </p>

            <label class="full-width">
              <span>Answer depth</span>
              <input class="range-input" bind:value={topK} type="range" min="3" max="7" />
              <small>{topK} supporting passages considered per answer</small>
            </label>
          </section>

          <section class="card">
            <div class="section-head">
              <h2>Use your own API key</h2>
              <span>Optional</span>
            </div>
            <p class="muted">
              Your key stays in this browser tab and is never stored by Koala. Each request uses your key to contact
              your chosen provider. You can clear it at any time.
            </p>
            {#if DEMO_MODE}
              <div class="info-card">
                <strong>Demo mode uses hosted providers only.</strong>
                <p class="muted">
                  Local assistants run only in the self-hosted version of Koala. Add your API key below to enable full
                  answers in this demo.
                </p>
              </div>
            {/if}
            <label class="toggle-row">
              <span>Use my API key</span>
              <input
                type="checkbox"
                checked={useCustomKey}
                on:change={(event) =>
                  handleCustomKeyToggle((event.currentTarget as HTMLInputElement).checked)}
              />
            </label>

            {#if useCustomKey}
              <div class="system-form-grid setup-grid">
                <label>
                  <span>Provider</span>
                  <select bind:value={provider}>
                    {#each providerOptions as option}
                      <option value={option.id} disabled={isProviderDisabled(option)}>
                        {option.label}{isProviderDisabled(option) ? ' (self-hosted only)' : ''}
                      </option>
                    {/each}
                  </select>
                  <small>For Gemini, DeepSeek, Kimi, or Meta, use a provider-prefixed model ID if available.</small>
                </label>

                <label>
                  <span>Model</span>
                  <input
                    bind:value={customModel}
                    placeholder={activeProvider?.default_model ?? 'e.g. gpt-4o-mini'}
                  />
                  <small>Leave blank to use the recommended model for the selected provider.</small>
                </label>

                {#if showApiBaseField}
                  <label>
                    <span>Base URL</span>
                    <input bind:value={apiBase} placeholder="https://api.your-provider.com/v1" />
                    <small>Only required if your provider exposes an OpenAI-compatible endpoint.</small>
                  </label>
                {/if}

                {#if providerRequiresKey}
                  <label>
                    <span>API key</span>
                    <input type="password" bind:value={apiKey} placeholder="Paste your API key" autocomplete="off" />
                    <small>We never store or log this key.</small>
                  </label>
                {:else}
                  <div class="info-card">
                    <strong>No key required for this provider.</strong>
                    <p class="muted">Koala will connect to your local assistant.</p>
                  </div>
                {/if}

                <label>
                  <span>Max output tokens</span>
                  <input type="number" min="128" max="4096" step="32" bind:value={maxOutputTokens} />
                  <small>
                    Limits response length to help control usage costs.
                    {#if estimatedInputTokens > 0}
                      Estimated input ~{estimatedInputTokens} tokens. Max total ~{estimatedTotalTokens}.
                    {:else}
                      Draft a question to see a token estimate.
                    {/if}
                    {#if estimatedTotalCost > 0}
                      Estimated max cost {formatCost(estimatedTotalCost)} (based on your rates).
                    {/if}
                    Retrieved passages add to input size.
                  </small>
                </label>

                <label>
                  <span>Input cost per 1M tokens</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    bind:value={inputCostPerMillion}
                    placeholder="e.g. 1.00"
                  />
                  <small>Use your provider pricing. Leave blank to skip cost estimates.</small>
                </label>

                <label>
                  <span>Output cost per 1M tokens</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    bind:value={outputCostPerMillion}
                    placeholder="e.g. 3.00"
                  />
                  <small>Shown in your own currency or cost unit.</small>
                </label>
              </div>

              <div class="inline-actions">
                <button class="ghost-button" type="button" on:click={() => (apiKey = '')}>
                  Clear key
                </button>
              </div>
              <div class="info-card">
                <strong>Session usage estimate</strong>
                <p class="muted">
                  Input ~{sessionInputTokens} tokens, output ~{sessionOutputTokens} tokens.
                </p>
                <p class="muted">Estimates use a simple token approximation; provider billing may differ.</p>
                {#if sessionTotalCost > 0}
                  <p class="muted">Estimated spend {formatCost(sessionTotalCost)} (based on your rates).</p>
                {/if}
                <div class="inline-actions">
                  <button class="ghost-button" type="button" on:click={resetSessionUsage}>
                    Reset session usage
                  </button>
                </div>
              </div>
              <div class="provider-hints">
                <div class="provider-hints-head">
                  <h3>Common provider model IDs</h3>
                  <span>2026 quick reference</span>
                </div>
                <p class="muted">
                  If your provider is not listed in the dropdown, select Custom API and paste the model ID from your
                  provider console. Use the base URL only if your provider exposes an OpenAI-compatible endpoint.
                </p>
                <ul>
                  {#each PROVIDER_HINTS as hint}
                    <li>
                      <strong>{hint.name}</strong>
                      <span>{hint.models}</span>
                      {#if hint.note}
                        <small>{hint.note}</small>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {:else}
              <p class="muted">
                Koala will use the default assistant for this workspace. If no model is available, answers fall back to
                sources-only with citations.
              </p>
            {/if}
          </section>
        </div>
      {:else}
        <div class="workspace-screen">
          <section class="card">
            <div class="section-head">
              <h2>Usage help</h2>
              <span>Recommended flow</span>
            </div>
            <div class="help-list">
              <p class="muted">
                🐨 Koala is an open-source AI governance assistant for teams that build AI. It helps compliance officers
                ask grounded questions about the EU AI Act and keep a clear register of AI systems.
              </p>
              <p>
                Koala is scoped to the EU AI Act (Reg. 2024/1689). If amendment proposals are indexed, they are treated as
                updates to the Act rather than separate regulations.
              </p>
              <p>
                Koala helps interpret the EU AI Act by grounding answers in the indexed legal text. The Act defines
                four primary risk levels: <strong>prohibited</strong>, <strong>high</strong>, <strong>limited</strong>,
                and <strong>minimal</strong>, plus a dedicated category for <strong>general-purpose AI</strong>.
              </p>
              <p>
                <strong>Chat</strong>: Ask questions about obligations, definitions, and deadlines with citations.
              </p>
              <p>
                <strong>Catalog</strong>: Maintain a structured register of your AI systems and store analysis results.
              </p>
              <p>
                <strong>KPIs</strong>: Monitor portfolio coverage, risk distribution, and analysis readiness at a glance.
              </p>
              <p>
                <strong>AI Setup</strong>: Adjust how much supporting evidence is considered in each answer.
              </p>
              <p>
                <strong>Help</strong>: Read the product overview, AI Act basics, and reach the team.
              </p>
              <p>
                <strong>Context</strong>: Set your role and an active AI system so answers reflect your obligations.
              </p>
              <p>
                <strong>Source filters</strong>: Limit answers to specific AI Act sources and languages.
              </p>
              <p>
                <strong>Index snapshot</strong>: A quick read on how many sources and systems are currently indexed.
              </p>
              <p>
                GitHub support: <a href={PROJECT_GITHUB_URL} target="_blank" rel="noreferrer">Project repository</a>
              </p>
            </div>
          </section>

          <section class="card">
            <div class="section-head">
              <h2>AI Act amendments</h2>
              <span>Digital Omnibus proposal (not yet adopted)</span>
            </div>
            <div class="help-list">
              <p><strong>High-risk timeline</strong>: application tied to the availability of harmonised standards, with later deadlines for Annex III and Annex I systems.</p>
              <p><strong>Centralised enforcement</strong>: AI Office supervision for AI systems in very large online platforms or search engines and for systems based on GPAI models when the same provider controls both.</p>
              <p><strong>AI literacy</strong>: obligation shifts from providers/deployers to Commission and Member States promoting AI literacy initiatives.</p>
              <p><strong>SME/SMC relief</strong>: simplified documentation and special consideration in penalties extended to small mid-caps.</p>
              <p><strong>Bias correction data</strong>: exceptional use of special categories of personal data for bias detection and correction, with safeguards.</p>
              <p><strong>Registration burden</strong>: no EU database registration when Annex III systems are concluded not high-risk due to narrow or procedural tasks.</p>
              <p><strong>Sandboxes & testing</strong>: expanded real-world testing and legal basis for an EU-level AI regulatory sandbox.</p>
              <p><strong>Generative AI marking</strong>: transitional period to comply with AI-generated content marking obligations.</p>
              <p><strong>Interplay with other laws</strong>: clarifies interaction with other EU legislation such as aviation rules and GDPR.</p>
            </div>
          </section>
        </div>
      {/if}
    </section>

    {#if showControlsPanel}
      <aside class="panel control-panel">
        <div class="control-scroll">
          <section class="card">
            <div class="section-head">
              <h2>EU AI Act</h2>
              <span>In force</span>
            </div>
            <div class="help-list">
              <p><strong>{ACT_BADGE}</strong></p>
              <p class="muted">Answers are grounded in the EU AI Act (Reg. 2024/1689).</p>
              {#if hasAmendmentSources}
                <p class="muted">
                  Amendment proposal indexed: {AMENDMENT_LABEL} · published {AMENDMENT_PUBLISHED} · updated {AMENDMENT_UPDATED}
                </p>
              {/if}
            </div>
          </section>

          <section class="card">
            <div class="section-head">
              <h2>Context</h2>
              <span>Role and system</span>
            </div>

            <label>
              <span>You are reviewing as</span>
              <select bind:value={userRole}>
                {#each ROLE_OPTIONS as option}
                  <option value={option.value}>{option.label}</option>
                {/each}
              </select>
            </label>

            {#if centerView === 'catalog'}
              <div class="catalog-summary">
                <p>
                  <strong>{visibleSystems.length}</strong> system{visibleSystems.length === 1 ? '' : 's'}{' '}
                  {resolvedCatalog === ALL_CATALOG ? 'registered' : 'in this catalog'} ·
                  <strong>{pendingSystemIds.length}</strong> pending analysis
                </p>
              </div>
            {:else}
              <label>
                <span>Active AI system</span>
                <select bind:value={activeSystemId}>
                  <option value="">None</option>
                  {#each systems as system}
                    <option value={system.id}>
                      {system.name}{hasMultipleCatalogs ? ` · ${normalizeCatalog(system.catalog)}` : ''}
                    </option>
                  {/each}
                </select>
              </label>

              {#if !activeSystem}
                <p class="muted">No AI system selected : answers will reflect general obligations.</p>
              {/if}

              {#if activeSystem}
                <article class="active-system-card">
                  <strong>{activeSystem.name}</strong>
                  <p>{activeSystem.description}</p>
                  <div class="inline-meta">
                    <span>{normalizeCatalog(activeSystem.catalog)}</span>
                    <span>{activeSystem.system_type}</span>
                    <span>{formatRiskLevel(activeSystem.level_of_risk)}</span>
                    <span>{activeSystem.confidence ? `${activeSystem.confidence}%` : 'No score'}</span>
                  </div>
                </article>
              {/if}
            {/if}

            <div class="inline-actions">
              {#if centerView !== 'catalog'}
                <button class="ghost-button" type="button" on:click={() => (centerView = 'catalog')}>
                  Open catalog
                </button>
              {/if}
              <button class="ghost-button" type="button" on:click={() => (centerView = 'setup')}>
                Answer settings
              </button>
              <button class="ghost-button" type="button" on:click={() => (centerView = 'help')}>
                Open help
              </button>
            </div>
          </section>

          {#if centerView !== 'catalog'}
            <section class="card">
              <div class="section-head">
                <h2>Source filters</h2>
                <div class="inline-actions">
                  <button class="ghost-button" type="button" on:click={resetFilters}>Reset</button>
                  <button class="ghost-button" type="button" on:click={loadAppState} disabled={refreshing}>
                    {refreshing ? 'Refreshing…' : 'Refresh'}
                  </button>
                </div>
              </div>

              {#if sources.length === 0}
                <p class="muted">
                  {#if sourceCountFromHealth > 0}
                    Indexed documents exist, but source summaries are unavailable right now. Retry the connection.
                  {:else}
                    No AI Act sources indexed yet.
                  {/if}
                </p>
              {:else}
                <div class="chip-grid">
                  {#each sources as source}
                    <button
                      type="button"
                      class:selected={selectedSources.includes(source.source)}
                      class="chip"
                      on:click={() => toggleSource(source.source)}
                    >
                      <strong>{source.source}</strong>
                      <span>{source.chunk_count} passages</span>
                    </button>
                  {/each}
                </div>
              {/if}

              {#if availableLanguages.length > 0}
                <div class="language-group">
                  {#each availableLanguages as language}
                    <button
                      type="button"
                      class:selected={selectedLanguages.includes(language)}
                      class="chip chip-small"
                      on:click={() => toggleLanguage(language)}
                    >
                      {language.toUpperCase()}
                    </button>
                  {/each}
                </div>
              {/if}
            </section>
          {/if}

          <section class="card">
            <div class="section-head">
              <h2>Index snapshot</h2>
              <span>{sourceCountFromHealth} records</span>
            </div>
            <div class="help-list">
              <p><strong>{sources.length}</strong> indexed source set{sources.length === 1 ? '' : 's'} available.</p>
              <p><strong>{systems.length}</strong> saved AI system{systems.length === 1 ? '' : 's'} in the catalog.</p>
              <p>Use Help for definitions of context, source filters, and index snapshot.</p>
            </div>
          </section>
        </div>
      </aside>
    {/if}
  </main>
{/if}

{#if openConversationMenuId}
  <div
    class="conversation-menu"
    role="menu"
    aria-label={`Conversation actions${openConversation ? ` for ${openConversation.title}` : ''}`}
    tabindex="0"
    style={conversationMenuStyle}
    bind:this={conversationMenuEl}
  >
    <button class="menu-item" type="button" on:click={() => openRenameDialog(openConversationMenuId)}>
      Rename
    </button>
    <button class="menu-item menu-danger" type="button" on:click={() => deleteConversation(openConversationMenuId)}>
      Delete
    </button>
  </div>
{/if}

{#if showSystemForm}
  <button class="modal-backdrop" type="button" aria-label="Close" tabindex="-1" on:click={clearSystemForm}></button>
  <div class="modal-card catalog-modal" role="dialog" aria-modal="true" tabindex="-1" bind:this={systemFormEl}>
    <div class="modal-head catalog-modal-head">
      <div>
        <h3>{editingSystemId ? 'Edit system' : 'Add system'}</h3>
        <p class="muted">Describe the AI system and how it is used.</p>
      </div>
      <button class="text-button" type="button" on:click={clearSystemForm}>Close</button>
    </div>

    <div class="system-form-grid">
      <label>
        <span>Catalog</span>
        <input bind:value={systemCatalog} list="catalog-options" placeholder={DEFAULT_CATALOG} />
      </label>

      <label>
        <span>Name</span>
        <input bind:value={systemName} placeholder="e.g. Office Entry Face Scanner" />
      </label>

      <label>
        <span>Type</span>
        <input bind:value={systemType} placeholder="e.g. biometric identification" />
      </label>

      <label class="full-width">
        <span>Description</span>
        <textarea
          bind:value={systemDescription}
          rows="4"
          placeholder="Describe the AI system, who uses it, and what decision or task it performs."
        ></textarea>
      </label>
    </div>

    <datalist id="catalog-options">
      {#each catalogOptions as catalog}
        <option value={catalog}></option>
      {/each}
    </datalist>

    <div class="inline-actions">
      <button class="submit-button compact-button" type="button" on:click={submitSystem} disabled={savingSystem}>
        {savingSystem ? 'Saving…' : editingSystemId ? 'Update system' : 'Add system'}
      </button>
      <button class="text-button" type="button" on:click={clearSystemForm}>
        Cancel
      </button>
    </div>
  </div>
{/if}

{#if renameDialogOpen}
  <button class="modal-backdrop" type="button" aria-label="Close" tabindex="-1" on:click={closeRenameDialog}></button>
  <div class="modal-card" role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-head">
      <h3>Rename conversation</h3>
      <button class="ghost-button compact-ghost" type="button" on:click={closeRenameDialog}>Close</button>
    </div>
    <label class="modal-field">
      <span>Title</span>
      <input
        bind:value={renameDraft}
        bind:this={renameInput}
        placeholder="Conversation title"
        on:keydown={(event) => event.key === 'Enter' && submitRenameDialog()}
      />
    </label>
    <div class="modal-actions">
      <button class="ghost-button" type="button" on:click={closeRenameDialog}>Cancel</button>
      <button class="submit-button compact-button" type="button" on:click={submitRenameDialog}>Save</button>
    </div>
  </div>
{/if}

<style>
  :global(body) {
    margin: 0;
    min-height: 100vh;
    overflow: hidden;
    font-family: "Inter", "Helvetica Neue", sans-serif;
    background:
      radial-gradient(circle at top left, rgba(128, 86, 58, 0.25), transparent 34%),
      radial-gradient(circle at bottom right, rgba(100, 120, 92, 0.22), transparent 30%),
      #efe9e0;
    color: #2b1d15;
  }

  :global(*) {
    box-sizing: border-box;
  }

  .shell {
    --ink: #2b1d15;
    --muted: #6e5d53;
    --accent: #8b5a3c;
    --accent-soft: rgba(139, 90, 60, 0.14);
    --panel: rgba(248, 242, 234, 0.9);
    --line: rgba(55, 37, 27, 0.12);
    --shadow: 0 24px 70px rgba(44, 29, 19, 0.16);
    display: grid;
    grid-template-columns: minmax(240px, 280px) minmax(0, 1fr) minmax(320px, 380px);
    gap: 18px;
    height: 100dvh;
    padding: 18px;
    overflow: hidden;
    position: relative;
  }

  .shell.history-hidden {
    grid-template-columns: minmax(0, 1fr) minmax(320px, 380px);
  }

  .shell.controls-hidden {
    grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  }

  .shell.history-hidden.controls-hidden {
    grid-template-columns: minmax(0, 1fr);
  }

  .loading-shell {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .loading-card,
  .panel {
    position: relative;
    z-index: 1;
    backdrop-filter: blur(20px);
    background: var(--panel);
    border: 1px solid var(--line);
    box-shadow: var(--shadow);
    border-radius: 28px;
  }

  .loading-card {
    width: min(560px, 100%);
    padding: 40px;
  }

  .panel {
    min-height: 0;
    height: 100%;
    overflow: hidden;
  }

  .background-orb {
    position: absolute;
    border-radius: 999px;
    filter: blur(12px);
    opacity: 0.7;
    animation: drift 12s ease-in-out infinite;
  }

  .orb-a {
    top: 8%;
    right: 18%;
    width: 220px;
    height: 220px;
    background: rgba(138, 92, 64, 0.25);
  }

  .orb-b {
    bottom: 12%;
    left: 34%;
    width: 260px;
    height: 260px;
    background: rgba(108, 126, 96, 0.22);
    animation-delay: -4s;
  }

  .history-panel,
  .control-panel,
  .chat-panel {
    padding: 20px;
  }

  .history-panel,
  .chat-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .control-panel {
    padding-right: 12px;
  }

  .control-scroll {
    height: 100%;
    overflow: auto;
    display: grid;
    gap: 16px;
    padding-right: 8px;
  }

  .workspace-bar,
  .history-head,
  .section-head,
  .message-head,
  .composer-actions,
  .confidence-row,
  .citation-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .message-title {
    display: inline-flex;
    align-items: baseline;
    gap: 8px;
  }

  .copy-button {
    padding: 4px 10px;
    font-size: 0.78rem;
  }

  .copy-button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .panel-toggle-row,
  .inline-actions,
  .row-actions,
  .inline-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .panel-toggle-row {
    margin-left: auto;
    justify-content: flex-end;
  }

  .health-indicator {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    border: 1px solid rgba(139, 90, 60, 0.2);
    background: rgba(255, 255, 255, 0.6);
  }

  .health-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(139, 90, 60, 0.4);
  }

  .health-dot.healthy {
    background: #6a7b5f;
  }

  .history-head h2,
  .workspace-title h2,
  .empty-state h3,
  .loading-card h1 {
    margin: 0;
    font-family: "Satoshi", "Inter", "Helvetica Neue", sans-serif;
    font-weight: 600;
    line-height: 1.05;
    letter-spacing: -0.03em;
  }

  .history-head h2,
  .workspace-title h2,
  .loading-card h1 {
    font-size: clamp(1.6rem, 3vw, 2.4rem);
  }

  .muted,
  .warning-text,
  .detail-meta,
  .conversation-select p {
    color: var(--muted);
  }

  .eyebrow {
    margin: 0 0 10px;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.74rem;
    color: var(--accent);
  }

  .conversation-list,
  .message-list {
    min-height: 0;
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
  }

  .message-list {
    padding-right: 4px;
  }

  .workspace-title,
  .workspace-controls,
  .status-inline,
  .conversation-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .workspace-title,
  .workspace-controls {
    align-items: flex-start;
  }

  .workspace-controls {
    justify-content: flex-start;
    gap: 16px;
    flex: 1;
  }

  .workspace-bar {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }

  .view-tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex: 1;
  }

  .ghost-button.active-tab {
    background: rgba(139, 90, 60, 0.18);
    color: #6f4228;
  }

  .workspace-screen {
    min-height: 0;
    flex: 1;
    overflow: auto;
    display: grid;
    gap: 16px;
    padding-right: 4px;
  }

  .catalog-screen {
    display: flex;
    flex-direction: column;
  }

  .catalog-entries {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .catalog-toolbar {
    align-items: flex-end;
    justify-content: flex-end;
    gap: 10px;
    flex-wrap: wrap;
  }

  .catalog-utility {
    display: inline-flex;
    gap: 8px;
    align-items: center;
    margin-left: auto;
  }

  .catalog-toolbar .submit-button {
    padding: 10px 16px;
    min-width: auto;
  }

  .catalog-toolbar .ghost-button,
  .catalog-toolbar .compact-ghost {
    padding: 6px 10px;
    font-size: 0.82rem;
  }

  .catalog-toolbar .select-field {
    min-width: 160px;
  }

  .row-actions .ghost-button {
    padding: 6px 10px;
    font-size: 0.78rem;
  }

  .text-button {
    border: 0;
    background: transparent;
    padding: 0;
    color: #6f4228;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .text-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .section-head-split {
    align-items: flex-start;
    gap: 16px;
  }

  .select-field {
    display: grid;
    gap: 4px;
    font-size: 0.78rem;
    color: var(--muted);
  }

  .select-field span {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.66rem;
  }

  .conversation-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 18px;
    border: 1px solid rgba(55, 37, 27, 0.08);
    background: rgba(43, 29, 21, 0.04);
    overflow: visible;
  }

  .conversation-card.selected {
    background: rgba(139, 90, 60, 0.16);
    border-color: rgba(139, 90, 60, 0.34);
  }

  .conversation-select {
    display: grid;
    gap: 6px;
    text-align: left;
    background: transparent;
    border: 0;
    padding: 0;
    cursor: pointer;
    color: inherit;
    min-width: 0;
    width: 100%;
  }

  .conversation-heading {
    min-width: 0;
    width: 100%;
    align-items: baseline;
    gap: 8px;
  }

  .conversation-heading strong {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }


  .conversation-actions {
    position: relative;
    display: flex;
    align-items: flex-start;
  }

  .menu-button {
    border: 0;
    padding: 6px 10px;
    border-radius: 10px;
    background: rgba(139, 90, 60, 0.12);
    color: #6f4228;
    font-size: 1rem;
    line-height: 1;
    cursor: pointer;
  }

  .menu-button:hover {
    background: rgba(139, 90, 60, 0.2);
  }

  .conversation-menu {
    position: fixed;
    min-width: 168px;
    padding: 8px;
    border-radius: 14px;
    background: rgba(34, 24, 18, 0.92);
    color: #f7efe6;
    box-shadow: 0 18px 40px rgba(24, 16, 10, 0.35);
    display: grid;
    gap: 6px;
    z-index: 24;
    transform-origin: bottom right;
  }

  .menu-item {
    border: 0;
    background: transparent;
    color: inherit;
    text-align: left;
    padding: 6px 8px;
    border-radius: 10px;
    cursor: pointer;
    font-size: 0.88rem;
  }

  .menu-item:hover {
    background: rgba(255, 255, 255, 0.08);
  }

  .menu-danger {
    color: #f6b3a7;
  }

  button:focus-visible,
  select:focus-visible,
  input:focus-visible,
  textarea:focus-visible {
    outline: 2px solid rgba(139, 90, 60, 0.55);
    outline-offset: 2px;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(31, 23, 16, 0.4);
    backdrop-filter: blur(3px);
    z-index: 30;
    border: 0;
    padding: 0;
    margin: 0;
    cursor: pointer;
  }

  .modal-card {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(420px, 92vw);
    padding: 18px;
    border-radius: 20px;
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: var(--shadow);
    display: grid;
    gap: 14px;
    z-index: 31;
  }

  .catalog-modal {
    width: min(520px, 94vw);
    max-height: 80vh;
    overflow: auto;
  }

  .catalog-modal-head {
    align-items: flex-start;
  }

  .catalog-modal-head .muted {
    margin: 4px 0 0;
  }

  .catalog-summary {
    padding: 10px 12px;
    border-radius: 14px;
    background: rgba(139, 90, 60, 0.08);
    color: #6f4228;
  }

  .catalog-summary p {
    margin: 0;
  }

  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .modal-head h3 {
    margin: 0;
    font-family: "Satoshi", "Inter", "Helvetica Neue", sans-serif;
  }

  .modal-field {
    display: grid;
    gap: 8px;
  }

  .modal-card input {
    background: rgba(255, 255, 255, 0.9);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .conversation-preview {
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 0.82rem;
  }

  .ghost-button,
  .submit-button,
  .link-button {
    cursor: pointer;
    border: 0;
    font: inherit;
  }

  .ghost-button {
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(31, 31, 27, 0.06);
  }

  .panel-toggle-button {
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(139, 90, 60, 0.14);
    color: #6f4228;
    border: 1px solid rgba(139, 90, 60, 0.22);
    font-size: 0.82rem;
  }

  .panel-toggle-button:hover {
    background: rgba(139, 90, 60, 0.2);
  }

  .compact-ghost {
    padding: 6px 10px;
  }

  .link-button {
    background: transparent;
    color: var(--accent);
    padding: 0;
    text-align: left;
  }

  .version-pill,
  .confidence-pill,
  .model-pill {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(31, 31, 27, 0.06);
    font-size: 0.78rem;
  }

  .status-message-pill,
  .act-badge,
  .amendment-pill {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.78rem;
  }

  .status-message-pill,
  .act-badge {
    background: rgba(139, 90, 60, 0.16);
    color: #6f4228;
  }

  .amendment-pill {
    background: rgba(106, 123, 95, 0.18);
    color: #516248;
  }

  .status-pill-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 6px 0 0;
    flex-wrap: wrap;
  }

  .model-pill.ready {
    background: rgba(106, 123, 95, 0.2);
    color: #516248;
  }

  .confidence-pill.low {
    background: rgba(139, 90, 60, 0.18);
    color: #6f4228;
  }

  .card,
  .suggestion-card,
  .active-system-card,
  .confirm-card {
    display: grid;
    gap: 14px;
    padding: 16px;
    border-radius: 22px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.45);
  }

  .suggestion-card {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
  }

  .active-system-card p {
    margin: 0;
    line-height: 1.5;
  }

  label {
    display: grid;
    gap: 8px;
    font-size: 0.94rem;
  }

  input,
  select,
  textarea,
  button {
    font: inherit;
  }

  input,
  select,
  textarea {
    width: 100%;
    border: 1px solid rgba(31, 31, 27, 0.12);
    border-radius: 16px;
    padding: 12px 14px;
    background: rgba(255, 255, 255, 0.8);
    color: var(--ink);
  }

  textarea {
    resize: vertical;
    min-height: 110px;
  }

  .range-input {
    accent-color: var(--accent);
    padding: 0;
    border: none;
    height: 18px;
    background: transparent;
  }

  .range-input::-webkit-slider-runnable-track {
    height: 6px;
    border-radius: 999px;
    background: rgba(139, 90, 60, 0.28);
  }

  .range-input::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    background: #8b5a3c;
    border: 2px solid rgba(248, 242, 234, 0.95);
    margin-top: -6px;
    box-shadow: 0 2px 6px rgba(44, 29, 19, 0.2);
  }

  .range-input::-moz-range-track {
    height: 6px;
    border-radius: 999px;
    background: rgba(139, 90, 60, 0.28);
  }

  .range-input::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 999px;
    background: #8b5a3c;
    border: 2px solid rgba(248, 242, 234, 0.95);
    box-shadow: 0 2px 6px rgba(44, 29, 19, 0.2);
  }

  small {
    color: var(--muted);
  }

  .chip-grid,
  .language-group,
  .kpi-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .chip {
    display: grid;
    gap: 4px;
    min-width: 120px;
    padding: 12px 14px;
    text-align: left;
    border-radius: 18px;
    background: rgba(31, 31, 27, 0.06);
    color: var(--ink);
    transition: transform 180ms ease, background 180ms ease;
  }

  .suggested-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .suggested-chip {
    text-align: left;
    padding: 10px 14px;
    border-radius: 999px;
    border: 1px solid rgba(139, 90, 60, 0.2);
    background: rgba(255, 255, 255, 0.7);
    color: var(--ink);
    line-height: 1.4;
    transition: transform 180ms ease, background 180ms ease;
  }

  .suggested-chip:hover {
    background: rgba(139, 90, 60, 0.12);
    transform: translateY(-1px);
  }

  .chip,
  .conversation-card,
  .submit-button,
  .ghost-button {
    transition: transform 180ms ease, background 180ms ease;
  }

  .chip:hover,
  .submit-button:hover,
  .ghost-button:hover,
  .conversation-card:hover {
    transform: translateY(-1px);
  }

  .chip.selected {
    background: var(--accent-soft);
    outline: 1px solid rgba(139, 90, 60, 0.32);
  }

  .chip-small {
    min-width: auto;
    padding: 10px 12px;
  }

  .kpi-item {
    display: grid;
    gap: 6px;
    min-width: 160px;
    padding: 14px 16px;
    border-radius: 18px;
    background: rgba(139, 90, 60, 0.1);
  }

  .kpi-item span {
    color: var(--muted);
    font-size: 0.85rem;
  }

  .empty-state,
  .message-card,
  .composer {
    border-radius: 24px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.55);
  }

  .empty-state,
  .message-card {
    padding: 18px;
  }

  .message-card.user {
    align-self: flex-end;
    width: min(72%, 760px);
    background: rgba(139, 90, 60, 0.14);
  }

  .message-card.assistant {
    width: min(100%, 920px);
  }

  .message-card.pending {
    border-style: dashed;
  }

  .message-head span {
    font-weight: 600;
  }

  .markdown-body :global(p) {
    margin: 0 0 0.9rem;
    line-height: 1.6;
  }

  .markdown-body :global(p:last-child) {
    margin-bottom: 0;
  }

  .markdown-body :global(ul),
  .markdown-body :global(ol) {
    margin: 0 0 0.9rem 1.2rem;
    padding: 0;
    line-height: 1.6;
  }

  .markdown-body :global(code) {
    padding: 0.1rem 0.35rem;
    border-radius: 8px;
    background: rgba(31, 31, 27, 0.08);
    font-size: 0.92em;
  }

  .markdown-body :global(a) {
    color: var(--accent);
  }

  .typing-indicator {
    display: inline-flex;
    gap: 6px;
    margin-bottom: 12px;
  }

  .typing-indicator span {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: rgba(139, 90, 60, 0.55);
    animation: pulse 1.2s infinite ease-in-out;
  }

  .typing-indicator span:nth-child(2) {
    animation-delay: 0.15s;
  }

  .typing-indicator span:nth-child(3) {
    animation-delay: 0.3s;
  }

  .citation-list {
    display: grid;
    gap: 10px;
    margin-top: 14px;
  }

  .citation-card {
    padding: 14px;
    border-radius: 18px;
    background: rgba(31, 31, 27, 0.04);
  }

  .citation-card p {
    margin: 10px 0 0;
    color: var(--muted);
    line-height: 1.5;
  }

  .composer {
    display: grid;
    gap: 14px;
    padding: 18px;
  }

  .composer-field,
  .composer-meta {
    display: grid;
    gap: 10px;
  }

  .preparing-label {
    font-size: 0.85rem;
    color: var(--muted);
  }

  .submit-button {
    padding: 12px 18px;
    border-radius: 999px;
    background: linear-gradient(135deg, #8b5a3c, #5f3b27);
    color: white;
    min-width: 168px;
  }

  .submit-button.compact-button {
    min-width: auto;
  }

  .submit-button:disabled {
    opacity: 0.72;
    cursor: wait;
  }

  .soft-error {
    margin: 0;
    padding: 10px 12px;
    border-radius: 16px;
    background: rgba(139, 90, 60, 0.16);
    color: #6f4228;
  }

  .notice-banner {
    margin: 0;
    padding: 10px 12px;
    border-radius: 16px;
    background: rgba(106, 123, 95, 0.18);
    color: #516248;
  }

  .notice-banner p {
    margin: 6px 0 0;
    color: inherit;
  }

  .notice-banner a {
    color: #4f5d46;
  }

  .system-form-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .setup-grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .setup-grid small {
    display: block;
    color: var(--muted);
  }

  .info-card {
    padding: 12px;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: rgba(139, 90, 60, 0.08);
    grid-column: 1 / -1;
  }

  .info-card p {
    margin: 6px 0 0;
  }

  .provider-hints {
    padding: 14px;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.45);
    display: grid;
    gap: 10px;
  }

  .provider-hints-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }

  .provider-hints h3 {
    margin: 0;
    font-size: 1rem;
    font-family: "Satoshi", "Inter", "Helvetica Neue", sans-serif;
  }

  .provider-hints ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }

  .provider-hints li {
    display: grid;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 12px;
    background: rgba(43, 29, 21, 0.04);
    border: 1px solid rgba(55, 37, 27, 0.08);
  }

  .provider-hints li span {
    color: var(--muted);
    font-size: 0.86rem;
  }

  .provider-hints li small {
    color: var(--muted);
    font-size: 0.78rem;
  }

  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 0;
  }

  .toggle-row input[type='checkbox'] {
    width: 18px;
    height: 18px;
    accent-color: #8b5a3c;
  }

  .catalog-modal .system-form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .full-width {
    grid-column: 1 / -1;
  }

  .system-table-wrap {
    flex: 1;
    min-height: 0;
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.55);
  }

  .system-table-wrap.empty-state {
    display: grid;
    place-items: center;
    padding: 36px;
    overflow: hidden;
  }

  .catalog-empty {
    max-width: 360px;
    text-align: center;
    display: grid;
    gap: 10px;
  }

  .catalog-empty h3 {
    margin: 0;
    font-size: 1.2rem;
  }

  .catalog-empty .ghost-button {
    justify-self: center;
  }

  .system-table {
    width: 100%;
    border-collapse: collapse;
    min-width: 980px;
  }

  .system-table th,
  .system-table td {
    padding: 12px;
    border-bottom: 1px solid rgba(31, 31, 27, 0.08);
    text-align: left;
    vertical-align: top;
  }

  .selected-row {
    background: rgba(184, 78, 46, 0.07);
  }

  .catalog-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(139, 90, 60, 0.12);
    color: #6f4228;
    font-size: 0.72rem;
    white-space: nowrap;
  }

  .detail-row td {
    background: rgba(31, 31, 27, 0.03);
  }

  .detail-copy {
    margin: 0 0 0.5rem;
    line-height: 1.55;
  }

  .help-list {
    display: grid;
    gap: 10px;
  }

  .help-list p {
    margin: 0;
    line-height: 1.55;
  }

  .wrap-cell {
    max-width: 280px;
    white-space: normal;
    line-height: 1.5;
  }

  @keyframes drift {
    0%,
    100% {
      transform: translate3d(0, 0, 0) scale(1);
    }
    50% {
      transform: translate3d(8px, -18px, 0) scale(1.06);
    }
  }

  @keyframes pulse {
    0%,
    80%,
    100% {
      opacity: 0.35;
      transform: translateY(0);
    }
    40% {
      opacity: 1;
      transform: translateY(-3px);
    }
  }

  @media (max-width: 1220px) {
    .shell,
    .shell.history-hidden,
    .shell.controls-hidden {
      grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
    }

    .control-panel {
      grid-column: 1 / -1;
      max-height: 34vh;
    }

    .shell.controls-hidden {
      grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
    }
  }

  @media (max-width: 980px) {
    .shell,
    .shell.history-hidden,
    .shell.controls-hidden,
    .shell.history-hidden.controls-hidden {
      grid-template-columns: 1fr;
      grid-auto-rows: min-content;
    }

    .history-panel,
    .control-panel {
      max-height: 28vh;
    }

    .message-card.user {
      width: 100%;
    }
  }

  @media (max-width: 640px) {
    .shell {
      padding: 12px;
      gap: 12px;
    }

    .history-panel,
    .control-panel,
    .chat-panel {
      padding: 16px;
    }

    .workspace-bar,
    .workspace-title,
    .workspace-controls,
    .status-inline,
    .composer-actions,
    .history-head,
    .suggestion-card {
      flex-direction: column;
      align-items: stretch;
    }

    .system-form-grid {
      grid-template-columns: 1fr;
    }

    .full-width {
      grid-column: auto;
    }

    .submit-button {
      width: 100%;
    }

    .conversation-card {
      grid-template-columns: 1fr;
    }

    .view-tabs {
      width: 100%;
    }
  }
</style>
