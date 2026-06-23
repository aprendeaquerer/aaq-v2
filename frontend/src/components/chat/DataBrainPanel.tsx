'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import * as api from '@/lib/api';
import { useLanguage } from '@/hooks/useLanguage';
import { personalityTestConversations, type PersonalityTestKind } from '@/data/personalityTestConversations';
import type { DebugSession, KnowledgeChunk, UserMemory, UserProfile } from '@/lib/types';

type BrainMode = 'text' | 'constellation';
export type BrainTab = 'data' | 'knowledge' | 'live' | 'tests';

interface Props {
  activeTab: BrainTab;
  debugSessions: DebugSession[];
  isAuthenticated: boolean;
  refreshKey: number;
  standalone?: boolean;
}

interface LiveCandidate {
  id: string;
  message: string;
  type: string;
  summary: string;
  curated_summary: string;
  status: string;
  confidence: number | null;
  capturedAt: Date;
}

interface VisibleBotTrace {
  intent: string;
  loopStep: string;
  knowledge: string;
  knowledgeWhy: string;
  notes: string[];
  guardrails: string[];
  memoryCandidates: VisibleMemoryCandidate[];
}

interface VisibleMemoryCandidate {
  type: string;
  summary: string;
  confidence: number;
  sensitivity: 'low' | 'medium' | 'high';
  status: 'candidate' | 'reinforce' | 'not_saved';
  reason: string;
}

const TYPE_COLORS = [
  { bg: '#F1DCF4', border: '#9B5AA6', text: '#5B2467' },
  { bg: '#EAF7EF', border: '#2F8F5B', text: '#165A38' },
  { bg: '#FFF0D8', border: '#C1821D', text: '#70490D' },
  { bg: '#E6F0FF', border: '#4674B8', text: '#173F76' },
  { bg: '#FFE8E0', border: '#C76447', text: '#7A2E1D' },
];

export default function DataBrainPanel({
  activeTab,
  debugSessions,
  isAuthenticated,
  refreshKey,
  standalone = false,
}: Props) {
  const { language } = useLanguage();
  const [mode, setMode] = useState<BrainMode>('text');
  const [memories, setMemories] = useState<UserMemory[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [knowledgeChunks, setKnowledgeChunks] = useState<KnowledgeChunk[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isKnowledgeLoading, setIsKnowledgeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);
  const [selectedKnowledgeChunk, setSelectedKnowledgeChunk] = useState<KnowledgeChunk | null>(null);
  const [selectedMemory, setSelectedMemory] = useState<UserMemory | null>(null);
  const [collapsedKnowledgeDomains, setCollapsedKnowledgeDomains] = useState<Set<string>>(new Set());
  const [selectedPersonalityTestId, setSelectedPersonalityTestId] = useState(
    personalityTestConversations[0]?.id || ''
  );

  const loadMemories = useCallback(async () => {
    if (!isAuthenticated) {
      setMemories([]);
      setError(null);
      return;
    }

    setIsLoading(true);
    try {
      const nextMemories = await api.getUserMemories();
      setMemories(nextMemories);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to fetch memories');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  const loadKnowledge = useCallback(async () => {
    setIsKnowledgeLoading(true);
    try {
      const brain = await api.getKnowledgeBrain(language);
      setKnowledgeChunks(brain.chunks);
      setKnowledgeError(null);
    } catch (loadError) {
      setKnowledgeError(loadError instanceof Error ? loadError.message : 'Failed to fetch knowledge brain');
    } finally {
      setIsKnowledgeLoading(false);
    }
  }, [language]);

  const loadProfile = useCallback(async () => {
    if (!isAuthenticated) {
      setProfile(null);
      return;
    }

    try {
      const nextProfile = await api.getProfile();
      setProfile(nextProfile);
    } catch {
      setProfile(null);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadMemories();
  }, [loadMemories, refreshKey]);

  useEffect(() => {
    if (activeTab === 'data' || activeTab === 'live') {
      void loadProfile();
    }
  }, [activeTab, loadProfile, refreshKey]);

  useEffect(() => {
    if (activeTab === 'knowledge') {
      void loadKnowledge();
    }
  }, [activeTab, loadKnowledge]);

  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'live') return;

    const interval = window.setInterval(() => {
      void loadMemories();
    }, 3000);

    return () => window.clearInterval(interval);
  }, [activeTab, isAuthenticated, loadMemories]);

  const liveCandidates = useMemo(() => extractLiveCandidates(debugSessions), [debugSessions]);
  const groupedMemories = useMemo(() => groupMemoriesByType(memories), [memories]);
  const groupedKnowledge = useMemo(() => groupKnowledgeByDomain(knowledgeChunks), [knowledgeChunks]);
  const knowledgeDomains = useMemo(() => groupedKnowledge.map(([domain]) => domain), [groupedKnowledge]);
  const selectedPersonalityTest = useMemo(
    () =>
      personalityTestConversations.find((conversation) => conversation.id === selectedPersonalityTestId) ||
      personalityTestConversations[0],
    [selectedPersonalityTestId]
  );

  useEffect(() => {
    setCollapsedKnowledgeDomains(new Set(knowledgeDomains));
  }, [knowledgeDomains]);

  const toggleKnowledgeDomain = (domain: string) => {
    setCollapsedKnowledgeDomains((current) => {
      const next = new Set(current);
      if (next.has(domain)) {
        next.delete(domain);
      } else {
        next.add(domain);
      }
      return next;
    });
  };

  const collapseAllKnowledgeDomains = () => {
    setCollapsedKnowledgeDomains(new Set(knowledgeDomains));
  };

  const expandAllKnowledgeDomains = () => {
    setCollapsedKnowledgeDomains(new Set());
  };

  if (activeTab === 'tests') {
    return (
      <BrainShell
        title="Personality Tests"
        subtitle="Threaded QA conversations for the current relationship coach personality."
        countLabel={`${personalityTestConversations.length} threads`}
        openHref="/brain?tab=tests"
        standalone={standalone}
      >
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[330px_minmax(0,1fr)]">
          <aside className="min-h-0 overflow-y-auto rounded border border-[#042648]/12 bg-white">
            <div className="border-b border-[#042648]/10 px-3 py-3">
              <h3 className="text-sm font-bold text-[#042648]">Conversation Threads</h3>
              <p className="mt-1 text-xs text-[#042648]/60">
                20 scenarios with 10 user prompts each.
              </p>
            </div>
            <div className="space-y-1 p-2">
              {personalityTestConversations.map((conversation) => (
                <PersonalityThreadButton
                  key={conversation.id}
                  conversation={conversation}
                  isSelected={conversation.id === selectedPersonalityTest?.id}
                  onSelect={() => setSelectedPersonalityTestId(conversation.id)}
                />
              ))}
            </div>
          </aside>

          <div className="min-h-0 overflow-y-auto pr-1">
            {selectedPersonalityTest && (
              <PersonalityThreadReader conversation={selectedPersonalityTest} />
            )}
          </div>
        </div>
      </BrainShell>
    );
  }

  if (activeTab === 'knowledge') {
    return (
      <BrainShell
        title="Knowledge Brain"
        subtitle="File-backed relationship, attachment, somatics, polarity, and growth knowledge."
        countLabel={isKnowledgeLoading ? 'Loading...' : `${knowledgeChunks.length} chunks`}
        openHref="/brain?tab=knowledge"
        standalone={standalone}
        toolbar={<BrainModeToggle mode={mode} onChange={setMode} />}
      >
        {knowledgeError && (
          <div className="mb-3 rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-3 py-2 text-sm text-[#7A1F1F]">
            {knowledgeError}
          </div>
        )}

        {knowledgeChunks.length === 0 && !isKnowledgeLoading && (
          <div className="rounded border border-dashed border-[#042648]/25 bg-white px-4 py-6 text-sm text-[#042648]/70">
            No knowledge chunks were loaded.
          </div>
        )}

        {mode === 'text' && knowledgeChunks.length > 0 && (
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded border border-[#042648]/12 bg-white px-3 py-2">
              <div className="text-xs font-semibold text-[#042648]/55">
                {knowledgeDomains.length} categories
              </div>
              <div className="flex rounded border border-[#042648]/15 bg-[#F8FAF7] p-1">
                <button
                  type="button"
                  onClick={expandAllKnowledgeDomains}
                  className="px-3 py-1.5 text-xs font-semibold text-[#042648]/70 transition hover:bg-white"
                >
                  Expand all
                </button>
                <button
                  type="button"
                  onClick={collapseAllKnowledgeDomains}
                  className="px-3 py-1.5 text-xs font-semibold text-[#042648]/70 transition hover:bg-white"
                >
                  Fold all
                </button>
              </div>
            </div>
            <div className="space-y-4">
              {groupedKnowledge.map(([domain, rows], groupIndex) => (
                <section key={domain} className="rounded border border-[#042648]/12 bg-white">
                  <button
                    type="button"
                    onClick={() => toggleKnowledgeDomain(domain)}
                    className="flex w-full items-center justify-between gap-3 px-3 py-3 text-left transition hover:bg-[#F8FAF7]"
                    aria-expanded={!collapsedKnowledgeDomains.has(domain)}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: getTypeColor(groupIndex).border }}
                      />
                      <span className="truncate text-sm font-bold uppercase tracking-[0.06em] text-[#042648]/70">
                        {formatType(domain)}
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="text-xs text-[#042648]/45">{rows.length} chunks</span>
                      <span className="flex h-7 w-7 items-center justify-center rounded border border-[#042648]/15 bg-white text-sm font-bold text-[#042648]/60">
                        {collapsedKnowledgeDomains.has(domain) ? '+' : '-'}
                      </span>
                    </span>
                  </button>
                  {!collapsedKnowledgeDomains.has(domain) && (
                    <div className="grid gap-3 border-t border-[#042648]/10 bg-[#FFFDF8] p-3 md:grid-cols-2 xl:grid-cols-3">
                      {rows.map((chunk) => (
                        <KnowledgeCard
                          key={chunk.id}
                          chunk={chunk}
                          onOpen={() => setSelectedKnowledgeChunk(chunk)}
                        />
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          </div>
        )}

        {mode === 'constellation' && knowledgeChunks.length > 0 && (
          <div className="min-h-0 flex-1 overflow-hidden rounded border border-[#042648]/12 bg-white">
            <KnowledgeConstellation
              chunks={knowledgeChunks}
              onOpenChunk={setSelectedKnowledgeChunk}
            />
          </div>
        )}

        {selectedKnowledgeChunk && (
          <KnowledgeReader
            chunk={selectedKnowledgeChunk}
            onClose={() => setSelectedKnowledgeChunk(null)}
          />
        )}
      </BrainShell>
    );
  }

  if (!isAuthenticated) {
    return (
      <BrainShell
        title={activeTab === 'data' ? 'Data Brain' : 'Live Fill'}
        subtitle="Sign in to see user memory data."
        openHref={`/brain?tab=${activeTab}`}
        standalone={standalone}
      >
        <div className="rounded border border-dashed border-[#042648]/25 bg-white px-4 py-6 text-sm text-[#042648]/70">
          Guest chats are not written into the persistent user data brain.
        </div>
      </BrainShell>
    );
  }

  if (activeTab === 'live') {
    return (
      <BrainShell
        title="Live Fill"
        subtitle="Candidate memories captured from this chat session."
        countLabel={`${liveCandidates.length} events`}
        openHref="/brain?tab=live"
        standalone={standalone}
      >
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-h-0 overflow-y-auto pr-1">
            {liveCandidates.length === 0 && (
              <div className="rounded border border-dashed border-[#042648]/25 bg-white px-4 py-6 text-sm text-[#042648]/70">
                No candidate memories captured in this session yet.
              </div>
            )}

            <div className="space-y-3">
              {liveCandidates.map((candidate, index) => (
                <LiveCandidateCard
                  key={`${candidate.id}-${index}`}
                  candidate={candidate}
                  index={liveCandidates.length - index}
                />
              ))}
            </div>
          </div>

          <aside className="min-h-0 overflow-y-auto rounded border border-[#042648]/12 bg-white">
            <ProfileSummary profile={profile} />
            <div className="border-b border-[#042648]/10 px-3 py-2">
              <h3 className="text-sm font-bold text-[#042648]">Stored Now</h3>
              <p className="mt-1 text-xs text-[#042648]/60">
                {isLoading ? 'Refreshing...' : `${memories.length} visible memories`}
              </p>
            </div>
            <div className="space-y-2 p-3">
              {memories.slice(0, 6).map((memory) => (
                <CompactMemory key={memory.id} memory={memory} />
              ))}
              {memories.length === 0 && (
                <p className="text-sm text-[#042648]/60">The persistent brain is empty.</p>
              )}
            </div>
          </aside>
        </div>
      </BrainShell>
    );
  }

  return (
    <BrainShell
      title="Data Brain"
      subtitle="Stable profile fields plus user-visible memories from the conversation."
      countLabel={`${memories.length} memories`}
      openHref="/brain?tab=data"
      standalone={standalone}
      toolbar={
        <BrainModeToggle mode={mode} onChange={setMode} />
      }
    >
      <div className="mb-4">
        <ProfileSummary profile={profile} />
      </div>

      {error && (
        <div className="mb-3 rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-3 py-2 text-sm text-[#7A1F1F]">
          {error}
        </div>
      )}

      {memories.length === 0 && !isLoading && (
        <div className="rounded border border-dashed border-[#042648]/25 bg-white px-4 py-6 text-sm text-[#042648]/70">
          No visible memories have been captured yet.
        </div>
      )}

      {mode === 'text' && memories.length > 0 && (
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="space-y-4">
            {groupedMemories.map(([type, rows], groupIndex) => (
              <section key={type}>
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: getTypeColor(groupIndex).border }}
                  />
                  <h3 className="text-sm font-bold uppercase tracking-[0.06em] text-[#042648]/70">
                    {formatType(type)}
                  </h3>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {rows.map((memory) => (
                    <MemoryCard key={memory.id} memory={memory} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      )}

      {mode === 'constellation' && memories.length > 0 && (
        <div className="min-h-0 flex-1 overflow-hidden rounded border border-[#042648]/12 bg-white">
          <Constellation memories={memories} onOpenMemory={setSelectedMemory} />
        </div>
      )}

      {selectedMemory && (
        <MemoryReader memory={selectedMemory} onClose={() => setSelectedMemory(null)} />
      )}
    </BrainShell>
  );
}

function BrainShell({
  title,
  subtitle,
  countLabel,
  openHref,
  standalone,
  toolbar,
  children,
}: {
  title: string;
  subtitle: string;
  countLabel?: string;
  openHref?: string;
  standalone?: boolean;
  toolbar?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-[#FFF6EA] px-4 py-4 text-[#042648]">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">{title}</h2>
          <p className="mt-1 text-sm text-[#042648]/65">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          {countLabel && (
            <span className="rounded-full border border-[#042648]/20 bg-white px-3 py-1 text-xs font-semibold">
              {countLabel}
            </span>
          )}
          {toolbar}
          {openHref && !standalone && (
            <a
              href={openHref}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-[#042648]/15 bg-white px-3 py-1.5 text-xs font-semibold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Open in new window
            </a>
          )}
        </div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

function BrainModeToggle({ mode, onChange }: { mode: BrainMode; onChange: (mode: BrainMode) => void }) {
  return (
    <div className="flex rounded border border-[#042648]/15 bg-white p-1">
      <button
        type="button"
        onClick={() => onChange('text')}
        className={`px-3 py-1.5 text-xs font-semibold transition ${
          mode === 'text' ? 'bg-[#042648] text-white' : 'text-[#042648]/70 hover:bg-[#F8FAF7]'
        }`}
      >
        Text
      </button>
      <button
        type="button"
        onClick={() => onChange('constellation')}
        className={`px-3 py-1.5 text-xs font-semibold transition ${
          mode === 'constellation' ? 'bg-[#042648] text-white' : 'text-[#042648]/70 hover:bg-[#F8FAF7]'
        }`}
      >
        Constellation
      </button>
    </div>
  );
}

function PersonalityThreadButton({
  conversation,
  isSelected,
  onSelect,
}: {
  conversation: (typeof personalityTestConversations)[number];
  isSelected: boolean;
  onSelect: () => void;
}) {
  const userPromptCount = conversation.turns.filter((turn) => turn.role === 'user').length;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded border px-3 py-2 text-left transition ${
        isSelected
          ? 'border-[#042648] bg-[#042648] text-white'
          : 'border-transparent bg-white text-[#042648] hover:border-[#042648]/15 hover:bg-[#F8FAF7]'
      }`}
    >
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] opacity-65">
        {formatType(conversation.kind)}
      </div>
      <div className="mt-1 text-sm font-bold leading-snug">{conversation.title}</div>
      <div className="mt-1 text-xs opacity-65">{userPromptCount} user prompts</div>
    </button>
  );
}

function PersonalityThreadReader({
  conversation,
}: {
  conversation: (typeof personalityTestConversations)[number];
}) {
  const userPromptCount = conversation.turns.filter((turn) => turn.role === 'user').length;

  return (
    <article className="rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              {formatType(conversation.kind)}
            </div>
            <h3 className="mt-1 text-base font-bold text-[#042648]">{conversation.title}</h3>
          </div>
          <span className="rounded border border-[#042648]/15 bg-[#F8FAF7] px-2 py-1 text-[11px] font-semibold text-[#042648]/60">
            {userPromptCount} user prompts / {conversation.turns.length} turns
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-[#042648]/68">{conversation.purpose}</p>
      </div>

      <div className="space-y-3 px-3 py-3">
        {conversation.turns.map((turn, index) => {
          const previousUserTurn = getPreviousUserTurn(conversation.turns, index);
          const assistantTurnNumber = getAssistantTurnNumber(conversation.turns, index);
          const trace =
            turn.role === 'assistant'
              ? buildVisibleBotTrace(conversation, assistantTurnNumber, previousUserTurn, turn.content)
              : null;

          return (
            <div
              key={`${conversation.id}-${turn.role}-${index}`}
              className={`rounded border px-3 py-2 ${
                turn.role === 'assistant'
                  ? 'border-[#2F8F5B]/18 bg-[#EAF7EF]'
                  : 'border-[#042648]/10 bg-[#F8FAF7]'
              }`}
            >
              <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
                {turn.role === 'assistant' ? `Bot / Reply ${assistantTurnNumber}` : 'Usuario'}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">{turn.content}</p>
              {trace && <VisibleBotTracePanel trace={trace} />}
            </div>
          );
        })}
      </div>

      <div className="border-t border-[#042648]/10 bg-[#FFFDF8] px-3 py-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
          QA note
        </div>
        <p className="mt-1 text-sm leading-relaxed text-[#042648]/68">{conversation.qaNote}</p>
      </div>
    </article>
  );
}

function VisibleBotTracePanel({ trace }: { trace: VisibleBotTrace }) {
  return (
    <div className="mt-3 rounded border border-[#2F8F5B]/20 bg-white/70 px-3 py-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#165A38]/70">
          Visible Bot Trace
        </div>
        <div className="text-[11px] font-semibold text-[#042648]/45">
          QA notes, not private chain-of-thought
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2">
        <TraceField label="Intent" value={trace.intent} />
        <TraceField label="Loop Step" value={trace.loopStep} />
        <TraceField label="Knowledge Chosen" value={trace.knowledge} />
        <TraceField label="Why This Knowledge" value={trace.knowledgeWhy} />
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        <TraceList label="Notes Taken" values={trace.notes} />
        <TraceList label="Guardrails Applied" values={trace.guardrails} />
      </div>

      <MemoryCaptureList candidates={trace.memoryCandidates} />
    </div>
  );
}

function TraceField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        {label}
      </div>
      <div className="mt-1 text-xs leading-5 text-[#042648]/78">{value}</div>
    </div>
  );
}

function TraceList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        {label}
      </div>
      <div className="mt-2 space-y-1.5">
        {values.map((value, index) => (
          <div key={`${label}-${index}`} className="text-xs leading-5 text-[#042648]/78">
            {value}
          </div>
        ))}
      </div>
    </div>
  );
}

function MemoryCaptureList({ candidates }: { candidates: VisibleMemoryCandidate[] }) {
  return (
    <div className="mt-3 rounded bg-[#FFFDF8] px-3 py-2">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
          Simulated Memory Capture
        </div>
        <div className="text-[11px] font-semibold text-[#042648]/45">
          QA preview, not a database write
        </div>
      </div>

      <div className="space-y-2">
        {candidates.map((candidate, index) => (
          <div
            key={`${candidate.type}-${index}`}
            className="rounded border border-[#042648]/10 bg-white px-3 py-2"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-bold text-[#042648]">{formatType(candidate.type)}</div>
              <div className="flex flex-wrap gap-1.5 text-[11px] font-semibold text-[#042648]/58">
                <span className="rounded bg-[#F8FAF7] px-2 py-0.5">{candidate.status}</span>
                <span className="rounded bg-[#F8FAF7] px-2 py-0.5">{candidate.sensitivity}</span>
                <span className="rounded bg-[#F8FAF7] px-2 py-0.5">
                  {Math.round(candidate.confidence * 100)}% confidence
                </span>
              </div>
            </div>
            <p className="mt-2 text-xs leading-5 text-[#042648]/78">{candidate.summary}</p>
            <p className="mt-1 text-[11px] leading-4 text-[#042648]/50">{candidate.reason}</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#042648]/10">
              <div
                className="h-full rounded-full bg-[#2F8F5B]"
                style={{ width: `${Math.round(candidate.confidence * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getPreviousUserTurn(turns: (typeof personalityTestConversations)[number]['turns'], index: number): string {
  for (let currentIndex = index - 1; currentIndex >= 0; currentIndex -= 1) {
    if (turns[currentIndex].role === 'user') {
      return turns[currentIndex].content;
    }
  }
  return '';
}

function getAssistantTurnNumber(turns: (typeof personalityTestConversations)[number]['turns'], index: number): number {
  return turns.slice(0, index + 1).filter((turn) => turn.role === 'assistant').length;
}

function buildVisibleBotTrace(
  conversation: (typeof personalityTestConversations)[number],
  assistantTurnNumber: number,
  previousUserTurn: string,
  assistantContent: string
): VisibleBotTrace {
  const knowledge = getScenarioKnowledge(conversation.id, conversation.kind);
  const followUpQuestion = extractLastQuestion(assistantContent);

  return {
    intent: getTraceIntent(conversation.kind, assistantTurnNumber, previousUserTurn),
    loopStep: getTraceLoopStep(conversation.kind, assistantTurnNumber, assistantContent),
    knowledge: knowledge.title,
    knowledgeWhy: getKnowledgeWhy(knowledge.why, previousUserTurn, assistantTurnNumber),
    notes: [
      `User signal: ${compactText(previousUserTurn, 150)}`,
      `State tracked: ${getStateTracked(conversation.kind, assistantTurnNumber)}`,
      `Next information gap: ${followUpQuestion || 'No follow-up; the user asked for reflection only.'}`,
    ],
    guardrails: getTraceGuardrails(conversation.kind, assistantContent),
    memoryCandidates: buildMemoryCandidates(conversation, assistantTurnNumber, previousUserTurn, assistantContent),
  };
}

function getTraceIntent(kind: PersonalityTestKind, turnNumber: number, userTurn: string): string {
  if (kind === 'seguridad') return 'Safety triage before relationship coaching.';
  if (kind === 'resistencia' && turnNumber >= 4) return 'Respect resistance and stay in rapport-only mode.';
  if (kind === 'desahogo' && turnNumber <= 2) return 'Venting: reflect emotional content before solving.';
  if (kind === 'duda' && turnNumber === 1) return 'Concrete question: answer directly, then check the missing context.';
  if (userTurn.toLowerCase().includes('quiero') || userTurn.toLowerCase().includes('creo que')) {
    return 'Problem-solving: respond to the chosen path without taking the decision away.';
  }
  return 'Problem mapping: separate facts, assumptions, feelings, and next missing data.';
}

function getTraceLoopStep(kind: PersonalityTestKind, turnNumber: number, assistantContent: string): string {
  if (kind === 'seguridad') return turnNumber <= 2 ? 'Safety check' : 'Immediate support plan';
  if (kind === 'resistencia' && !assistantContent.includes('?')) return 'Reflect only';
  if (kind === 'desahogo' && turnNumber <= 3) return 'Rapport / devolver';
  if (kind === 'duda' && turnNumber <= 2) return 'Answer / clarify';
  if (turnNumber <= 3) return 'Entiende / escucha';
  if (turnNumber <= 5) return 'Explicación';
  if (turnNumber <= 7) return 'Soluciones';
  return 'Plan de acción / seguimiento';
}

function getScenarioKnowledge(id: string, kind: PersonalityTestKind): { title: string; why: string } {
  const map: Record<string, { title: string; why: string }> = {
    'control-digital-pareja-hetero': {
      title: 'Boundaries without coercion; privacy as a relationship limit.',
      why: 'The user describes phone access, guilt, jealousy, and pressure around privacy.',
    },
    'hombre-gay-exclusividad': {
      title: 'Dating clarity signals; explicit agreements over mind-reading.',
      why: 'The issue is undefined exclusivity and app use without a shared agreement.',
    },
    'persona-no-binaria-relacion-abierta': {
      title: 'Open relationship care agreements; jealousy as information.',
      why: 'The user wants non-monogamy but needs reconnection rituals and emotional care.',
    },
    'matrimonio-carga-mental': {
      title: 'Couple dynamics; responsibility by area instead of task delegation.',
      why: 'The problem is invisible labor and household ownership, not a single task.',
    },
    'ex-vuelve-divorcio': {
      title: 'Breakup repair; evidence of changed behavior before re-entry.',
      why: 'The user is emotionally activated by an ex and needs facts before nostalgia.',
    },
    'hombre-joven-rechazo': {
      title: 'Rejection resilience and reading reciprocity.',
      why: 'The user turns a specific rejection into a global self-worth conclusion.',
    },
    'distancia-bisexual': {
      title: 'Long-distance reconnection agreements.',
      why: 'The trigger is distance, delayed contact, and fear of being replaced.',
    },
    'hombre-trans-citas': {
      title: 'Dating disclosure with safety, consent, and pacing.',
      why: 'The user needs agency around when and how to share sensitive identity information.',
    },
    'lesbianas-convivencia-silencio': {
      title: 'Negative cycle repair; pause with return.',
      why: 'The pattern is withdrawal, pursuit, and unresolved repair after conflict.',
    },
    'viudo-mayor-citas': {
      title: 'Grief and new attachment; permission without replacement.',
      why: 'The user feels guilt about dating after loss and needs a small next step.',
    },
    'embarazo-compromiso': {
      title: 'Relationship decision under practical pressure.',
      why: 'Pregnancy creates immediate needs for presence, logistics, and support.',
    },
    'ruptura-no-contacto': {
      title: 'No-contact grief plan; impulse delay and stimulus reduction.',
      why: 'The user is in acute breakup distress and wants to write from anxiety.',
    },
    'familia-religion-pareja': {
      title: 'Partner-family boundary; values without contempt.',
      why: 'The user is between family pressure, faith, and a partner who reacts with anger.',
    },
    'intimidad-consentimiento': {
      title: 'Consent and sexual pressure; desire differences with boundaries.',
      why: 'The user reports pressure and emotional consequences after saying no.',
    },
    'ghosting-apps': {
      title: 'Dating apps: pattern over isolated response time.',
      why: 'The user is interpreting response delay as proof of low interest.',
    },
    'apego-ansioso-whatsapp': {
      title: 'Anxious activation loop; interrupt checking before conflict.',
      why: 'The user checks WhatsApp status and turns delay into lack of importance.',
    },
    'violencia-control-aislamiento': {
      title: 'Safety rules for coercive control and isolation.',
      why: 'Keys removed and isolation from friends indicate real safety risk.',
    },
    'amenaza-suicidio-ruptura': {
      title: 'Self-harm crisis response; emergency support before coaching.',
      why: 'The user states suicidal intent tonight, so safety overrides relationship advice.',
    },
    'poliamor-limites': {
      title: 'Polyamory agreements; reliability and information boundaries.',
      why: 'The issue is canceled plans and too much intimate detail, not the structure itself.',
    },
    'resistencia-no-consejos': {
      title: 'Resistance handling; rapport and reflection without advice.',
      why: 'The user explicitly asks for no advice and wants emotional reflection.',
    },
  };

  return map[id] || {
    title: `${formatType(kind)} response rules.`,
    why: 'The response follows the selected conversation mode and one-question rule.',
  };
}

function getKnowledgeWhy(baseWhy: string, previousUserTurn: string, turnNumber: number): string {
  const turnSignal = previousUserTurn ? `Turn ${turnNumber} signal: ${compactText(previousUserTurn, 90)}` : '';
  return turnSignal ? `${baseWhy} ${turnSignal}` : baseWhy;
}

function getStateTracked(kind: PersonalityTestKind, turnNumber: number): string {
  if (kind === 'seguridad') return 'Current risk, immediate support, access to safe people, and next safety action.';
  if (kind === 'resistencia') return 'Resistance level, preferred depth, and whether to stop asking questions.';
  if (turnNumber <= 3) return 'Facts versus assumptions, emotional load, and missing context.';
  if (turnNumber <= 6) return 'Emerging pattern, attempted fixes, and viable options.';
  return 'Chosen option, concrete action, timing, and success indicators.';
}

function getTraceGuardrails(kind: PersonalityTestKind, assistantContent: string): string[] {
  const guardrails = ['One question maximum.', 'No diagnosis of user or other people.', 'No promise of outcome.'];

  if (kind === 'seguridad') {
    guardrails.push('Prioritize safety over relationship strategy.');
    guardrails.push('Escalate to human/emergency support when risk is present.');
  }

  if (kind === 'resistencia' || !assistantContent.includes('?')) {
    guardrails.push('Do not insist when the user resists exploration.');
  }

  if (assistantContent.includes('límite') || assistantContent.includes('seguridad')) {
    guardrails.push('Keep responsibility with the user; offer options, not orders.');
  }

  return guardrails;
}

function buildMemoryCandidates(
  conversation: (typeof personalityTestConversations)[number],
  turnNumber: number,
  previousUserTurn: string,
  assistantContent: string
): VisibleMemoryCandidate[] {
  if (!previousUserTurn) {
    return [notSavedMemory('No user message available for this assistant turn.')];
  }

  if (conversation.kind === 'seguridad') {
    return [
      {
        type: conversation.id === 'amenaza-suicidio-ruptura' ? 'safety_self_harm_risk' : 'safety_relationship_risk',
        summary: compactText(`Safety-relevant disclosure: ${previousUserTurn}`, 170),
        confidence: conversation.id === 'amenaza-suicidio-ruptura' ? 0.96 : 0.92,
        sensitivity: 'high',
        status: turnNumber <= 2 ? 'candidate' : 'reinforce',
        reason: 'High-sensitivity memory because the user disclosed current risk, coercive control, or need for immediate support.',
      },
    ];
  }

  if (conversation.kind === 'resistencia' && !assistantContent.includes('?')) {
    return [
      {
        type: 'conversation_preference',
        summary: 'User prefers reflection-only support in this moment and does not want advice or analysis.',
        confidence: 0.9,
        sensitivity: 'medium',
        status: 'reinforce',
        reason: 'Repeated explicit preference across the thread; useful for tone and response depth.',
      },
    ];
  }

  if (turnNumber === 1) {
    return [
      {
        type: 'relationship_context',
        summary: compactText(`Initial scenario context: ${previousUserTurn}`, 170),
        confidence: previousUserTurn.toLowerCase().includes('soy ') ? 0.88 : 0.8,
        sensitivity: inferSensitivity(previousUserTurn),
        status: 'candidate',
        reason: 'Opening message contains stable context about identity, relationship structure, and the presenting issue.',
      },
    ];
  }

  if (isActionPlanTurn(previousUserTurn, assistantContent, turnNumber)) {
    return [
      {
        type: 'action_plan',
        summary: compactText(`Chosen next step or plan signal: ${previousUserTurn}`, 170),
        confidence: 0.84,
        sensitivity: inferSensitivity(previousUserTurn),
        status: 'candidate',
        reason: 'The user selected a path, timing, script, or concrete next action that should be followed up later.',
      },
    ];
  }

  if (isUserPreferenceTurn(previousUserTurn)) {
    return [
      {
        type: 'user_preference',
        summary: compactText(`Preference or boundary expressed: ${previousUserTurn}`, 170),
        confidence: 0.78,
        sensitivity: inferSensitivity(previousUserTurn),
        status: 'candidate',
        reason: 'The user stated a preference, fear, boundary, or desired response style that can improve future support.',
      },
    ];
  }

  if (turnNumber <= 6) {
    return [
      {
        type: 'relationship_pattern',
        summary: compactText(`Pattern detail from user: ${previousUserTurn}`, 170),
        confidence: 0.72,
        sensitivity: inferSensitivity(previousUserTurn),
        status: 'candidate',
        reason: 'The message adds behavioral evidence about the recurring relational pattern.',
      },
    ];
  }

  return [notSavedMemory('No new stable memory; this turn mostly continues the current conversation state.')];
}

function notSavedMemory(summary: string): VisibleMemoryCandidate {
  return {
    type: 'transient_context',
    summary,
    confidence: 0.35,
    sensitivity: 'low',
    status: 'not_saved',
    reason: 'Useful inside this thread, but too temporary or repetitive for persistent user memory.',
  };
}

function inferSensitivity(value: string): VisibleMemoryCandidate['sensitivity'] {
  const lowerValue = value.toLowerCase();
  if (
    lowerValue.includes('matar') ||
    lowerValue.includes('suicid') ||
    lowerValue.includes('llaves') ||
    lowerValue.includes('sexo') ||
    lowerValue.includes('embarazada') ||
    lowerValue.includes('trans') ||
    lowerValue.includes('violencia')
  ) {
    return 'high';
  }
  if (
    lowerValue.includes('familia') ||
    lowerValue.includes('relig') ||
    lowerValue.includes('culpa') ||
    lowerValue.includes('ansiedad') ||
    lowerValue.includes('celos') ||
    lowerValue.includes('ex')
  ) {
    return 'medium';
  }
  return 'low';
}

function isActionPlanTurn(userTurn: string, assistantContent: string, turnNumber: number): boolean {
  const lowerUserTurn = userTurn.toLowerCase();
  const lowerAssistantContent = assistantContent.toLowerCase();
  return (
    turnNumber >= 6 &&
    (lowerUserTurn.includes('mañana') ||
      lowerUserTurn.includes('jueves') ||
      lowerUserTurn.includes('viernes') ||
      lowerUserTurn.includes('domingo') ||
      lowerUserTurn.includes('hoy') ||
      lowerUserTurn.includes('sí') ||
      lowerUserTurn.includes('quiero') ||
      lowerAssistantContent.includes('plan'))
  );
}

function isUserPreferenceTurn(userTurn: string): boolean {
  const lowerUserTurn = userTurn.toLowerCase();
  return (
    lowerUserTurn.includes('quiero') ||
    lowerUserTurn.includes('necesito') ||
    lowerUserTurn.includes('me da miedo') ||
    lowerUserTurn.includes('me gustaría') ||
    lowerUserTurn.includes('prefiero') ||
    lowerUserTurn.includes('me serviría')
  );
}

function extractLastQuestion(content: string): string {
  const match = content.match(/([^.\n!?]*\?)/g);
  if (!match || match.length === 0) return '';
  return match[match.length - 1].trim();
}

function compactText(value: string, maxLength: number): string {
  const compacted = value.replace(/\s+/g, ' ').trim();
  if (compacted.length <= maxLength) return compacted;
  return `${compacted.slice(0, maxLength - 3)}...`;
}

function ProfileSummary({ profile }: { profile: UserProfile | null }) {
  const rows = profile ? buildProfileRows(profile) : [];

  return (
    <section className="rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <h3 className="text-sm font-bold text-[#042648]">Stable Profile</h3>
        <p className="mt-1 text-xs text-[#042648]/60">
          Empirical facts captured from profile, tests, and chat.
        </p>
      </div>

      <div className="grid gap-2 p-3 md:grid-cols-2 xl:grid-cols-3">
        {rows.length > 0 ? (
          rows.map(([label, value]) => (
            <div key={label} className="rounded bg-[#F8FAF7] px-3 py-2">
              <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-[#042648]/45">
                {label}
              </div>
              <div className="mt-1 break-words text-sm font-semibold text-[#042648]/80">
                {value}
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-[#042648]/60">
            No stable profile fields yet. Feelings, goals, and patterns appear as memories below.
          </p>
        )}
      </div>
    </section>
  );
}

function buildProfileRows(profile: UserProfile): [string, string][] {
  const rows: [string, string][] = [];
  addRow(rows, 'Name', profile.nombre);
  addRow(rows, 'Age', profile.edad);
  addRow(rows, 'Gender', profile.genero);
  addRow(rows, 'Has partner', formatBoolean(profile.tiene_pareja));
  addRow(rows, 'Partner name', profile.nombre_pareja);
  addRow(rows, 'Partner age', profile.edad_pareja);
  addRow(rows, 'Partner gender', profile.genero_pareja);
  addRow(rows, 'Time together', profile.tiempo_pareja);
  addRow(rows, 'Relationship type', profile.tipo_relacion);
  addRow(rows, 'Lives together', formatBoolean(profile.convive_con_pareja));
  addRow(rows, 'Living situation', profile.convivencia);
  addRow(rows, 'Work', profile.trabajo_profesion);
  addRow(rows, 'Has children', formatBoolean(profile.tiene_hijos));
  addRow(rows, 'Children details', profile.hijos_detalle);
  addRow(rows, 'Relevant ex', formatBoolean(profile.ex_pareja_relevante));
  addRow(rows, 'Ex context', profile.ex_pareja_contexto);
  addRow(rows, 'Family structure', profile.estructura_familiar_relevante);
  addRow(rows, 'Orientation', profile.orientacion);
  addRow(rows, 'Language', profile.preferred_language);
  addRow(rows, 'Premium', formatBoolean(profile.is_premium));
  addRow(rows, 'Email verified', formatBoolean(profile.email_verified));
  return rows;
}

function addRow(rows: [string, string][], label: string, value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return;
  rows.push([label, String(value)]);
}

function formatBoolean(value: boolean | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  return value ? 'Yes' : 'No';
}

function MemoryCard({ memory }: { memory: UserMemory }) {
  return (
    <article className="rounded border border-[#042648]/12 bg-white px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold">{formatType(memory.type)}</div>
          <div className="mt-1 text-xs text-[#042648]/55">{formatTimestamp(memory.updated_at)}</div>
        </div>
        <StatusBadge status={memory.status} />
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[#042648]/78">
        {memory.curated_summary || memory.summary}
      </p>
      <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold text-[#042648]/55">
        <span>{memory.sensitivity}</span>
        <span>{Math.round(memory.confidence * 100)}% confidence</span>
      </div>
    </article>
  );
}

function MemoryReader({ memory, onClose }: { memory: UserMemory; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#042648]/35 px-4 py-6">
      <div className="flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded border border-[#042648]/18 bg-white shadow-xl">
        <div className="border-b border-[#042648]/12 px-4 py-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/48">
                {formatType(memory.type)} / {memory.visibility}
              </div>
              <h3 className="mt-1 text-lg font-bold text-[#042648]">User Memory</h3>
              <p className="mt-1 text-sm text-[#042648]/62">{formatTimestamp(memory.updated_at)}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-[#042648]/15 px-3 py-1.5 text-sm font-semibold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Close
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <div className="mb-4 flex flex-wrap gap-2 text-xs font-semibold text-[#042648]/58">
            <span className="rounded bg-[#FFF6EA] px-2 py-0.5">{memory.status}</span>
            <span className="rounded bg-[#FFF6EA] px-2 py-0.5">{memory.sensitivity}</span>
            <span className="rounded bg-[#FFF6EA] px-2 py-0.5">
              {Math.round(memory.confidence * 100)}% confidence
            </span>
          </div>

          {memory.curated_summary && (
            <section className="mb-4">
              <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/48">
                User Visible Summary
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#042648]/82">
                {memory.curated_summary}
              </p>
            </section>
          )}

          <section>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/48">
              Raw Summary
            </div>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[#042648]/82">
              {memory.summary}
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

function CompactMemory({ memory }: { memory: UserMemory }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-bold text-[#042648]">{formatType(memory.type)}</span>
        <StatusBadge status={memory.status} />
      </div>
      <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-[#042648]/70">
        {memory.curated_summary || memory.summary}
      </p>
    </div>
  );
}

function LiveCandidateCard({ candidate, index }: { candidate: LiveCandidate; index: number }) {
  return (
    <article className="rounded border border-[#042648]/12 bg-white px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#042648] text-xs font-bold text-white">
            {index}
          </span>
          <div>
            <div className="text-sm font-bold">{formatType(candidate.type)}</div>
            <div className="text-xs text-[#042648]/55">{formatTime(candidate.capturedAt)}</div>
          </div>
        </div>
        <StatusBadge status={candidate.status || 'candidate'} />
      </div>
      <p className="mt-3 rounded bg-[#F8FAF7] px-3 py-2 text-xs leading-relaxed text-[#042648]/66">
        {candidate.message}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-[#042648]/78">
        {candidate.curated_summary || candidate.summary}
      </p>
      {typeof candidate.confidence === 'number' && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#042648]/10">
          <div
            className="h-full rounded-full bg-[#2F8F5B]"
            style={{ width: `${Math.max(8, Math.round(candidate.confidence * 100))}%` }}
          />
        </div>
      )}
    </article>
  );
}

function KnowledgeCard({ chunk, onOpen }: { chunk: KnowledgeChunk; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="rounded border border-[#042648]/12 bg-white px-3 py-3 text-left transition hover:border-[#042648]/35 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-[#042648]/30"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold">{chunk.title}</div>
          <div className="mt-1 text-xs text-[#042648]/55">{chunk.section}</div>
        </div>
        <span className="rounded-full border border-[#042648]/15 bg-[#F8FAF7] px-2 py-0.5 text-[11px] font-semibold text-[#042648]/60">
          {chunk.language || 'multi'}
        </span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-[#042648]/78">{chunk.preview}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {chunk.topics.slice(0, 5).map((topic) => (
          <span
            key={`${chunk.id}-${topic}`}
            className="rounded bg-[#FFF6EA] px-2 py-0.5 text-[11px] font-semibold text-[#042648]/58"
          >
            {formatType(topic)}
          </span>
        ))}
      </div>
      <div className="mt-3 text-xs font-bold text-[#042648]/55">Open full text</div>
    </button>
  );
}

function KnowledgeReader({ chunk, onClose }: { chunk: KnowledgeChunk; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#042648]/35 px-4 py-6">
      <div className="flex max-h-full w-full max-w-4xl flex-col overflow-hidden rounded border border-[#042648]/18 bg-white shadow-xl">
        <div className="border-b border-[#042648]/12 px-4 py-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/48">
                {formatType(chunk.domain)} / {chunk.language || 'multi'}
              </div>
              <h3 className="mt-1 text-lg font-bold text-[#042648]">{chunk.title}</h3>
              <p className="mt-1 text-sm text-[#042648]/62">{chunk.section}</p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-[#042648]/15 px-3 py-1.5 text-sm font-semibold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Close
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <div className="mb-4 flex flex-wrap gap-1">
            {chunk.topics.map((topic) => (
              <span
                key={`${chunk.id}-reader-${topic}`}
                className="rounded bg-[#FFF6EA] px-2 py-0.5 text-[11px] font-semibold text-[#042648]/58"
              >
                {formatType(topic)}
              </span>
            ))}
          </div>

          <div className="whitespace-pre-wrap text-sm leading-7 text-[#042648]/82">
            {chunk.content}
          </div>

          {chunk.source_notes && (
            <div className="mt-5 rounded border border-[#042648]/10 bg-[#F8FAF7] px-3 py-3">
              <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/48">
                Source Notes
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#042648]/70">
                {chunk.source_notes}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Constellation({
  memories,
  onOpenMemory,
}: {
  memories: UserMemory[];
  onOpenMemory: (memory: UserMemory) => void;
}) {
  const nodes = useMemo(() => buildConstellationNodes(memories), [memories]);
  const groups = useMemo(() => Array.from(new Set(memories.map((memory) => memory.type))), [memories]);

  return (
    <div className="relative h-full min-h-[480px] w-full overflow-hidden">
      <svg className="h-full w-full" viewBox="0 0 900 560" role="img" aria-label="Data brain constellation">
        <rect width="900" height="560" fill="#FFFFFF" />
        {groups.map((type, index) => {
          const color = getTypeColor(index);
          const center = groupCenter(index, groups.length);
          return (
            <g key={`group-${type}`}>
              <circle
                cx={center.x}
                cy={center.y}
                r="52"
                fill={color.bg}
                stroke={color.border}
                strokeWidth="2"
              />
              <text
                x={center.x}
                y={center.y + 4}
                textAnchor="middle"
                className="fill-[#042648] text-[12px] font-bold"
              >
                {formatType(type)}
              </text>
            </g>
          );
        })}

        {nodes.map((node) => (
          <line
            key={`line-${node.memory.id}`}
            x1={node.group.x}
            y1={node.group.y}
            x2={node.x}
            y2={node.y}
            stroke={node.color.border}
            strokeOpacity="0.35"
            strokeWidth="1.5"
          />
        ))}

        {nodes.map((node) => (
          <g
            key={node.memory.id}
            role="button"
            tabIndex={0}
            className="cursor-pointer outline-none"
            onClick={() => onOpenMemory(node.memory)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onOpenMemory(node.memory);
              }
            }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              fill={node.color.bg}
              stroke={node.color.border}
              strokeWidth="2"
            />
            <title>{`${formatType(node.memory.type)} - ${node.memory.curated_summary || node.memory.summary}`}</title>
            <text
              x={node.x}
              y={node.y + 4}
              textAnchor="middle"
              className="pointer-events-none fill-[#042648] text-[11px] font-bold"
            >
              {Math.round(node.memory.confidence * 100)}%
            </text>
          </g>
        ))}
      </svg>

      <div className="absolute bottom-3 left-3 right-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {nodes.slice(0, 6).map((node) => (
          <button
            key={`legend-${node.memory.id}`}
            type="button"
            onClick={() => onOpenMemory(node.memory)}
            className="rounded border border-[#042648]/10 bg-white/95 px-3 py-2 text-left text-xs transition hover:border-[#042648]/35"
          >
            <div className="font-bold text-[#042648]">{formatType(node.memory.type)}</div>
            <div className="mt-1 line-clamp-2 text-[#042648]/65">
              {node.memory.curated_summary || node.memory.summary}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function KnowledgeConstellation({
  chunks,
  onOpenChunk,
}: {
  chunks: KnowledgeChunk[];
  onOpenChunk: (chunk: KnowledgeChunk) => void;
}) {
  const nodes = useMemo(() => buildKnowledgeConstellationNodes(chunks), [chunks]);
  const groups = useMemo(() => Array.from(new Set(chunks.map((chunk) => chunk.domain))), [chunks]);

  return (
    <div className="relative h-full min-h-[520px] w-full overflow-hidden">
      <svg className="h-full w-full" viewBox="0 0 960 600" role="img" aria-label="Knowledge brain constellation">
        <rect width="960" height="600" fill="#FFFFFF" />
        {groups.map((domain, index) => {
          const color = getTypeColor(index);
          const center = knowledgeGroupCenter(index, groups.length);
          const count = chunks.filter((chunk) => chunk.domain === domain).length;
          return (
            <g key={`knowledge-group-${domain}`}>
              <circle
                cx={center.x}
                cy={center.y}
                r="58"
                fill={color.bg}
                stroke={color.border}
                strokeWidth="2"
              />
              <text
                x={center.x}
                y={center.y - 3}
                textAnchor="middle"
                className="fill-[#042648] text-[12px] font-bold"
              >
                {formatType(domain)}
              </text>
              <text
                x={center.x}
                y={center.y + 15}
                textAnchor="middle"
                className="fill-[#042648]/70 text-[11px]"
              >
                {count} chunks
              </text>
            </g>
          );
        })}

        {nodes.map((node) => (
          <line
            key={`knowledge-line-${node.chunk.id}`}
            x1={node.group.x}
            y1={node.group.y}
            x2={node.x}
            y2={node.y}
            stroke={node.color.border}
            strokeOpacity="0.28"
            strokeWidth="1.4"
          />
        ))}

        {nodes.map((node) => (
          <g
            key={node.chunk.id}
            role="button"
            tabIndex={0}
            className="cursor-pointer outline-none"
            onClick={() => onOpenChunk(node.chunk)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onOpenChunk(node.chunk);
              }
            }}
          >
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              fill={node.color.bg}
              stroke={node.color.border}
              strokeWidth="1.8"
            />
            <title>{`${node.chunk.title} - ${node.chunk.section}`}</title>
          </g>
        ))}
      </svg>

      <div className="absolute bottom-3 left-3 right-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {nodes.slice(0, 6).map((node) => (
          <button
            key={`knowledge-legend-${node.chunk.id}`}
            type="button"
            onClick={() => onOpenChunk(node.chunk)}
            className="rounded border border-[#042648]/10 bg-white/95 px-3 py-2 text-left text-xs transition hover:border-[#042648]/35"
          >
            <div className="font-bold text-[#042648]">{node.chunk.title}</div>
            <div className="mt-1 text-[#042648]/55">{formatType(node.chunk.domain)} / {node.chunk.section}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isActive = status === 'active';
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
        isActive
          ? 'border-[#1F7A4D]/25 bg-[#EAF7EF] text-[#145C39]'
          : 'border-[#B88700]/35 bg-[#FFF6EA] text-[#7A5600]'
      }`}
    >
      {status}
    </span>
  );
}

function extractLiveCandidates(sessions: DebugSession[]): LiveCandidate[] {
  return sessions.flatMap((session) => {
    const capturedAt = session.completedAt || session.startedAt;
    const candidates = session.trace?.steps.flatMap((step) => getCandidates(step.payload)) || [];
    return candidates.map((candidate, index) => ({
      id: stringValue(candidate.id) || `${session.id}-${index}`,
      message: session.userMessage,
      type: stringValue(candidate.type) || 'memory',
      summary: stringValue(candidate.summary),
      curated_summary: stringValue(candidate.curated_summary) || stringValue(candidate.summary),
      status: stringValue(candidate.status) || 'candidate',
      confidence: typeof candidate.confidence === 'number' ? candidate.confidence : null,
      capturedAt,
    }));
  }).reverse();
}

function getCandidates(payload: Record<string, unknown>): Record<string, unknown>[] {
  const value = payload.candidates;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item));
}

function groupMemoriesByType(memories: UserMemory[]): [string, UserMemory[]][] {
  const grouped = new Map<string, UserMemory[]>();
  memories.forEach((memory) => {
    const rows = grouped.get(memory.type) || [];
    rows.push(memory);
    grouped.set(memory.type, rows);
  });
  return Array.from(grouped.entries());
}

function groupKnowledgeByDomain(chunks: KnowledgeChunk[]): [string, KnowledgeChunk[]][] {
  const grouped = new Map<string, KnowledgeChunk[]>();
  chunks.forEach((chunk) => {
    const rows = grouped.get(chunk.domain) || [];
    rows.push(chunk);
    grouped.set(chunk.domain, rows);
  });
  return Array.from(grouped.entries());
}

function buildConstellationNodes(memories: UserMemory[]) {
  const groups = Array.from(new Set(memories.map((memory) => memory.type)));
  return memories.map((memory, index) => {
    const groupIndex = groups.indexOf(memory.type);
    const center = groupCenter(groupIndex, groups.length);
    const sameTypeIndex = memories.slice(0, index).filter((item) => item.type === memory.type).length;
    const angle = sameTypeIndex * 1.7 + groupIndex * 0.6;
    const distance = 84 + (sameTypeIndex % 4) * 26;

    return {
      memory,
      group: center,
      x: center.x + Math.cos(angle) * distance,
      y: center.y + Math.sin(angle) * distance,
      radius: 16 + Math.min(12, memory.confidence * 16),
      color: getTypeColor(groupIndex),
    };
  });
}

function buildKnowledgeConstellationNodes(chunks: KnowledgeChunk[]) {
  const groups = Array.from(new Set(chunks.map((chunk) => chunk.domain)));
  return chunks.map((chunk, index) => {
    const groupIndex = groups.indexOf(chunk.domain);
    const center = knowledgeGroupCenter(groupIndex, groups.length);
    const sameDomainIndex = chunks.slice(0, index).filter((item) => item.domain === chunk.domain).length;
    const angle = sameDomainIndex * 1.32 + groupIndex * 0.5;
    const distance = 86 + (sameDomainIndex % 6) * 22;

    return {
      chunk,
      group: center,
      x: center.x + Math.cos(angle) * distance,
      y: center.y + Math.sin(angle) * distance,
      radius: 8 + Math.min(9, chunk.topics.length * 1.8),
      color: getTypeColor(groupIndex),
    };
  });
}

function groupCenter(index: number, total: number) {
  const centerX = 450;
  const centerY = 260;
  if (total <= 1) return { x: centerX, y: centerY };

  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const radiusX = 245;
  const radiusY = 145;
  return {
    x: centerX + Math.cos(angle) * radiusX,
    y: centerY + Math.sin(angle) * radiusY,
  };
}

function knowledgeGroupCenter(index: number, total: number) {
  const centerX = 480;
  const centerY = 285;
  if (total <= 1) return { x: centerX, y: centerY };

  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const radiusX = 285;
  const radiusY = 175;
  return {
    x: centerX + Math.cos(angle) * radiusX,
    y: centerY + Math.sin(angle) * radiusY,
  };
}

function getTypeColor(index: number) {
  return TYPE_COLORS[index % TYPE_COLORS.length];
}

function formatType(value: string): string {
  return value
    .replaceAll('_', ' ')
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatTimestamp(value?: string): string {
  if (!value) return 'Recently updated';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Recently updated';
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

function formatTime(value: Date): string {
  return value.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}
