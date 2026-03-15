import { buildConversationTitle } from '$lib/conversations';
import type { AISystem } from '$lib/types';

export interface SuggestedSystemDraft {
  name: string;
  description: string;
  system_type: string;
}

const TYPE_HINTS: Array<{ label: string; pattern: RegExp }> = [
  { label: 'biometric identification', pattern: /\b(face|facial|biometric|fingerprint|iris)\b/i },
  { label: 'recruitment screening', pattern: /\b(hiring|recruitment|candidate|cv|resume)\b/i },
  { label: 'employee monitoring', pattern: /\b(employee|workplace|attendance|monitoring)\b/i },
  { label: 'customer support assistant', pattern: /\b(chatbot|assistant|copilot|support bot)\b/i },
  { label: 'content moderation', pattern: /\b(moderation|flagging|unsafe content)\b/i },
  { label: 'risk scoring', pattern: /\b(scoring|ranking|credit|eligibility)\b/i }
];

export function detectSuggestedSystem(question: string, systems: AISystem[]): SuggestedSystemDraft | null {
  const normalized = question.replace(/\s+/g, ' ').trim();
  if (normalized.length < 28) {
    return null;
  }
  if (!/\b(system|tool|model|assistant|platform|scanner|classifier|service|application)\b/i.test(normalized)) {
    return null;
  }

  const description = normalized;
  const name =
    extractQuotedName(normalized) ||
    extractNamedSystem(normalized) ||
    buildConversationTitle(normalized.replace(/^[Qq]uestion:\s*/, '')) ||
    'Potential AI system';
  const system_type = guessSystemType(normalized);
  const existing = systems.some((system) => normalize(system.name) === normalize(name));
  if (existing) {
    return null;
  }
  return { name, description, system_type };
}

function guessSystemType(question: string): string {
  for (const hint of TYPE_HINTS) {
    if (hint.pattern.test(question)) {
      return hint.label;
    }
  }
  return 'general AI system';
}

function extractQuotedName(question: string): string | null {
  const match = question.match(/["“]([^"”]{3,72})["”]/);
  return match ? match[1].trim() : null;
}

function extractNamedSystem(question: string): string | null {
  const match = question.match(/\b(?:called|named)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,5})/);
  return match ? match[1].trim() : null;
}

function normalize(value: string): string {
  return value.trim().toLowerCase();
}
