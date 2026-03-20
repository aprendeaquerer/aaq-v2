'use client';

import { useState, useCallback, useRef } from 'react';
import * as api from '@/lib/api';
import type { ChatMessage, ChatResponse } from '@/lib/types';

let messageIdCounter = 0;
function generateId(): string {
  return `msg_${Date.now()}_${++messageIdCounter}`;
}

export function useChat(language: string = 'es') {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
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

  const sendMessage = useCallback(
    async (text: string, isAuthenticated: boolean) => {
      // Add user message to chat
      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        const guestId = isAuthenticated ? undefined : getGuestId();
        const response = await api.sendMessage(text, language, guestId);
        setLastResponse(response);

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
  }, []);

  return { messages, isLoading, lastResponse, sendMessage, clearMessages };
}
