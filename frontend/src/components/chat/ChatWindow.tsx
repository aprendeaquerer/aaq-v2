'use client';

import { useEffect, useRef } from 'react';
import { useChat } from '@/hooks/useChat';
import { useAuth } from '@/hooks/useAuth';
import { useLanguage } from '@/hooks/useLanguage';
import MessageBubble from './MessageBubble';
import TestQuestion from './TestQuestion';
import TestResults from './TestResults';
import PaywallModal from './PaywallModal';
import TypingIndicator from './TypingIndicator';
import ChatInput from './ChatInput';
import type { TestQuestionData, TestResultsData } from '@/lib/types';

export default function ChatWindow() {
  const { language } = useLanguage();
  const { isAuthenticated } = useAuth();
  const { messages, isLoading, sendMessage } = useChat(language);
  const scrollRef = useRef<HTMLDivElement>(null);
  const greetingSent = useRef(false);

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isLoading]);

  // Send initial greeting once (ref prevents React strict mode double-fire)
  useEffect(() => {
    if (!greetingSent.current) {
      greetingSent.current = true;
      sendMessage('saludo inicial', isAuthenticated);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = (text: string) => {
    sendMessage(text, isAuthenticated);
  };

  const handleTestAnswer = (optionId: string) => {
    sendMessage(optionId, isAuthenticated);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-[#FFF6EA]">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.map((msg) => {
          // Render different components based on response type
          if (msg.role === 'assistant' && msg.type === 'test_question' && msg.data) {
            return (
              <TestQuestion
                key={msg.id}
                data={msg.data as unknown as TestQuestionData}
                onAnswer={handleTestAnswer}
                disabled={isLoading}
              />
            );
          }

          if (msg.role === 'assistant' && msg.type === 'test_results' && msg.data) {
            return <TestResults key={msg.id} data={msg.data as unknown as TestResultsData} />;
          }

          if (msg.role === 'assistant' && msg.type === 'paywall' && msg.data) {
            return (
              <PaywallModal
                key={msg.id}
                message={msg.data.message || msg.content}
                onClose={() => {}}
              />
            );
          }

          if (msg.role === 'assistant' && msg.type === 'greeting' && msg.data) {
            // Greeting with options
            return (
              <div key={msg.id}>
                <MessageBubble message={{ ...msg, content: msg.data.message }} />
                {msg.data.options && (
                  <div className="flex justify-start mb-3 ml-2">
                    <div className="flex flex-col gap-2">
                      {msg.data.options.map((opt: { id: string; text: string }) => (
                        <button
                          key={opt.id}
                          onClick={() => handleSend(opt.id)}
                          disabled={isLoading}
                          className="text-left px-4 py-2 bg-white border border-[#042648]/20 rounded-xl text-sm hover:bg-[#F1DCF4] transition disabled:opacity-50"
                        >
                          <span className="font-semibold">{opt.id})</span> {opt.text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          }

          if (msg.role === 'assistant' && msg.type === 'partner_offer' && msg.data) {
            return (
              <div key={msg.id}>
                <MessageBubble message={{ ...msg, content: msg.data.message }} />
                {msg.data.options && (
                  <div className="flex justify-start mb-3 ml-2">
                    <div className="flex flex-col gap-2">
                      {msg.data.options.map((opt: { id: string; text: string }) => (
                        <button
                          key={opt.id}
                          onClick={() => handleSend(opt.id)}
                          disabled={isLoading}
                          className="text-left px-4 py-2 bg-white border border-[#042648]/20 rounded-xl text-sm hover:bg-[#F1DCF4] transition disabled:opacity-50"
                        >
                          {opt.text}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          }

          // Default message bubble
          return <MessageBubble key={msg.id} message={msg} />;
        })}

        {isLoading && <TypingIndicator />}
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
