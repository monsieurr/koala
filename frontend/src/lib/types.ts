export interface Citation {
  index: number;
  id: string;
  label: string;
  source: string;
  language: string;
  chunk_type: string;
  title: string | null;
  article_number: string | null;
  recital_number: string | null;
  annex_number: string | null;
  page_start: number;
  page_end: number;
  excerpt: string;
}

export interface QueryResponse {
  question: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  low_confidence: boolean;
  warning: string | null;
  answer_mode: string;
  retrieval_debug: Record<string, unknown>;
}

export interface QueryRequest {
  question: string;
  sources?: string[];
  languages?: string[];
  top_k?: number;
  user_role?: UserRole;
  system?: SystemContext;
  model?: {
    provider?: string;
    model?: string;
    api_base?: string;
    api_key?: string;
    temperature?: number;
    max_tokens?: number;
    timeout_seconds?: number;
  };
}

export interface SourceSummary {
  id: string;
  source: string;
  chunk_count: number;
  languages: string[];
  articles: number;
  recitals: number;
  annexes: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  dependencies: Record<string, boolean>;
  store: Record<string, unknown>;
}

export interface ProviderOption {
  id: string;
  label: string;
  requires_api_key: boolean;
  default_model: string;
  default_base_url: string | null;
}

export interface HardwareRecommendation {
  hardware: string;
  recommendation: string;
}

export interface AppConfig {
  app_name: string;
  app_version: string;
  default_top_k: number;
  default_model: string;
  default_provider: string;
  default_api_base: string | null;
  provider_options: ProviderOption[];
  hardware_recommendations: HardwareRecommendation[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  confidence?: number;
  lowConfidence?: boolean;
  warning?: string | null;
  answerMode?: string;
  pending?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export type UserRole =
  | 'provider'
  | 'deployer'
  | 'distributor'
  | 'importer'
  | 'authorized_representative'
  | 'affected_person'
  | 'user'
  | 'other';

export interface SystemContext {
  id?: string;
  name: string;
  description: string;
  system_type: string;
  catalog?: string | null;
  level_of_risk?: string | null;
  confidence?: number | null;
}

export interface AISystem extends SystemContext {
  id: string;
  analysis_summary?: string | null;
  analysis_status: 'new' | 'analyzed' | 'error';
  analysis_error?: string | null;
  analysis_citations: string[];
  last_user_role?: UserRole | null;
  last_provider?: string | null;
  last_model?: string | null;
  last_analyzed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OllamaModel {
  name: string;
  size: number;
  modified_at: string | null;
}

export interface OllamaModelsResponse {
  status: string;
  base_url: string;
  models: OllamaModel[];
}

export interface OllamaPullResponse {
  status: string;
  base_url: string;
  model: string;
}

export interface AISystemUpsertResponse {
  status: string;
  created: boolean;
  system: AISystem;
}

export interface AISystemAnalysisFailure {
  system_id: string;
  message: string;
}

export interface AISystemAnalysisResponse {
  status: string;
  analyzed: AISystem[];
  skipped: AISystem[];
  failures: AISystemAnalysisFailure[];
}

export interface AISystemImportResponse {
  status: string;
  mode: 'merge' | 'replace';
  total: number;
  imported: number;
  updated: number;
}
