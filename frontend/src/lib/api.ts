import type {
  AISystem,
  AISystemImportResponse,
  AISystemAnalysisResponse,
  AISystemUpsertResponse,
  AppConfig,
  HealthResponse,
  OllamaModelsResponse,
  OllamaPullResponse,
  QueryRequest,
  QueryResponse,
  SourceSummary
} from '$lib/types';

const API_BASE_URL = (import.meta.env.PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers || {})
      },
      ...init
    });
  } catch (error) {
    const hint =
      `Could not reach the backend at ${API_BASE_URL}. ` +
      'Confirm the FastAPI server is running and PUBLIC_API_BASE_URL is set correctly.';
    throw new Error(hint);
  }

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message =
      typeof payload === 'string'
        ? payload
        : (payload.detail as string | undefined) || 'Request failed.';
    throw new Error(message);
  }

  return payload as T;
}

export function fetchConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config');
}

export function fetchSources(): Promise<SourceSummary[]> {
  return request<SourceSummary[]>('/sources');
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

export function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>('/query', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function fetchOllamaModels(baseUrl?: string): Promise<OllamaModelsResponse> {
  const query = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : '';
  return request<OllamaModelsResponse>(`/models/ollama${query}`);
}

export function pullOllamaModel(model: string, baseUrl?: string): Promise<OllamaPullResponse> {
  return request<OllamaPullResponse>('/models/ollama/pull', {
    method: 'POST',
    body: JSON.stringify({
      model,
      base_url: baseUrl
    })
  });
}

export function fetchSystems(): Promise<AISystem[]> {
  return request<AISystem[]>('/systems');
}

export function exportSystems(): Promise<AISystem[]> {
  return request<AISystem[]>('/systems/export');
}

export function importSystems(payload: {
  systems: AISystem[];
  mode?: 'merge' | 'replace';
}): Promise<AISystemImportResponse> {
  return request<AISystemImportResponse>('/systems/import', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function upsertSystem(payload: {
  name: string;
  description: string;
  system_type: string;
  catalog?: string;
}): Promise<AISystemUpsertResponse> {
  return request<AISystemUpsertResponse>('/systems', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function updateSystem(
  systemId: string,
  payload: {
    name: string;
    description: string;
    system_type: string;
    catalog?: string;
  }
): Promise<AISystem> {
  return request<AISystem>(`/systems/${encodeURIComponent(systemId)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  });
}

export function deleteSystem(systemId: string): Promise<{ status: string; deleted_system_id: string }> {
  return request<{ status: string; deleted_system_id: string }>(`/systems/${encodeURIComponent(systemId)}`, {
    method: 'DELETE'
  });
}

export function analyzeSystems(payload: {
  system_ids: string[];
  force?: boolean;
  user_role?: string;
  model?: QueryRequest['model'];
}): Promise<AISystemAnalysisResponse> {
  return request<AISystemAnalysisResponse>('/systems/analyze', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}
