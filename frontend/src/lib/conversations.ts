import type { ChatMessage, Conversation } from '$lib/types';

const CONVERSATIONS_KEY = 'ai-compliance.conversations.v1';
const ACTIVE_CONVERSATION_KEY = 'ai-compliance.activeConversation.v1';

export function createConversation(seedTitle = 'New conversation'): Conversation {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: seedTitle,
    createdAt: now,
    updatedAt: now,
    messages: []
  };
}

export function buildConversationTitle(question: string): string {
  const collapsed = question.replace(/\s+/g, ' ').trim();
  return collapsed.length > 56 ? `${collapsed.slice(0, 56)}…` : collapsed;
}

export function loadConversations(): Conversation[] {
  if (typeof localStorage === 'undefined') {
    return [];
  }
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isConversation);
  } catch {
    return [];
  }
}

export function saveConversations(conversations: Conversation[]): void {
  if (typeof localStorage === 'undefined') {
    return;
  }
  localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations));
}

export function loadActiveConversationId(): string | null {
  if (typeof localStorage === 'undefined') {
    return null;
  }
  return localStorage.getItem(ACTIVE_CONVERSATION_KEY);
}

export function saveActiveConversationId(conversationId: string | null): void {
  if (typeof localStorage === 'undefined') {
    return;
  }
  if (conversationId) {
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId);
  } else {
    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  }
}

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.title === 'string' &&
    typeof candidate.createdAt === 'string' &&
    typeof candidate.updatedAt === 'string' &&
    Array.isArray(candidate.messages) &&
    candidate.messages.every(isChatMessage)
  );
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.id === 'string' &&
    (candidate.role === 'user' || candidate.role === 'assistant') &&
    typeof candidate.content === 'string'
  );
}
