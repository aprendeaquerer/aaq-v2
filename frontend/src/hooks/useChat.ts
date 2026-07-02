'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import * as api from '@/lib/api';
import { API_URL } from '@/lib/constants';
import type { BotDebugTrace, ChatMessage, ChatResponse, DebugSession, StoredChatMessage } from '@/lib/types';

let messageIdCounter = 0;
function generateId(): string {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

const DEBUG_STORAGE_KEY = 'aaq_debug_sessions_v1';
const MAX_DEBUG_SESSIONS = 20;

function limitDebugSessions(sessions: DebugSession[]): DebugSession[] {
  return sessions.slice(-MAX_DEBUG_SESSIONS);
}

function loadStoredDebugSessions(): DebugSession[] {
  if (typeof window === 'undefined') return [];

  try {
    const stored = window.localStorage.getItem(DEBUG_STORAGE_KEY);
    if (!stored) return [];
    const rows = JSON.parse(stored);
    if (!Array.isArray(rows)) return [];

    return limitDebugSessions(
      rows
        .filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object')
        .map((row) => ({
          id: typeof row.id === 'string' ? row.id : generateId(),
          userMessage: typeof row.userMessage === 'string' ? row.userMessage : 'Restored debug trace',
          status: row.status === 'processing' || row.status === 'error' ? row.status : 'complete',
          startedAt: row.startedAt ? new Date(String(row.startedAt)) : new Date(),
          completedAt: row.completedAt ? new Date(String(row.completedAt)) : undefined,
          trace: row.trace as BotDebugTrace | undefined,
        }))
    );
  } catch {
    return [];
  }
}

function storeDebugSessions(sessions: DebugSession[]) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(DEBUG_STORAGE_KEY, JSON.stringify(limitDebugSessions(sessions)));
  } catch {
    // Debug persistence is helpful, but never worth breaking the chat.
  }
}

function clearStoredDebugSessions() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(DEBUG_STORAGE_KEY);
}

export function useChat(language: string = 'es') {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [debugSessions, setDebugSessions] = useState<DebugSession[]>(() => loadStoredDebugSessions());
  const guestIdRef = useRef<string | null>(null);

  useEffect(() => {
    storeDebugSessions(debugSessions);
  }, [debugSessions]);

  // Get or create guest ID
  const getGuestId = useCallback(() => {
    if (!guestIdRef.current) {
      const stored = localStorage.getItem('guest_id');
      if (stored) {
        guestIdRef.current = stored;
      } else {
        const id = `guest_${Date.now()}_${Math.random().toString(36).slice(2)}`;
        localStorage.setItem('guest_id', id);
        guestIdRef.current = id;
      }
    }
    return guestIdRef.current;
  }, []);

  const initializeSession = useCallback(
    async () => {
      setIsLoading(true);
      const debugSessionId = generateId();

      try {
        const guestId = getGuestId();
        const response = await api.getChatSession(language, guestId, true);
        setLastResponse(response);

        const trace = response.data.debug as BotDebugTrace | undefined;
        if (trace) {
          setDebugSessions((prev) => limitDebugSessions([
            ...prev,
            {
              id: debugSessionId,
              userMessage: response.type === 'greeting' ? 'Session start' : 'Session resume',
              status: 'complete',
              startedAt: new Date(),
              completedAt: new Date(),
              trace,
            },
          ]));
        }

        if (response.type === 'greeting' && response.data.message) {
          const assistantMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: response.data.message,
            type: response.type,
            data: response.data,
            timestamp: new Date(),
          };
          setMessages((prev) =>
            prev.some((msg) => msg.role === 'assistant' && msg.type === 'greeting')
              ? prev
              : [...prev, assistantMessage]
          );
        }

        if (response.type === 'session' && response.data.recap_message) {
          const recapMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: response.data.recap_message,
            type: response.type,
            data: response.data,
            timestamp: new Date(),
          };
          setMessages([recapMessage]);
        } else if (response.type === 'session' && Array.isArray(response.data.messages)) {
          const restoredMessages = (response.data.messages as StoredChatMessage[])
            .filter((msg) => msg.content && (msg.role === 'user' || msg.role === 'assistant'))
            .map<ChatMessage>((msg) => ({
              id: generateId(),
              role: msg.role,
              content: msg.content,
              timestamp: new Date(),
            }));

          if (restoredMessages.length > 0) {
            setMessages(restoredMessages);
          }
        }
      } catch (error) {
        setDebugSessions((prev) => limitDebugSessions([
          ...prev,
          {
            id: debugSessionId,
            userMessage: 'Session start',
            status: 'error',
            startedAt: new Date(),
            completedAt: new Date(),
            trace: {
              enabled: true,
              mode: 'frontend_trace',
              note: 'The session request failed before a backend debug trace was returned.',
              reasoning_summary: 'The frontend session request failed.',
              steps: [
                {
                  stage: 'error',
                  title: 'Session request failed',
                  detail: error instanceof Error ? error.message : 'Unknown error',
                  payload: {
                    api_url: API_URL,
                    request_url: `${API_URL}/chat/session`,
                    page_url: window.location.href,
                    online: navigator.onLine,
                  },
                },
              ],
            },
          },
        ]));
      } finally {
        setIsLoading(false);
      }
    },
    [language, getGuestId]
  );

  const sendMessage = useCallback(
    async (text: string, isAuthenticated: boolean, displayText?: string) => {
      // Add user message to chat
      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: displayText ?? text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      const debugSessionId = generateId();
      setDebugSessions((prev) => limitDebugSessions([
        ...prev,
        {
          id: debugSessionId,
          userMessage: displayText ?? text,
          status: 'processing',
          startedAt: new Date(),
        },
      ]));

      try {
        const guestId = getGuestId();
        const response = await api.sendMessage(text, language, guestId, true);
        setLastResponse(response);
        const trace = response.data.debug as BotDebugTrace | undefined;
        setDebugSessions((prev) =>
          limitDebugSessions(prev.map((session) =>
            session.id === debugSessionId
              ? { ...session, status: 'complete', completedAt: new Date(), trace }
              : session
          ))
        );

        // Add assistant message
        const assistantMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: response.data.message || '',
          type: response.type,
          data: response.data,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (error) {
        setDebugSessions((prev) =>
          limitDebugSessions(prev.map((session) =>
            session.id === debugSessionId
              ? {
                  ...session,
                  status: 'error',
                  completedAt: new Date(),
                  trace: {
                    enabled: true,
                    mode: 'frontend_trace',
                    note: 'The request failed before a backend debug trace was returned.',
                    reasoning_summary: 'The frontend request failed.',
                    steps: [
                      {
                        stage: 'error',
                        title: 'Request failed',
                        detail: error instanceof Error ? error.message : 'Unknown error',
                        payload: {
                          api_url: API_URL,
                          request_url: `${API_URL}/chat/message`,
                          page_url: window.location.href,
                          online: navigator.onLine,
                        },
                      },
                    ],
                  },
                }
              : session
          ))
        );
        const errorMessage: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: 'Lo siento, hubo un error. Intenta de nuevo.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    },
    [language, getGuestId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setLastResponse(null);
    setDebugSessions([]);
    clearStoredDebugSessions();
  }, []);

  const resetSession = useCallback(async () => {
    const guestId = getGuestId();
    await api.resetSession(guestId);
    setMessages([]);
    setLastResponse(null);
    setDebugSessions([]);
    clearStoredDebugSessions();
    await initializeSession();
  }, [getGuestId, initializeSession]);

  return { messages, isLoading, lastResponse, debugSessions, initializeSession, sendMessage, clearMessages, resetSession };
}
