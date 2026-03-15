import { browser } from '$app/environment';
import type { AISystem } from '$lib/types';

const DEMO_FLAG = import.meta.env.PUBLIC_DEMO_MODE;
const DEMO_MODE = DEMO_FLAG === 'true' || DEMO_FLAG === '1';
const DEMO_SYSTEMS_KEY = 'koala_demo_systems';

export function isDemoMode(): boolean {
  return DEMO_MODE;
}

export function loadDemoSystems(): AISystem[] {
  if (!browser) {
    return [];
  }
  try {
    const stored = localStorage.getItem(DEMO_SYSTEMS_KEY);
    if (!stored) {
      return [];
    }
    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map((system) => ({
      analysis_citations: [],
      analysis_status: 'new',
      ...system
    })) as AISystem[];
  } catch (error) {
    return [];
  }
}

export function saveDemoSystems(nextSystems: AISystem[]) {
  if (!browser) {
    return;
  }
  localStorage.setItem(DEMO_SYSTEMS_KEY, JSON.stringify(nextSystems));
}

function createId(): string {
  if (browser && typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `demo-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function buildDemoSystem(payload: {
  name: string;
  description: string;
  system_type: string;
  catalog?: string;
}): AISystem {
  const now = new Date().toISOString();
  return {
    id: createId(),
    name: payload.name,
    description: payload.description,
    system_type: payload.system_type,
    catalog: payload.catalog ?? 'Default',
    level_of_risk: null,
    confidence: null,
    analysis_summary: null,
    analysis_status: 'new',
    analysis_error: null,
    analysis_citations: [],
    last_user_role: null,
    last_provider: null,
    last_model: null,
    last_analyzed_at: null,
    created_at: now,
    updated_at: now
  };
}

export function updateDemoSystem(
  system: AISystem,
  payload: {
    name: string;
    description: string;
    system_type: string;
    catalog?: string;
  }
): AISystem {
  const now = new Date().toISOString();
  const shouldReset =
    system.description !== payload.description || system.system_type !== payload.system_type;
  return {
    ...system,
    name: payload.name,
    description: payload.description,
    system_type: payload.system_type,
    catalog: payload.catalog ?? system.catalog ?? 'Default',
    updated_at: now,
    ...(shouldReset
      ? {
          level_of_risk: null,
          confidence: null,
          analysis_summary: null,
          analysis_status: 'new',
          analysis_error: null,
          analysis_citations: [],
          last_analyzed_at: null
        }
      : {})
  };
}
