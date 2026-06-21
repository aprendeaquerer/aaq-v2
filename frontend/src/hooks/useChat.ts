'use client';

import { useState, useCallback, useRef } from 'react';
import * as api from '@/lib/api';
import { API_URL } from '@/lib/constants';
import type { BotDebugTrace, ChatMessage, ChatResponse, DebugSession, StoredChatMessage } from '@/lib/types';

let messageIdCounter = 0;
function generateId(): string {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

export function useChat(language: string = 'es') {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [debugSessions, setDebugSessions] = useState<DebugSession[]>([]);
  const guestIdRef = useRef<string | null>(null);

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
          setDebugSessions((prev) => [
            ...prev,
            {
              id: debugSessionId,
              userMessage: response.type === 'greeting' ? 'Session start' : 'Session resume',
              status: 'complete',
              startedAt: new Date(),
              completedAt: new Date(),
              trace,
            },
          ]);
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

        if (response.type === 'session' && Array.isArray(response.data.messages)) {
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
        setDebugSessions((prev) => [
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
        ]);
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
      setDebugSessions((prev) => [
        ...prev,
        {
          id: debugSessionId,
          userMessage: displayText ?? text,
          status: 'processing',
          startedAt: new Date(),
        },
      ]);

      try {
        const guestId = getGuestId();
        const response = await api.sendMessage(text, language, guestId, true);
        setLastResponse(response);
        const trace = response.data.debug as BotDebugTrace | undefined;
        setDebugSessions((prev) =>
          prev.map((session) =>
            session.id === debugSessionId
              ? { ...session, status: 'complete', completedAt: new Date(), trace }
              : session
          )
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
          prev.map((session) =>
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
          )
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
  }, []);

  return { messages, isLoading, lastResponse, debugSessions, initializeSession, sendMessage, clearMessages };
}
