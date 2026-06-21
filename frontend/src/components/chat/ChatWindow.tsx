'use client';

import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useChat } from '@/hooks/useChat';
import { useAuth } from '@/hooks/useAuth';
import { useLanguage } from '@/hooks/useLanguage';
import MessageBubble from './MessageBubble';
import TestQuestion from './TestQuestion';
import TestResults from './TestResults';
import PaywallModal from './PaywallModal';
import TypingIndicator from './TypingIndicator';
import ChatInput from './ChatInput';
import DebugPanel from './DebugPanel';
import DataBrainPanel, { type BrainTab } from './DataBrainPanel';
import type { TestQuestionData, TestResultsData } from '@/lib/types';

type ChatTab = 'chat' | BrainTab;

export default function ChatWindow() {
  const { language } = useLanguage();
  const { isAuthenticated } = useAuth();
  const { messages, isLoading, debugSessions, initializeSession, sendMessage } = useChat(language);
  const [activeTab, setActiveTab] = useState<ChatTab>('chat');
  const memoryRefreshKey = messages.length + debugSessions.length;
  const scrollRef = useRef<HTMLDivElement>(null);
  const sessionInitialized = useRef(false);

  // Auto-scroll to bottom
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isLoading]);

  // Load opening session once (ref prevents React strict mode double-fire)
  useEffect(() => {
    if (!sessionInitialized.current) {
      sessionInitialized.current = true;
      initializeSession(isAuthenticated);
    }
  }, [initializeSession, isAuthenticated]);

  const handleSend = (text: string) => {
    sendMessage(text, isAuthenticated);
  };

  const handleTestAnswer = (optionId: string) => {
    sendMessage(optionId, isAuthenticated);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-[#FFF6EA]">
      <div className="border-b border-[#042648]/15 bg-white px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <TabButton active={activeTab === 'chat'} onClick={() => setActiveTab('chat')}>
            Chat
          </TabButton>
          <TabButton active={activeTab === 'data'} onClick={() => setActiveTab('data')}>
            Data Brain
          </TabButton>
          <TabButton active={activeTab === 'knowledge'} onClick={() => setActiveTab('knowledge')}>
            Knowledge Brain
          </TabButton>
          <TabButton active={activeTab === 'live'} onClick={() => setActiveTab('live')}>
            Live Fill
          </TabButton>
          {activeTab !== 'chat' && (
            <a
              href={`/brain?tab=${activeTab}`}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-[#042648]/15 bg-white px-3 py-2 text-sm font-semibold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Open in new window
            </a>
          )}
        </div>
      </div>

      {activeTab === 'chat' ? (
        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <div className="flex min-h-0 flex-1 flex-col">
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
                      <MessageBubble message={{ ...msg, content: msg.data.message ?? msg.content }} />
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
                      <MessageBubble message={{ ...msg, content: msg.data.message ?? msg.content }} />
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
          <DebugPanel sessions={debugSessions} />
        </div>
      ) : (
        <DataBrainPanel
          activeTab={activeTab}
          debugSessions={debugSessions}
          isAuthenticated={isAuthenticated}
          refreshKey={memoryRefreshKey}
        />
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-3 py-2 text-sm font-semibold transition ${
        active
          ? 'bg-[#042648] text-white'
          : 'border border-[#042648]/15 bg-white text-[#042648]/70 hover:bg-[#F8FAF7]'
      }`}
    >
      {children}
    </button>
  );
}
