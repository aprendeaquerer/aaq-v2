'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import * as api from '@/lib/api';
import { API_URL } from '@/lib/constants';
import { useLanguage } from '@/hooks/useLanguage';
import { personalityTestConversations } from '@/data/personalityTestConversations';
import type { BotDebugStep, ChatResponse, DebugSession, KnowledgeChunk, UserMemory, UserProfile } from '@/lib/types';

type BrainMode = 'text' | 'constellation';
export type BrainTab = 'data' | 'knowledge' | 'live' | 'new-tests';

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


interface ActualSimulationTurn {
  prompt: string;
  response: ChatResponse;
}

interface ActualSimulationRun {
  status: 'running' | 'complete' | 'error';
  email: string;
  userId?: string;
  startedAt: Date;
  completedAt?: Date;
  profile?: UserProfile;
  selfTestResult?: ChatResponse;
  setupResponses: ChatResponse[];
  turns: ActualSimulationTurn[];
  memories: UserMemory[];
  error?: string;
}

// Live-conversation mode: an AI plays the user persona and talks to the real bot.
const LIVE_MAX_TURNS = 8;

interface LiveSimulationTurn {
  persona: string; // the AI-generated user message
  response: ChatResponse; // the real bot reply (+ debug)
}

interface LiveSimulationRun {
  status: 'running' | 'complete' | 'error';
  email: string;
  userId?: string;
  startedAt: Date;
  completedAt?: Date;
  opening?: string; // bot's opening line
  profile?: UserProfile;
  turns: LiveSimulationTurn[];
  memories: UserMemory[];
  error?: string;
}

interface PublishedQaRun {
  runId: string;
  startedAt?: string;
  completedAt: string;
  apiUrl?: string;
  focus?: string;
  instructions?: string;
  permanentPath?: string;
  patchedAt?: string;
  patchNotes?: string;
  aggregate: {
    conversationCount: number;
    failedConversationCount: number;
    turnCount: number;
    aiErrorTurnCount?: number;
    plannerErrorTurnCount?: number;
    knowledgeTurnCount?: number;
    noKnowledgeTurnCount?: number;
    memoryRetrievedTurnCount?: number;
    memoryCapturedTurnCount?: number;
    profileCapturedTurnCount?: number;
    averageKnowledgeChunks?: number;
    storedAttachmentStyleCount?: number;
    storedPartnerAttachmentStyleCount?: number;
    storedMemoryCount?: number;
    storedProfileNameCount?: number;
  };
  conversations: PublishedQaConversation[];
}

interface PublishedQaConversation {
  id: string;
  title: string;
  kind?: string;
  purpose?: string;
  qaNote?: string;
  email: string;
  expectedAttachmentStyle?: string;
  openingPrompt?: string;
  profileSeed: Record<string, unknown>;
  setupMessage?: string;
  setupResponses?: unknown;
  turns: PublishedQaTurn[];
  finalMemories?: UserMemory[];
  storedMemories?: UserMemory[];
  storedProfile?: UserProfile;
  storedMemoryResponse?: unknown;
  error?: string | null;
}

interface PublishedQaTurn {
  prompt: string;
  type?: string;
  message?: string;
  debug?: unknown;
  reasoning_summary?: string | null;
  intent?: string | null;
  routed_domains?: string[] | null;
  knowledge?: {
    count: number;
    detail: string;
    chunks: Array<{
      id: string;
      title: string;
      section: string;
      domain: string;
      score: number;
      preview: string;
    }>;
  };
  memory_retrieval?: {
    count: number;
    detail: string;
    memories: Array<{
      id: string;
      type: string;
      confidence: number;
      status: string;
      summary: string;
    }>;
  };
  memory_capture?: {
    count: number;
    detail: string;
    candidates: Array<{
      id: string;
      type: string;
      confidence: number;
      status: string;
      summary: string;
    }>;
  };
  profile_capture?: {
    updates?: Record<string, unknown>;
    error?: string | null;
  };
  ai_error?: string | null;
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
  const [actualRuns, setActualRuns] = useState<Record<string, ActualSimulationRun>>({});
  const [isRunningAllPersonalityTests, setIsRunningAllPersonalityTests] = useState(false);
  const [liveRuns, setLiveRuns] = useState<Record<string, LiveSimulationRun>>({});
  const [publishedQaRun, setPublishedQaRun] = useState<PublishedQaRun | null>(null);
  const [publishedQaError, setPublishedQaError] = useState<string | null>(null);

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
    if (activeTab !== 'new-tests') return;

    let isCancelled = false;

    fetch('/qa/personality-latest.json', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`Published QA run failed to load (${response.status})`);
        return response.json() as Promise<PublishedQaRun>;
      })
      .then((run) => {
        if (!isCancelled) {
          setPublishedQaRun(run);
          setPublishedQaError(null);
        }
      })
      .catch((loadError) => {
        if (!isCancelled) {
          setPublishedQaRun(null);
          setPublishedQaError(loadError instanceof Error ? loadError.message : 'Published QA run failed to load');
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [activeTab]);

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

  const runPersonalityScenario = async (conversation: (typeof personalityTestConversations)[number]) => {
    const startedAt = new Date();
    const email = `qa+${conversation.id.slice(0, 24)}-${startedAt.getTime()}@aprendeaquerer.com`;
    setActualRuns((current) => ({
      ...current,
      [conversation.id]: {
        status: 'running',
        email,
        startedAt,
        setupResponses: [],
        turns: [],
        memories: [],
      },
    }));

    try {
      const result = await runActualPersonalitySimulation(conversation, email);
      setActualRuns((current) => ({
        ...current,
        [conversation.id]: result,
      }));
    } catch (error) {
      setActualRuns((current) => ({
        ...current,
        [conversation.id]: {
          status: 'error',
          email,
          startedAt,
          completedAt: new Date(),
          setupResponses: [],
          turns: [],
          memories: [],
          error: error instanceof Error ? error.message : 'Simulation failed',
        },
      }));
    }
  };

  const runAllPersonalityScenarios = async () => {
    setIsRunningAllPersonalityTests(true);
    try {
      for (const conversation of personalityTestConversations) {
        await runPersonalityScenario(conversation);
      }
    } finally {
      setIsRunningAllPersonalityTests(false);
    }
  };

  const runLivePersonalityScenario = async (conversation: (typeof personalityTestConversations)[number]) => {
    const startedAt = new Date();
    const email = `qa-live+${conversation.id.slice(0, 20)}-${startedAt.getTime()}@aprendeaquerer.com`;
    setLiveRuns((current) => ({
      ...current,
      [conversation.id]: { status: 'running', email, startedAt, turns: [], memories: [] },
    }));

    try {
      const result = await runLivePersonalitySimulation(conversation, email, (partial) => {
        setLiveRuns((current) => ({ ...current, [conversation.id]: partial }));
      });
      setLiveRuns((current) => ({ ...current, [conversation.id]: result }));
    } catch (error) {
      setLiveRuns((current) => ({
        ...current,
        [conversation.id]: {
          status: 'error',
          email,
          startedAt,
          completedAt: new Date(),
          turns: [],
          memories: [],
          error: error instanceof Error ? error.message : 'Live simulation failed',
        },
      }));
    }
  };

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

  if (activeTab === 'new-tests') {
    return (
      <BrainShell
        title="New Personality Test"
        subtitle="New simulated conversations against Eldric's current personality and knowledge."
        countLabel={`${personalityTestConversations.length} personality threads`}
        openHref="/brain?tab=new-tests"
        standalone={standalone}
      >
        <div className="flex min-h-0 flex-1 flex-col gap-4">
          <>
              <LatestQaRunPanel publishedRun={publishedQaRun} loadError={publishedQaError} />

              <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[330px_minmax(0,1fr)]">
                <aside className="min-h-0 overflow-y-auto rounded border border-[#042648]/12 bg-white">
                  <div className="border-b border-[#042648]/10 px-3 py-3">
                    <h3 className="text-sm font-bold text-[#042648]">Conversation Threads</h3>
                    <p className="mt-1 text-xs text-[#042648]/60">
                      {personalityTestConversations.length} new personas across ages, genders, and relationship contexts.
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
                    <PersonalityThreadReader
                      conversation={selectedPersonalityTest}
                      actualRun={actualRuns[selectedPersonalityTest.id]}
                      liveRun={liveRuns[selectedPersonalityTest.id]}
                      isRunningAll={isRunningAllPersonalityTests}
                      onRun={() => void runPersonalityScenario(selectedPersonalityTest)}
                      onRunAll={() => void runAllPersonalityScenarios()}
                      onRunLive={() => void runLivePersonalityScenario(selectedPersonalityTest)}
                    />
                  )}
                </div>
              </div>
          </>
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
                        {formatKnowledgeGroup(domain)}
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
                    <div className="space-y-3 border-t border-[#042648]/10 bg-[#FFFDF8] p-3">
                      {groupKnowledgeByDocument(rows).map(([title, docChunks]) => (
                        <DocumentGroup
                          key={`${domain}-${title}`}
                          title={title}
                          chunks={docChunks}
                          onOpen={setSelectedKnowledgeChunk}
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

function AttachmentQaUsersPanel({
  publishedRun,
  loadError,
  selectedUserId,
  onSelectUser,
}: {
  publishedRun: PublishedQaRun | null;
  loadError: string | null;
  selectedUserId: string;
  onSelectUser: (id: string) => void;
}) {
  if (loadError) {
    return (
      <div className="rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-3 py-2 text-sm text-[#7A1F1F]">
        {loadError}
      </div>
    );
  }

  if (!publishedRun) {
    return (
      <div className="rounded border border-[#042648]/12 bg-white px-4 py-6 text-sm text-[#042648]/62">
        Loading attachment users...
      </div>
    );
  }

  const selectedConversation =
    publishedRun.conversations.find((conversation) => conversation.id === selectedUserId) ||
    publishedRun.conversations[0];

  return (
    <section className="min-h-0 overflow-y-auto rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Attachment Users
            </div>
            <h3 className="mt-1 text-base font-bold text-[#042648]">{publishedRun.runId}</h3>
            <p className="mt-1 text-xs leading-5 text-[#042648]/58">
              Per-user Data Brain snapshot plus the live profile, memory, and knowledge fill on every test turn.
            </p>
          </div>
          <a
            href="/qa/attachment-style-latest.json"
            target="_blank"
            rel="noreferrer"
            className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
          >
            Raw JSON
          </a>
        </div>
      </div>

      <div className="space-y-4 p-3">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4" role="tablist" aria-label="Attachment QA users">
          {publishedRun.conversations.map((conversation) => (
            <AttachmentQaUserTab
              key={conversation.id}
              conversation={conversation}
              isSelected={conversation.id === selectedConversation?.id}
              onSelect={() => onSelectUser(conversation.id)}
            />
          ))}
        </div>

        {selectedConversation && <AttachmentQaUserDetail conversation={selectedConversation} />}
      </div>
    </section>
  );
}

function AttachmentQaUserTab({
  conversation,
  isSelected,
  onSelect,
}: {
  conversation: PublishedQaConversation;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const name = getAttachmentQaDisplayName(conversation);
  const finalMemories = getPublishedMemories(conversation);
  const savedStyle = getPublishedProfileValue(conversation, 'attachment_style');
  const expectedStyle = conversation.expectedAttachmentStyle || 'n/a';
  const knowledgeTurns = conversation.turns.filter((turn) => getPublishedKnowledge(turn).count > 0).length;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isSelected}
      onClick={onSelect}
      className={`rounded border px-3 py-3 text-left transition ${
        isSelected
          ? 'border-[#042648] bg-[#042648] text-white'
          : 'border-[#042648]/10 bg-[#FFFDF8] text-[#042648] hover:border-[#042648]/25 hover:bg-[#F8FAF7]'
      }`}
    >
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] opacity-60">{expectedStyle}</div>
      <div className="mt-1 text-sm font-bold leading-snug">{name}</div>
      <div className="mt-2 flex flex-wrap gap-1 text-[11px] font-semibold opacity-70">
        <span>{conversation.turns.length} turns</span>
        <span>/</span>
        <span>K {knowledgeTurns}</span>
        <span>/</span>
        <span>M {finalMemories.length}</span>
      </div>
      <div className="mt-2 text-[11px] font-bold opacity-80">Saved: {savedStyle}</div>
    </button>
  );
}

function AttachmentQaUserDetail({ conversation }: { conversation: PublishedQaConversation }) {
  const finalMemories = getPublishedMemories(conversation);
  const knowledgeTurns = conversation.turns.filter((turn) => getPublishedKnowledge(turn).count > 0).length;
  const memoryCaptureTurns = conversation.turns.filter((turn) => getPublishedMemoryCapture(turn).count > 0).length;
  const memoryRetrievalTurns = conversation.turns.filter((turn) => getPublishedMemoryRetrieval(turn).count > 0).length;
  const profileUpdateTurns = conversation.turns.filter((turn) => getProfileUpdateEntries(turn).length > 0).length;
  const profileUpdateCount = conversation.turns.reduce((sum, turn) => sum + getProfileUpdateEntries(turn).length, 0);
  const savedStyle = getPublishedProfileValue(conversation, 'attachment_style');
  const expectedStyle = conversation.expectedAttachmentStyle || 'n/a';
  const styleMatches = savedStyle !== 'none' && expectedStyle !== 'n/a' && savedStyle === expectedStyle;

  return (
    <article className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-base font-bold text-[#042648]">{getAttachmentQaDisplayName(conversation)}</h4>
            <p className="mt-1 text-xs leading-5 text-[#042648]/58">
              {conversation.email} / {conversation.openingPrompt || conversation.title}
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            <StylePill label={`Expected ${expectedStyle}`} />
            <StylePill label={`Saved ${savedStyle}`} tone={styleMatches ? 'good' : savedStyle === 'none' ? 'bad' : 'neutral'} />
          </div>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          <QaMiniMetric label="Turns" value={conversation.turns.length} />
          <QaMiniMetric label="Knowledge Turns" value={`${knowledgeTurns}/${conversation.turns.length}`} />
          <QaMiniMetric label="Profile Updates" value={`${profileUpdateCount} in ${profileUpdateTurns} turns`} />
          <QaMiniMetric label="Memory Captures" value={`${memoryCaptureTurns}/${conversation.turns.length}`} />
          <QaMiniMetric label="Memory Retrievals" value={`${memoryRetrievalTurns}/${conversation.turns.length}`} />
          <QaMiniMetric label="Final Memories" value={finalMemories.length} />
        </div>
      </div>

      <div className="grid gap-4 p-3 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
        <AttachmentDataBrainSnapshot conversation={conversation} />
        <AttachmentLiveFillTimeline conversation={conversation} />
      </div>
    </article>
  );
}

function AttachmentDataBrainSnapshot({ conversation }: { conversation: PublishedQaConversation }) {
  const finalMemories = getPublishedMemories(conversation);

  return (
    <div className="space-y-4">
      <section className="rounded border border-[#042648]/10 bg-white">
        <div className="border-b border-[#042648]/10 px-3 py-2">
          <h5 className="text-sm font-bold text-[#042648]">Data Brain Profile</h5>
          <p className="mt-1 text-xs text-[#042648]/58">Final stable profile saved after this test conversation.</p>
        </div>
        <ProfileFieldGrid profile={conversation.storedProfile || null} />
      </section>

      <section className="rounded border border-[#042648]/10 bg-white">
        <div className="border-b border-[#042648]/10 px-3 py-2">
          <h5 className="text-sm font-bold text-[#042648]">Data Brain Memories</h5>
          <p className="mt-1 text-xs text-[#042648]/58">Final user memories visible after the run completed.</p>
        </div>
        <FinalMemoryGrid memories={finalMemories} />
      </section>
    </div>
  );
}

function ProfileFieldGrid({ profile }: { profile: UserProfile | null }) {
  const rows = profile ? buildProfileRows(profile) : [];

  return (
    <div className="grid gap-2 p-3 md:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded bg-[#F8FAF7] px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">{label}</div>
          <div className="mt-1 break-words text-xs font-bold text-[#042648]/82">{value}</div>
        </div>
      ))}
      {rows.length === 0 && (
        <p className="text-sm text-[#042648]/60">No stable profile fields were saved for this user.</p>
      )}
    </div>
  );
}

function FinalMemoryGrid({ memories }: { memories: UserMemory[] }) {
  return (
    <div className="grid gap-2 p-3 md:grid-cols-2">
      {memories.map((memory) => (
        <div key={memory.id} className="rounded bg-[#F8FAF7] px-3 py-2 text-xs text-[#042648]/70">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="font-bold text-[#042648]">{formatType(memory.type)}</div>
            <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold text-[#042648]/55">
              {Math.round(memory.confidence * 100)}%
            </span>
          </div>
          <div className="mt-1 text-[11px] font-semibold text-[#042648]/50">
            {memory.status} / {memory.sensitivity}
          </div>
          <p className="mt-1 leading-5">{memory.curated_summary || memory.summary}</p>
        </div>
      ))}
      {memories.length === 0 && (
        <p className="text-sm text-[#042648]/60">No final memories were stored for this user.</p>
      )}
    </div>
  );
}

function AttachmentLiveFillTimeline({ conversation }: { conversation: PublishedQaConversation }) {
  const knowledgeChunks = conversation.turns.reduce((sum, turn) => sum + getPublishedKnowledge(turn).count, 0);
  const capturedMemories = conversation.turns.reduce((sum, turn) => sum + getPublishedMemoryCapture(turn).count, 0);
  const retrievedMemories = conversation.turns.reduce((sum, turn) => sum + getPublishedMemoryRetrieval(turn).count, 0);
  const profileUpdates = conversation.turns.reduce((sum, turn) => sum + getProfileUpdateEntries(turn).length, 0);

  return (
    <section className="rounded border border-[#042648]/10 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <h5 className="text-sm font-bold text-[#042648]">Live Fill Timeline</h5>
        <p className="mt-1 text-xs text-[#042648]/58">
          Turn-by-turn capture into profile/memory and retrieval from memory/knowledge.
        </p>
        <div className="mt-2 grid gap-2 sm:grid-cols-4">
          <QaMiniMetric label="Profile" value={profileUpdates} />
          <QaMiniMetric label="Captured M" value={capturedMemories} />
          <QaMiniMetric label="Retrieved M" value={retrievedMemories} />
          <QaMiniMetric label="Chunks" value={knowledgeChunks} />
        </div>
      </div>
      <div className="space-y-3 p-3">
        {conversation.turns.map((turn, index) => (
          <LiveFillTurn key={`${conversation.id}-live-${index}`} turn={turn} index={index} />
        ))}
      </div>
    </section>
  );
}

function LiveFillTurn({ turn, index }: { turn: PublishedQaTurn; index: number }) {
  const knowledge = getPublishedKnowledge(turn);
  const memoryRetrieval = getPublishedMemoryRetrieval(turn);
  const memoryCapture = getPublishedMemoryCapture(turn);
  const profileCapture = getPublishedProfileCapture(turn);
  const profileUpdates = getProfileUpdateEntries(turn);
  const routedDomains = Array.isArray(turn.routed_domains) ? turn.routed_domains : [];

  return (
    <article className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Turn {index + 1}
            </div>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">{turn.prompt}</p>
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            <LiveFillPill label={`P ${profileUpdates.length}`} tone={profileUpdates.length > 0 ? 'good' : 'neutral'} />
            <LiveFillPill label={`M+ ${memoryCapture.count}`} tone={memoryCapture.count > 0 ? 'good' : 'neutral'} />
            <LiveFillPill label={`M ${memoryRetrieval.count}`} tone={memoryRetrieval.count > 0 ? 'good' : 'neutral'} />
            <LiveFillPill label={`K ${knowledge.count}`} tone={knowledge.count > 0 ? 'good' : 'bad'} />
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1 text-[11px] font-semibold text-[#042648]/52">
          <span>Intent: {turn.intent || 'none'}</span>
          <span>/</span>
          <span>Domains: {routedDomains.join(', ') || 'none'}</span>
        </div>
      </div>

      <div className="space-y-3 p-3">
        <ProfileUpdateList updates={profileUpdates} error={profileCapture.error || null} />

        <LiveFillCollection
          title="Memory Capture"
          empty="No memory candidates were written on this turn."
          items={memoryCapture.candidates.map((candidate) => ({
            id: candidate.id,
            title: formatType(candidate.type),
            meta: `${candidate.status} / ${Math.round(candidate.confidence * 100)}%`,
            body: candidate.summary,
          }))}
        />

        <LiveFillCollection
          title="Memory Retrieval"
          empty="No prior memories were retrieved on this turn."
          items={memoryRetrieval.memories.map((memory) => ({
            id: memory.id,
            title: formatType(memory.type),
            meta: `${memory.status} / ${Math.round(memory.confidence * 100)}%`,
            body: memory.summary,
          }))}
        />

        <LiveFillCollection
          title="Knowledge Chunks"
          empty="No knowledge chunks were used on this turn."
          items={knowledge.chunks.map((chunk) => ({
            id: chunk.id,
            title: chunk.title,
            meta: `${formatKnowledgeGroup(chunk.domain)} / ${chunk.section} / score ${chunk.score}`,
            body: chunk.preview,
          }))}
        />
      </div>
    </article>
  );
}

function LiveFillPill({ label, tone }: { label: string; tone: 'good' | 'bad' | 'neutral' }) {
  const classes =
    tone === 'good'
      ? 'bg-[#EAF7EF] text-[#165A38]'
      : tone === 'bad'
        ? 'bg-[#FFF0F0] text-[#7A1F1F]'
        : 'bg-white text-[#042648]/55';
  return <span className={`rounded px-2 py-1 text-[10px] font-bold ${classes}`}>{label}</span>;
}

function ProfileUpdateList({ updates, error }: { updates: Array<[string, unknown]>; error: string | null }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">Profile Capture</div>
      {error && <p className="mt-1 text-xs leading-5 text-[#7A1F1F]">{error}</p>}
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {updates.map(([key, value]) => (
          <div key={key} className="rounded bg-white px-2 py-2 text-xs">
            <div className="font-bold text-[#042648]">{formatType(key)}</div>
            <div className="mt-1 break-words leading-5 text-[#042648]/70">{formatPublishedValue(value)}</div>
          </div>
        ))}
        {updates.length === 0 && !error && (
          <p className="text-xs text-[#042648]/55">No stable profile field changed on this turn.</p>
        )}
      </div>
    </div>
  );
}

function LiveFillCollection({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: Array<{ id: string; title: string; meta: string; body: string }>;
}) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">{title}</div>
        <span className="rounded bg-white px-2 py-0.5 text-[10px] font-bold text-[#042648]/50">
          {items.length}
        </span>
      </div>
      <div className="mt-2 grid gap-2">
        {items.map((item, itemIndex) => (
          <div key={`${item.id}-${itemIndex}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/70">
            <div className="font-bold text-[#042648]">{item.title}</div>
            <div className="mt-1 text-[11px] font-semibold text-[#042648]/50">{item.meta}</div>
            <p className="mt-1 leading-5">{item.body}</p>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-[#042648]/55">{empty}</p>}
      </div>
    </div>
  );
}

function AttachmentStyleQaDashboard({
  publishedRun,
  loadError,
  onOpenDetails,
}: {
  publishedRun: PublishedQaRun | null;
  loadError: string | null;
  onOpenDetails: () => void;
}) {
  if (loadError) {
    return (
      <div className="rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-3 py-2 text-sm text-[#7A1F1F]">
        {loadError}
      </div>
    );
  }

  if (!publishedRun) {
    return (
      <div className="rounded border border-[#042648]/12 bg-white px-4 py-6 text-sm text-[#042648]/62">
        Loading attachment QA dashboard...
      </div>
    );
  }

  const summary = buildAttachmentQaSummary(publishedRun);

  return (
    <section className="min-h-0 overflow-y-auto rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Attachment QA Dashboard
            </div>
            <h3 className="mt-1 text-base font-bold text-[#042648]">{publishedRun.runId}</h3>
            <p className="mt-1 text-xs text-[#042648]/58">
              Completed {new Date(publishedRun.completedAt).toLocaleString()} / {publishedRun.apiUrl || 'Production API'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onOpenDetails}
              className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Full Details
            </button>
            <a
              href="/qa/attachment-style-latest.json"
              target="_blank"
              rel="noreferrer"
              className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
            >
              Raw JSON
            </a>
          </div>
        </div>
      </div>

      <div className="space-y-4 p-3">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <GraphMetric
            label="Knowledge coverage"
            value={`${summary.knowledgeTurns}/${summary.turns}`}
            tone={summary.knowledgeTurns === summary.turns ? 'good' : 'warn'}
            detail={`${summary.averageKnowledgeChunks.toFixed(1)} chunks average`}
            percent={percentage(summary.knowledgeTurns, summary.turns)}
          />
          <GraphMetric
            label="Attachment styles saved"
            value={`${summary.storedStyles}/${summary.conversations}`}
            tone={summary.storedStyles === summary.conversations ? 'good' : 'bad'}
            detail="profile attachment_style"
            percent={percentage(summary.storedStyles, summary.conversations)}
          />
          <GraphMetric
            label="Memory capture"
            value={`${summary.memoryCaptureTurns}/${summary.turns}`}
            tone="neutral"
            detail={`${summary.storedMemories} final memories`}
            percent={percentage(summary.memoryCaptureTurns, summary.turns)}
          />
          <GraphMetric
            label="Run health"
            value={`${summary.failures} failures`}
            tone={summary.failures === 0 ? 'good' : 'bad'}
            detail={`${summary.aiErrors} AI errors`}
            percent={summary.failures === 0 ? 100 : 0}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
          <section className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
            <div className="border-b border-[#042648]/10 px-3 py-2">
              <h4 className="text-sm font-bold text-[#042648]">Per-Person Capture</h4>
            </div>
            <div className="grid gap-3 p-3 md:grid-cols-2">
              {summary.people.map((person) => (
                <div key={person.id} className="rounded border border-[#042648]/10 bg-white px-3 py-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-bold text-[#042648]">{person.name}</div>
                      <div className="mt-1 text-xs text-[#042648]/55">{person.turns} turns</div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <StylePill label={`Expected ${person.expectedStyle || 'n/a'}`} />
                      <StylePill label={`Saved ${person.savedStyle || 'none'}`} tone={person.savedStyle ? 'good' : 'bad'} />
                    </div>
                  </div>

                  <div className="mt-3 space-y-2">
                    <ProgressRow label="Knowledge" value={person.knowledgeTurns} total={person.turns} />
                    <ProgressRow label="Mem capture" value={person.memoryCaptureTurns} total={person.turns} />
                    <ProgressRow label="Mem retrieval" value={person.memoryRetrievalTurns} total={person.turns} />
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded bg-[#F8FAF7] px-2 py-2">
                      <div className="font-bold text-[#042648]/48">Top Domain</div>
                      <div className="mt-1 font-semibold text-[#042648]">{formatKnowledgeGroup(person.topDomain)}</div>
                    </div>
                    <div className="rounded bg-[#F8FAF7] px-2 py-2">
                      <div className="font-bold text-[#042648]/48">Avg Chunks</div>
                      <div className="mt-1 font-semibold text-[#042648]">{person.averageChunks.toFixed(1)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <div className="space-y-4">
            <section className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
              <div className="border-b border-[#042648]/10 px-3 py-2">
                <h4 className="text-sm font-bold text-[#042648]">Knowledge Domains Used</h4>
              </div>
              <div className="space-y-2 p-3">
                {summary.domainCounts.map((row, index) => (
                  <HorizontalBar
                    key={row.label}
                    label={formatKnowledgeGroup(row.label)}
                    value={row.count}
                    max={summary.maxDomainCount}
                    color={getTypeColor(index).border}
                  />
                ))}
              </div>
            </section>

            <section className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
              <div className="border-b border-[#042648]/10 px-3 py-2">
                <h4 className="text-sm font-bold text-[#042648]">Most Reused Articles</h4>
              </div>
              <div className="space-y-2 p-3">
                {summary.topArticles.map((row, index) => (
                  <HorizontalBar
                    key={row.label}
                    label={row.label}
                    value={row.count}
                    max={summary.maxArticleCount}
                    color={getTypeColor(index + 1).border}
                  />
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}

function AttachmentStyleQaPanel({
  publishedRun,
  loadError,
}: {
  publishedRun: PublishedQaRun | null;
  loadError: string | null;
}) {
  const aggregate = publishedRun?.aggregate;
  const metrics = [
    ['Conversations', aggregate?.conversationCount ?? '-'],
    ['Turns', aggregate?.turnCount ?? '-'],
    ['Planner errors', aggregate?.plannerErrorTurnCount ?? '-'],
    ['Saved styles', aggregate?.storedAttachmentStyleCount ?? '-'],
    ['Saved memories', aggregate?.storedMemoryCount ?? '-'],
    ['Profiles named', aggregate?.storedProfileNameCount ?? '-'],
  ];

  return (
    <section className="rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Attachment Style Capture
            </div>
            <h3 className="mt-1 text-base font-bold text-[#042648]">
              {publishedRun?.runId || 'Loading attachment QA run'}
            </h3>
            <p className="mt-1 text-xs text-[#042648]/58">
              {publishedRun?.apiUrl || 'Production API'} / free conversation transcripts, stored profile, and stored memory
            </p>
          </div>
          <span className="rounded border border-[#042648]/15 bg-[#F8FAF7] px-2 py-1 text-[11px] font-bold text-[#042648]/65">
            Separate QA tab
          </span>
        </div>
        {publishedRun?.instructions && (
          <p className="mt-3 text-sm leading-6 text-[#042648]/72">{publishedRun.instructions}</p>
        )}
      </div>

      <div className="space-y-3 px-3 py-3">
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          {metrics.map(([label, value]) => (
            <div key={label} className="rounded bg-[#F8FAF7] px-3 py-2">
              <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
                {label}
              </div>
              <div className="mt-1 text-sm font-bold text-[#042648]">{value}</div>
            </div>
          ))}
        </div>

        <PublishedQaRunViewer
          run={publishedRun}
          loadError={loadError}
          title="Attachment Style Full Run"
          description="Complete simulated conversations plus the profile and memory the production bot saved for each QA user."
          latestHref="/qa/attachment-style-latest.json"
          permanentHref={publishedRun?.permanentPath || '/qa/attachment-style-latest.json'}
        />
      </div>
    </section>
  );
}

function LatestQaRunPanel({
  publishedRun,
  loadError,
}: {
  publishedRun: PublishedQaRun | null;
  loadError: string | null;
}) {
  const aggregate = publishedRun?.aggregate;
  const metrics = [
    ['Conversations', aggregate?.conversationCount ?? '-'],
    ['Turns', aggregate?.turnCount ?? '-'],
    ['AI errors', aggregate?.aiErrorTurnCount ?? '-'],
    ['Knowledge turns', aggregate ? `${aggregate.knowledgeTurnCount ?? 0}/${aggregate.turnCount}` : '-'],
    ['Memory turns', aggregate ? `${aggregate.memoryRetrievedTurnCount ?? 0}/${aggregate.turnCount}` : '-'],
    ['Memory captures', aggregate?.memoryCapturedTurnCount ?? '-'],
    ['Avg chunks', aggregate?.averageKnowledgeChunks ?? '-'],
    ['Failures', aggregate?.failedConversationCount ?? '-'],
  ];

  return (
    <section className="rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Latest Full QA Run
            </div>
            <h3 className="mt-1 text-base font-bold text-[#042648]">
              {publishedRun?.runId || 'Loading new personality run'}
            </h3>
            <p className="mt-1 text-xs text-[#042648]/58">
              {publishedRun?.apiUrl || 'Production API'} / generated personas talking to the real bot
            </p>
          </div>
          <span className="rounded border border-[#2F8F5B]/25 bg-[#EAF7EF] px-2 py-1 text-[11px] font-bold text-[#165A38]">
            Decision trace, not hidden chain-of-thought
          </span>
        </div>
        <p className="mt-3 text-sm leading-6 text-[#042648]/72">
          Each transcript shows the simulated user, Eldric&apos;s response, concise backend decision summary,
          routed domains, retrieved knowledge, and saved memory. Hidden chain-of-thought is not exposed.
        </p>
      </div>

      <div className="space-y-3 px-3 py-3">
        <div className="grid gap-2 md:grid-cols-4">
          {metrics.map(([label, value]) => (
            <div key={label} className="rounded bg-[#F8FAF7] px-3 py-2">
              <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
                {label}
              </div>
              <div className="mt-1 text-sm font-bold text-[#042648]">{value}</div>
            </div>
          ))}
        </div>

        <PublishedQaRunViewer
          run={publishedRun}
          loadError={loadError}
          permanentHref={publishedRun?.permanentPath || '/qa/personality-latest.json'}
        />
      </div>
    </section>
  );
}

function PublishedQaRunViewer({
  run,
  loadError,
  title = 'Published Full Run',
  description = 'Full prompts, bot replies, brain retrieval, memory retrieval, memory capture, and final memories.',
  latestHref = '/qa/personality-latest.json',
  permanentHref = '/qa/personality-latest.json',
}: {
  run: PublishedQaRun | null;
  loadError: string | null;
  title?: string;
  description?: string;
  latestHref?: string;
  permanentHref?: string;
}) {
  return (
    <div className="rounded border border-[#042648]/10 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#042648]/10 px-3 py-2">
        <div>
          <h4 className="text-sm font-bold text-[#042648]">{title}</h4>
          <p className="mt-1 text-xs text-[#042648]/60">{description}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={latestHref}
            target="_blank"
            rel="noreferrer"
            className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
          >
            Open raw JSON
          </a>
          <a
            href={permanentHref}
            target="_blank"
            rel="noreferrer"
            className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7]"
          >
            Permanent JSON
          </a>
        </div>
      </div>

      {loadError && (
        <div className="m-3 rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-3 py-2 text-sm text-[#7A1F1F]">
          {loadError}
        </div>
      )}

      {!run && !loadError && (
        <div className="px-3 py-4 text-sm text-[#042648]/62">Loading published QA run...</div>
      )}

      {run && (
        <div className="space-y-2 p-3">
          <div className="grid gap-2 md:grid-cols-5">
            <QaMiniMetric label="Run" value={run.runId} />
            <QaMiniMetric label="Completed" value={new Date(run.completedAt).toLocaleString()} />
            <QaMiniMetric label="Turns" value={run.aggregate.turnCount} />
            <QaMiniMetric label="Knowledge" value={`${run.aggregate.knowledgeTurnCount ?? 0}/${run.aggregate.turnCount}`} />
            <QaMiniMetric label="AI Errors" value={run.aggregate.aiErrorTurnCount ?? 0} />
          </div>

          <div className="space-y-2">
            {run.conversations.map((conversation, index) => (
              <PublishedConversationDetails
                key={conversation.id}
                conversation={conversation}
                index={index}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function QaMiniMetric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">{label}</div>
      <div className="mt-1 break-words text-xs font-bold text-[#042648]">{value}</div>
    </div>
  );
}

function buildAttachmentQaSummary(run: PublishedQaRun) {
  const people = run.conversations.map((conversation) => {
    const finalMemories = getPublishedMemories(conversation);
    const knowledgeTurns = conversation.turns.filter((turn) => getPublishedKnowledge(turn).count > 0).length;
    const memoryCaptureTurns = conversation.turns.filter((turn) => getPublishedMemoryCapture(turn).count > 0).length;
    const memoryRetrievalTurns = conversation.turns.filter((turn) => getPublishedMemoryRetrieval(turn).count > 0).length;
    const totalChunks = conversation.turns.reduce((sum, turn) => sum + getPublishedKnowledge(turn).count, 0);
    const domainCounts = countStrings(
      conversation.turns.flatMap((turn) => getPublishedKnowledge(turn).chunks.map((chunk) => chunk.domain))
    );

    return {
      id: conversation.id,
      name: conversation.storedProfile?.nombre || conversation.title.replace(/^\d+\.\s*/, '').split(',')[0],
      expectedStyle: conversation.expectedAttachmentStyle || '',
      savedStyle: conversation.storedProfile?.attachment_style || '',
      turns: conversation.turns.length,
      knowledgeTurns,
      memoryCaptureTurns,
      memoryRetrievalTurns,
      memories: finalMemories.length,
      topDomain: domainCounts[0]?.label || 'none',
      averageChunks: conversation.turns.length ? totalChunks / conversation.turns.length : 0,
    };
  });

  const turns = run.conversations.reduce((sum, conversation) => sum + conversation.turns.length, 0);
  const knowledgeTurns = run.conversations.reduce(
    (sum, conversation) => sum + conversation.turns.filter((turn) => getPublishedKnowledge(turn).count > 0).length,
    0
  );
  const memoryCaptureTurns = run.conversations.reduce(
    (sum, conversation) => sum + conversation.turns.filter((turn) => getPublishedMemoryCapture(turn).count > 0).length,
    0
  );
  const allChunks = run.conversations.flatMap((conversation) =>
    conversation.turns.flatMap((turn) => getPublishedKnowledge(turn).chunks)
  );
  const domainCounts = countStrings(allChunks.map((chunk) => chunk.domain));
  const topArticles = countStrings(allChunks.map((chunk) => chunk.title)).slice(0, 8);

  return {
    conversations: run.conversations.length,
    turns,
    failures: run.aggregate.failedConversationCount,
    aiErrors: run.aggregate.aiErrorTurnCount ?? 0,
    storedStyles: run.aggregate.storedAttachmentStyleCount ?? 0,
    storedMemories: run.aggregate.storedMemoryCount ?? 0,
    knowledgeTurns,
    memoryCaptureTurns,
    averageKnowledgeChunks: run.aggregate.averageKnowledgeChunks ?? 0,
    people,
    domainCounts,
    topArticles,
    maxDomainCount: Math.max(...domainCounts.map((row) => row.count), 1),
    maxArticleCount: Math.max(...topArticles.map((row) => row.count), 1),
  };
}

function countStrings(values: string[]): Array<{ label: string; count: number }> {
  const counts = new Map<string, number>();
  values.filter(Boolean).forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function percentage(value: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((value / total) * 100)));
}

function GraphMetric({
  label,
  value,
  detail,
  percent,
  tone,
}: {
  label: string;
  value: ReactNode;
  detail: string;
  percent: number;
  tone: 'good' | 'warn' | 'bad' | 'neutral';
}) {
  const colors = {
    good: '#2F8F5B',
    warn: '#C1821D',
    bad: '#A33A3A',
    neutral: '#4674B8',
  };
  return (
    <div className="rounded border border-[#042648]/10 bg-[#F8FAF7] px-3 py-3">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">{label}</div>
      <div className="mt-2 text-xl font-bold text-[#042648]">{value}</div>
      <div className="mt-1 text-xs text-[#042648]/60">{detail}</div>
      <div className="mt-3 h-2 overflow-hidden rounded bg-white">
        <div className="h-full rounded" style={{ width: `${percent}%`, backgroundColor: colors[tone] }} />
      </div>
    </div>
  );
}

function ProgressRow({ label, value, total }: { label: string; value: number; total: number }) {
  const percent = percentage(value, total);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2 text-[11px] font-semibold text-[#042648]/62">
        <span>{label}</span>
        <span>{value}/{total}</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-[#EEF1EA]">
        <div className="h-full rounded bg-[#2F8F5B]" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function HorizontalBar({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const width = max ? Math.max(5, Math.round((value / max) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3 text-xs">
        <span className="line-clamp-2 font-semibold leading-5 text-[#042648]/74">{label}</span>
        <span className="shrink-0 font-bold text-[#042648]">{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-white">
        <div className="h-full rounded" style={{ width: `${width}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function StylePill({ label, tone = 'neutral' }: { label: string; tone?: 'good' | 'bad' | 'neutral' }) {
  const classes =
    tone === 'good'
      ? 'border-[#2F8F5B]/25 bg-[#EAF7EF] text-[#165A38]'
      : tone === 'bad'
        ? 'border-[#A33A3A]/25 bg-[#FFF0F0] text-[#7A1F1F]'
        : 'border-[#042648]/15 bg-[#F8FAF7] text-[#042648]/62';
  return (
    <span className={`rounded border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.06em] ${classes}`}>
      {label}
    </span>
  );
}

function getPublishedMemories(conversation: PublishedQaConversation): UserMemory[] {
  return conversation.finalMemories || conversation.storedMemories || [];
}

function getAttachmentQaDisplayName(conversation: PublishedQaConversation): string {
  return conversation.storedProfile?.nombre || conversation.title.replace(/^\d+\.\s*/, '').split(',')[0];
}

function getPublishedProfileValue(conversation: PublishedQaConversation, key: keyof UserProfile): string {
  const value = conversation.storedProfile?.[key];
  if (value === null || value === undefined || value === '') return 'none';
  return String(value);
}

function getPublishedKnowledge(turn: PublishedQaTurn): NonNullable<PublishedQaTurn['knowledge']> {
  return turn.knowledge || { count: 0, detail: '', chunks: [] };
}

function getPublishedMemoryRetrieval(turn: PublishedQaTurn): NonNullable<PublishedQaTurn['memory_retrieval']> {
  return turn.memory_retrieval || { count: 0, detail: '', memories: [] };
}

function getPublishedMemoryCapture(turn: PublishedQaTurn): NonNullable<PublishedQaTurn['memory_capture']> {
  return turn.memory_capture || { count: 0, detail: '', candidates: [] };
}

function getPublishedProfileCapture(turn: PublishedQaTurn): NonNullable<PublishedQaTurn['profile_capture']> {
  return turn.profile_capture || { updates: {}, error: null };
}

function getPublishedDecisionSteps(turn: PublishedQaTurn): Array<{ stage: string; title: string; detail: string; payload: unknown }> {
  if (!turn.debug || typeof turn.debug !== 'object') return [];
  const steps = (turn.debug as { steps?: unknown }).steps;
  if (!Array.isArray(steps)) return [];
  const visibleStages = new Set(['brain_router', 'coaching_planner', 'knowledge_brain', 'memory_brain', 'response_composition']);
  return steps
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .filter((item) => visibleStages.has(String(item.stage || '')))
    .map((item) => ({
      stage: String(item.stage || 'step'),
      title: String(item.title || item.stage || 'Decision step'),
      detail: String(item.detail || ''),
      payload: item.payload,
    }));
}

function getProfileUpdateEntries(turn: PublishedQaTurn): Array<[string, unknown]> {
  const updates = getPublishedProfileCapture(turn).updates || {};
  return Object.entries(updates).filter(([, value]) => value !== undefined);
}

function formatPublishedValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'empty';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function PublishedConversationDetails({
  conversation,
  index,
}: {
  conversation: PublishedQaConversation;
  index: number;
}) {
  const finalMemories = getPublishedMemories(conversation);
  const knowledgeTurns = conversation.turns.filter((turn) => getPublishedKnowledge(turn).count > 0).length;
  const memoryCaptureTurns = conversation.turns.filter((turn) => getPublishedMemoryCapture(turn).count > 0).length;
  const aiErrors = conversation.turns.filter((turn) => turn.ai_error).length;

  return (
    <details className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
      <summary className="cursor-pointer px-3 py-2 text-sm font-bold text-[#042648]">
        {String(index + 1).padStart(2, '0')}. {conversation.title}
        <span className="ml-2 text-xs font-semibold text-[#042648]/50">
          {conversation.turns.length} turns / K {knowledgeTurns} / captures {memoryCaptureTurns} / errors {aiErrors}
        </span>
      </summary>
      <div className="space-y-3 border-t border-[#042648]/10 p-3">
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          <QaMiniMetric label="Kind" value={conversation.kind ? formatType(conversation.kind) : 'attachment style'} />
          <QaMiniMetric label="QA User" value={conversation.email} />
          <QaMiniMetric label="Saved Style" value={getPublishedProfileValue(conversation, 'attachment_style')} />
          <QaMiniMetric label="Expected Style" value={conversation.expectedAttachmentStyle || 'n/a'} />
          <QaMiniMetric label="Final Memories" value={finalMemories.length} />
          <QaMiniMetric label="Error" value={conversation.error || 'none'} />
        </div>

        <div className="rounded bg-white px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">Profile Seed</div>
          <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] leading-4 text-[#042648]/68">
            {JSON.stringify(conversation.profileSeed, null, 2)}
          </pre>
        </div>

        {conversation.storedProfile && (
          <div className="rounded bg-white px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Final Stored Profile
            </div>
            <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-[11px] leading-4 text-[#042648]/68">
              {JSON.stringify(conversation.storedProfile, null, 2)}
            </pre>
          </div>
        )}

        {conversation.turns.map((turn, turnIndex) => (
          <PublishedTurnDetails key={`${conversation.id}-${turnIndex}`} turn={turn} index={turnIndex} />
        ))}

        <div className="rounded bg-white px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
            Final Stored Memories
          </div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {finalMemories.map((memory) => (
              <div key={memory.id} className="rounded bg-[#F8FAF7] px-2 py-2 text-xs text-[#042648]/70">
                <div className="font-bold text-[#042648]">{formatType(memory.type)}</div>
                <div className="mt-1 text-[11px] text-[#042648]/50">
                  {memory.status} / {memory.sensitivity} / {Math.round(memory.confidence * 100)}%
                </div>
                <p className="mt-1 leading-5">{memory.curated_summary || memory.summary}</p>
              </div>
            ))}
            {finalMemories.length === 0 && (
              <p className="text-xs text-[#042648]/55">No visible memories stored.</p>
            )}
          </div>
        </div>
      </div>
    </details>
  );
}

function PublishedTurnDetails({ turn, index }: { turn: PublishedQaTurn; index: number }) {
  const knowledge = getPublishedKnowledge(turn);
  const memoryRetrieval = getPublishedMemoryRetrieval(turn);
  const memoryCapture = getPublishedMemoryCapture(turn);
  const routedDomains = Array.isArray(turn.routed_domains) ? turn.routed_domains : [];
  const aiError = turn.ai_error || null;
  const decisionSteps = getPublishedDecisionSteps(turn);

  return (
    <article className="rounded border border-[#042648]/10 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
          Turn {index + 1}
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/80">{turn.prompt}</p>
      </div>
      <div className="space-y-3 p-3">
        <div className="rounded border border-[#2F8F5B]/18 bg-[#EAF7EF] px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#165A38]/70">
            Actual Bot Response
          </div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">{turn.message || ''}</p>
        </div>

        <div className="grid gap-2 xl:grid-cols-3">
          <QaMiniMetric label="Intent" value={turn.intent || 'none'} />
          <QaMiniMetric label="Domains" value={routedDomains.join(', ') || 'none'} />
          <QaMiniMetric label="AI Error" value={aiError || 'none'} />
        </div>

        <div className="rounded bg-[#FBF4FC] px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#5B2467]/70">
            Internal Decision Trace
          </div>
          <p className="mt-1 text-xs leading-5 text-[#5B2467]/70">
            Concise backend planning and routing summaries; hidden chain-of-thought is not exposed.
          </p>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {decisionSteps.map((item, stepIndex) => (
              <div key={`${item.stage}-${stepIndex}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/70">
                <div className="font-bold text-[#042648]">{item.title}</div>
                <p className="mt-1 leading-5">{item.detail}</p>
                {item.payload !== null && item.payload !== undefined && (
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-[#F8FAF7] p-2 text-[10px] leading-4">
                    {JSON.stringify(item.payload, null, 2)}
                  </pre>
                )}
              </div>
            ))}
            {decisionSteps.length === 0 && <p className="text-xs text-[#042648]/55">No decision trace returned.</p>}
          </div>
        </div>

        <QaTurnCollection
          title="Knowledge Chosen From Brain"
          detail={knowledge.detail}
          empty="No knowledge chunks retrieved."
          items={knowledge.chunks.map((chunk) => ({
            id: chunk.id,
            title: chunk.title,
            meta: `${chunk.domain} / ${chunk.section} / score ${chunk.score}`,
            body: chunk.preview,
          }))}
        />

        <QaTurnCollection
          title="User Memories Retrieved"
          detail={memoryRetrieval.detail}
          empty="No memories retrieved."
          items={memoryRetrieval.memories.map((memory) => ({
            id: memory.id,
            title: formatType(memory.type),
            meta: `${memory.status} / ${Math.round(memory.confidence * 100)}%`,
            body: memory.summary,
          }))}
        />

        <QaTurnCollection
          title="Memory Capture Written By Backend"
          detail={memoryCapture.detail}
          empty="No memory candidates captured."
          items={memoryCapture.candidates.map((candidate) => ({
            id: candidate.id,
            title: formatType(candidate.type),
            meta: `${candidate.status} / ${Math.round(candidate.confidence * 100)}%`,
            body: candidate.summary,
          }))}
        />
      </div>
    </article>
  );
}

function QaTurnCollection({
  title,
  detail,
  empty,
  items,
}: {
  title: string;
  detail: string;
  empty: string;
  items: Array<{ id: string; title: string; meta: string; body: string }>;
}) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">{title}</div>
      {detail && <p className="mt-1 text-xs leading-5 text-[#042648]/60">{detail}</p>}
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {items.map((item, index) => (
          <div key={`${item.id}-${index}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/70">
            <div className="font-bold text-[#042648]">{item.title}</div>
            <div className="mt-1 text-[11px] text-[#042648]/50">{item.meta}</div>
            <p className="mt-1 leading-5">{item.body}</p>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-[#042648]/55">{empty}</p>}
      </div>
    </div>
  );
}

function PersonalityThreadReader({
  conversation,
  actualRun,
  liveRun,
  isRunningAll,
  onRun,
  onRunAll,
  onRunLive,
}: {
  conversation: (typeof personalityTestConversations)[number];
  actualRun?: ActualSimulationRun;
  liveRun?: LiveSimulationRun;
  isRunningAll: boolean;
  onRun: () => void;
  onRunAll: () => void;
  onRunLive: () => void;
}) {
  const userPromptCount = conversation.turns.filter((turn) => turn.role === 'user').length;
  const userPrompts = conversation.turns.filter((turn) => turn.role === 'user');
  const isBusy = actualRun?.status === 'running' || liveRun?.status === 'running' || isRunningAll;

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
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onRunLive}
            disabled={isBusy}
            className="rounded bg-[#9B5AA6] px-3 py-2 text-xs font-bold text-white transition hover:bg-[#9B5AA6]/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {liveRun?.status === 'running'
              ? 'Generando conversación...'
              : 'Generar conversación en vivo (IA como usuario)'}
          </button>
          <button
            type="button"
            onClick={onRun}
            disabled={isBusy}
            className="rounded bg-[#042648] px-3 py-2 text-xs font-bold text-white transition hover:bg-[#042648]/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actualRun?.status === 'running' ? 'Running scripted bot...' : 'Run scripted bot'}
          </button>
          <button
            type="button"
            onClick={onRunAll}
            disabled={isBusy}
            className="rounded border border-[#042648]/20 bg-white px-3 py-2 text-xs font-bold text-[#042648]/70 transition hover:bg-[#F8FAF7] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isRunningAll ? 'Running all...' : `Run all ${personalityTestConversations.length} (scripted)`}
          </button>
        </div>
      </div>

      <div className="space-y-4 px-3 py-3">
        <SimulationSetupCard conversation={conversation} />

        <section className="rounded border border-[#9B5AA6]/25 bg-[#FBF4FC]">
          <div className="border-b border-[#9B5AA6]/20 px-3 py-2">
            <h4 className="text-sm font-bold text-[#5B2467]">Conversación en vivo (IA como usuario)</h4>
            <p className="mt-1 text-xs text-[#5B2467]/70">
              Una IA interpreta este perfil y habla con el bot real turno a turno. Verás cómo responde
              el bot y de dónde saca la información en cada mensaje.
            </p>
          </div>
          <div className="p-3">
            {liveRun ? (
              <LiveSimulationRunPanel run={liveRun} />
            ) : (
              <div className="rounded border border-dashed border-[#9B5AA6]/35 bg-white px-4 py-6 text-sm text-[#5B2467]/70">
                Pulsa &ldquo;Generar conversación en vivo&rdquo; para crear una conversación de ejemplo
                nueva con este perfil e inspeccionar respuestas y fuentes.
              </div>
            )}
          </div>
        </section>

        <section className="rounded border border-[#042648]/10 bg-[#FFFDF8]">
          <div className="border-b border-[#042648]/10 px-3 py-2">
            <h4 className="text-sm font-bold text-[#042648]">Script Sent To Actual Bot</h4>
            <p className="mt-1 text-xs text-[#042648]/60">
              These are the user prompts the runner sends after register, login, profile setup, and optional self-test.
            </p>
          </div>
          <div className="space-y-2 p-3">
            {userPrompts.map((turn, index) => (
              <div key={`${conversation.id}-prompt-${index}`} className="rounded bg-white px-3 py-2">
                <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
                  Prompt {index + 1}
                </div>
                <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/78">{turn.content}</p>
              </div>
            ))}
          </div>
        </section>

        {actualRun ? (
          <ActualSimulationRunPanel run={actualRun} />
        ) : (
          <div className="rounded border border-dashed border-[#042648]/25 bg-white px-4 py-6 text-sm text-[#042648]/65">
            Run this thread to create a real QA user and inspect actual bot responses, retrieved brain knowledge,
            profile capture, memory capture, and user memory retrieval.
          </div>
        )}
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

function SimulationSetupCard({ conversation }: { conversation: (typeof personalityTestConversations)[number] }) {
  const profile = conversation.simulation.profile;

  return (
    <section className="rounded border border-[#042648]/10 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <h4 className="text-sm font-bold text-[#042648]">Real User Setup</h4>
        <p className="mt-1 text-xs text-[#042648]/60">
          The runner registers a fresh QA user, updates this profile, and tries the real attachment-test path if the backend offers it.
        </p>
      </div>
      <div className="grid gap-2 p-3 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(profile).map(([key, value]) => (
          <div key={key} className="rounded bg-[#F8FAF7] px-3 py-2">
            <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              {formatType(key)}
            </div>
            <div className="mt-1 text-xs font-semibold text-[#042648]/78">{String(value)}</div>
          </div>
        ))}
        <div className="rounded bg-[#F8FAF7] px-3 py-2">
          <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
            Self Test Answers
          </div>
          <div className="mt-1 text-xs font-semibold text-[#042648]/78">
            {conversation.simulation.selfTestAnswers.join(', ')}
          </div>
        </div>
      </div>
    </section>
  );
}

function ActualSimulationRunPanel({ run }: { run: ActualSimulationRun }) {
  if (run.status === 'running') {
    return (
      <div className="rounded border border-[#042648]/12 bg-white px-4 py-6 text-sm text-[#042648]/70">
        Running actual backend flow for {run.email}...
      </div>
    );
  }

  if (run.status === 'error') {
    return (
      <div className="rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-4 py-4 text-sm text-[#7A1F1F]">
        {run.error || 'Simulation failed'}
      </div>
    );
  }

  return (
    <section className="rounded border border-[#042648]/12 bg-white">
      <div className="border-b border-[#042648]/10 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-[#042648]">Actual Bot Run</h4>
            <p className="mt-1 text-xs text-[#042648]/60">
              User {run.email} / {run.userId || 'unknown user id'}
            </p>
          </div>
          <span className="rounded border border-[#2F8F5B]/25 bg-[#EAF7EF] px-2 py-1 text-[11px] font-bold text-[#165A38]">
            {run.turns.length} real responses
          </span>
        </div>
      </div>

      <div className="space-y-3 p-3">
        {run.profile && <ActualProfileSummary profile={run.profile} />}
        {run.selfTestResult && <ActualSelfTestSummary response={run.selfTestResult} />}

        {run.turns.map((turn, index) => (
          <ActualTurnCard key={`${run.email}-${index}`} turn={turn} index={index} />
        ))}

        <ActualMemorySummary memories={run.memories} />
      </div>
    </section>
  );
}

function ActualProfileSummary({ profile }: { profile: UserProfile }) {
  const rows = buildProfileRows(profile);
  return (
    <div className="rounded border border-[#042648]/10 bg-[#FFFDF8] px-3 py-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        Final Stored Profile
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label} className="rounded bg-white px-2 py-1.5 text-xs">
            <span className="font-bold text-[#042648]/55">{label}: </span>
            <span className="text-[#042648]/78">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ActualSelfTestSummary({ response }: { response: ChatResponse }) {
  const scores = response.data.scores && typeof response.data.scores === 'object'
    ? response.data.scores as Record<string, number>
    : {};

  return (
    <div className="rounded border border-[#042648]/10 bg-[#FFFDF8] px-3 py-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        Real Self-Test Result
      </div>
      <div className="mt-2 text-sm font-bold text-[#042648]">
        {String(response.data.attachment_style || 'unknown')}
      </div>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-[#042648]/65">
        {Object.entries(scores).map(([key, value]) => (
          <span key={key} className="rounded bg-white px-2 py-1">
            {formatType(key)}: {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function ActualTurnCard({ turn, index }: { turn: ActualSimulationTurn; index: number }) {
  const debug = turn.response.data.debug;
  const knowledgeStep = getDebugStep(debug?.steps, 'knowledge_brain');
  const memorySearchStep = getDebugStep(debug?.steps, 'memory_brain');
  const memoryCaptureStep = getDebugStep(debug?.steps, 'memory_capture');
  const profileCaptureStep = getDebugStep(debug?.steps, 'profile_capture');
  const routerStep = getDebugStep(debug?.steps, 'brain_router');

  return (
    <article className="rounded border border-[#042648]/10 bg-[#F8FAF7]">
      <div className="border-b border-[#042648]/10 px-3 py-2">
        <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
          Actual Prompt {index + 1}
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/80">{turn.prompt}</p>
      </div>

      <div className="space-y-3 px-3 py-3">
        <div className="rounded border border-[#2F8F5B]/18 bg-[#EAF7EF] px-3 py-2">
          <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#165A38]/70">
            Real Bot Response
          </div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">
            {String(turn.response.data.message || '')}
          </p>
        </div>

        {debug && (
          <div className="rounded border border-[#042648]/10 bg-white px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              Real Backend Debug
            </div>
            <p className="mt-1 text-xs leading-5 text-[#042648]/65">{debug.reasoning_summary}</p>

            <div className="mt-3 grid gap-2 lg:grid-cols-2">
              <DebugStepBlock title="Brain Router" step={routerStep} />
              <DebugStepBlock title="Profile Capture" step={profileCaptureStep} />
              <DebugKnowledgeBlock step={knowledgeStep} />
              <DebugMemorySearchBlock step={memorySearchStep} />
              <DebugMemoryCaptureBlock step={memoryCaptureStep} />
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function LiveSimulationRunPanel({ run }: { run: LiveSimulationRun }) {
  if (run.status === 'error') {
    return (
      <div className="rounded border border-[#A33A3A]/25 bg-[#FFF0F0] px-4 py-4 text-sm text-[#7A1F1F]">
        {run.error || 'Live simulation failed'}
      </div>
    );
  }

  return (
    <section className="rounded border border-[#9B5AA6]/20 bg-white">
      <div className="border-b border-[#9B5AA6]/15 px-3 py-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-[#5B2467]">Conversación generada</h4>
            <p className="mt-1 text-xs text-[#5B2467]/65">
              Usuario {run.email} / {run.userId || 'unknown user id'}
            </p>
          </div>
          <span className="rounded border border-[#9B5AA6]/30 bg-[#FBF4FC] px-2 py-1 text-[11px] font-bold text-[#5B2467]">
            {run.status === 'running'
              ? `Generando... ${run.turns.length}/${LIVE_MAX_TURNS}`
              : `${run.turns.length} turnos`}
          </span>
        </div>
      </div>

      <div className="space-y-3 p-3">
        {run.opening && (
          <div className="rounded border border-[#2F8F5B]/18 bg-[#EAF7EF] px-3 py-2">
            <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#165A38]/70">
              Bot (apertura)
            </div>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">{run.opening}</p>
          </div>
        )}

        {run.turns.map((turn, index) => (
          <LiveTurnCard key={`${run.email}-live-${index}`} turn={turn} index={index} />
        ))}

        {run.status === 'running' && (
          <div className="rounded border border-dashed border-[#9B5AA6]/30 bg-[#FBF4FC] px-3 py-3 text-xs text-[#5B2467]/70">
            Generando el siguiente mensaje del usuario...
          </div>
        )}

        {run.status === 'complete' && run.profile && <ActualProfileSummary profile={run.profile} />}
        {run.status === 'complete' && <ActualMemorySummary memories={run.memories} />}
      </div>
    </section>
  );
}

function LiveTurnCard({ turn, index }: { turn: LiveSimulationTurn; index: number }) {
  const debug = turn.response.data.debug;
  const knowledgeStep = getDebugStep(debug?.steps, 'knowledge_brain');
  const memorySearchStep = getDebugStep(debug?.steps, 'memory_brain');
  const memoryCaptureStep = getDebugStep(debug?.steps, 'memory_capture');
  const profileCaptureStep = getDebugStep(debug?.steps, 'profile_capture');
  const routerStep = getDebugStep(debug?.steps, 'brain_router');

  return (
    <article className="rounded border border-[#9B5AA6]/18 bg-[#FBF4FC]">
      <div className="border-b border-[#9B5AA6]/15 px-3 py-2">
        <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#5B2467]/70">
          Usuario simulado (IA) · turno {index + 1}
        </div>
        <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#5B2467]/90">{turn.persona}</p>
      </div>

      <div className="space-y-3 px-3 py-3">
        <div className="rounded border border-[#2F8F5B]/18 bg-[#EAF7EF] px-3 py-2">
          <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#165A38]/70">
            Respuesta real del bot
          </div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-[#042648]/82">
            {String(turn.response.data.message || '')}
          </p>
        </div>

        {debug && (
          <div className="rounded border border-[#042648]/10 bg-white px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
              De dónde saca la información
            </div>
            <p className="mt-1 text-xs leading-5 text-[#042648]/65">{debug.reasoning_summary}</p>

            <div className="mt-3 grid gap-2 lg:grid-cols-2">
              <DebugStepBlock title="Brain Router" step={routerStep} />
              <DebugStepBlock title="Profile Capture" step={profileCaptureStep} />
              <DebugKnowledgeBlock step={knowledgeStep} />
              <DebugMemorySearchBlock step={memorySearchStep} />
              <DebugMemoryCaptureBlock step={memoryCaptureStep} />
            </div>
          </div>
        )}
      </div>
    </article>
  );
}

function DebugStepBlock({ title, step }: { title: string; step?: BotDebugStep }) {
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        {title}
      </div>
      <p className="mt-1 text-xs leading-5 text-[#042648]/70">{step?.detail || 'No debug step returned.'}</p>
      {step?.payload && Object.keys(step.payload).length > 0 && (
        <pre className="mt-2 max-h-32 overflow-auto rounded bg-white p-2 text-[11px] leading-4 text-[#042648]/68">
          {JSON.stringify(step.payload, null, 2)}
        </pre>
      )}
    </div>
  );
}

function DebugKnowledgeBlock({ step }: { step?: BotDebugStep }) {
  const chunks = Array.isArray(step?.payload.chunks) ? step.payload.chunks as Record<string, unknown>[] : [];
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        Knowledge Chosen From Brain
      </div>
      <p className="mt-1 text-xs leading-5 text-[#042648]/70">{step?.detail || 'No knowledge debug step returned.'}</p>
      <div className="mt-2 space-y-2">
        {chunks.map((chunk, index) => (
          <div key={`${String(chunk.id)}-${index}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/72">
            <div className="font-bold text-[#042648]">{String(chunk.title || 'Untitled')}</div>
            <div className="mt-1 text-[11px] text-[#042648]/55">
              {String(chunk.domain || 'domain')} / {String(chunk.section || 'section')} / score {String(chunk.score ?? 'n/a')}
            </div>
            <p className="mt-1 leading-5">{String(chunk.preview || '')}</p>
          </div>
        ))}
        {chunks.length === 0 && <p className="text-xs text-[#042648]/55">No chunks retrieved.</p>}
      </div>
    </div>
  );
}

function DebugMemorySearchBlock({ step }: { step?: BotDebugStep }) {
  const memories = Array.isArray(step?.payload.memories) ? step.payload.memories as Record<string, unknown>[] : [];
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        User Memories Retrieved
      </div>
      <p className="mt-1 text-xs leading-5 text-[#042648]/70">{step?.detail || 'No memory search debug step returned.'}</p>
      <div className="mt-2 space-y-2">
        {memories.map((memory, index) => (
          <div key={`${String(memory.id)}-${index}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/72">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-bold text-[#042648]">{formatType(String(memory.type || 'memory'))}</div>
              <span className="text-[11px] text-[#042648]/55">
                {String(memory.status || 'status')} / {Math.round(Number(memory.confidence || 0) * 100)}%
              </span>
            </div>
            <p className="mt-1 leading-5">{String(memory.summary || '')}</p>
          </div>
        ))}
        {memories.length === 0 && <p className="text-xs text-[#042648]/55">No memories retrieved for this prompt.</p>}
      </div>
    </div>
  );
}

function DebugMemoryCaptureBlock({ step }: { step?: BotDebugStep }) {
  const candidates = Array.isArray(step?.payload.candidates) ? step.payload.candidates as Record<string, unknown>[] : [];
  return (
    <div className="rounded bg-[#F8FAF7] px-3 py-2 lg:col-span-2">
      <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        Memory Capture Written By Backend
      </div>
      <p className="mt-1 text-xs leading-5 text-[#042648]/70">{step?.detail || 'No memory capture debug step returned.'}</p>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {candidates.map((candidate, index) => (
          <div key={`${String(candidate.id)}-${index}`} className="rounded bg-white px-2 py-2 text-xs text-[#042648]/72">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-bold text-[#042648]">{formatType(String(candidate.type || 'memory'))}</div>
              <span className="text-[11px] text-[#042648]/55">
                {String(candidate.change || candidate.status || 'candidate')} / {Math.round(Number(candidate.confidence || 0) * 100)}%
              </span>
            </div>
            <p className="mt-1 leading-5">{String(candidate.summary || candidate.curated_summary || '')}</p>
          </div>
        ))}
        {candidates.length === 0 && <p className="text-xs text-[#042648]/55">No new memory candidates captured.</p>}
      </div>
    </div>
  );
}

function ActualMemorySummary({ memories }: { memories: UserMemory[] }) {
  return (
    <div className="rounded border border-[#042648]/10 bg-[#FFFDF8] px-3 py-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#042648]/45">
        Final Stored User Memories
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        {memories.map((memory) => (
          <div key={memory.id} className="rounded bg-white px-3 py-2 text-xs text-[#042648]/72">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-bold text-[#042648]">{formatType(memory.type)}</div>
              <span className="text-[11px] text-[#042648]/55">
                {memory.status} / {memory.sensitivity} / {Math.round(memory.confidence * 100)}%
              </span>
            </div>
            <p className="mt-1 leading-5">{memory.curated_summary || memory.summary}</p>
          </div>
        ))}
        {memories.length === 0 && <p className="text-xs text-[#042648]/55">No visible memories stored.</p>}
      </div>
    </div>
  );
}

function getDebugStep(steps: BotDebugStep[] | undefined, stage: string): BotDebugStep | undefined {
  return steps?.find((step) => step.stage === stage);
}

async function runActualPersonalitySimulation(
  conversation: (typeof personalityTestConversations)[number],
  email: string
): Promise<ActualSimulationRun> {
  const password = `QA-${Date.now()}-aaq`;
  const startedAt = new Date();
  const setupResponses: ChatResponse[] = [];
  const turns: ActualSimulationTurn[] = [];

  await qaRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      preferred_language: 'es',
    }),
  });

  const login = await qaRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }) as {
    access_token: string;
    user_id: string;
  };

  const token = login.access_token;

  await qaRequest('/profile', {
    method: 'PUT',
    token,
    body: JSON.stringify(conversation.simulation.profile),
  });

  setupResponses.push(await qaRequest('/chat/session?language=es&debug=true', { method: 'GET', token }) as ChatResponse);
  const testStartResponse = await sendQaMessage(token, 'A');
  setupResponses.push(testStartResponse);

  let selfTestResult: ChatResponse | undefined;
  if (testStartResponse.type === 'test_question') {
    for (const answer of conversation.simulation.selfTestAnswers) {
      const response = await sendQaMessage(token, answer);
      setupResponses.push(response);
      if (response.type === 'test_results') {
        selfTestResult = response;
      }
    }

    setupResponses.push(await sendQaMessage(token, 'B'));
  }
  setupResponses.push(await sendQaMessage(token, conversation.simulation.setupMessage));

  const prompts = conversation.turns.filter((turn) => turn.role === 'user').map((turn) => turn.content);
  for (const prompt of prompts) {
    const response = await sendQaMessage(token, prompt);
    turns.push({ prompt, response });
  }

  const profile = await qaRequest('/profile', { method: 'GET', token }) as UserProfile;
  const memoriesResponse = await qaRequest('/memory', { method: 'GET', token }) as { memories: UserMemory[] };

  return {
    status: 'complete',
    email,
    userId: login.user_id,
    startedAt,
    completedAt: new Date(),
    profile,
    selfTestResult,
    setupResponses,
    turns,
    memories: memoriesResponse.memories,
  };
}

function buildLivePersona(conversation: (typeof personalityTestConversations)[number]) {
  const p = conversation.simulation.profile;
  const contexto = [conversation.simulation.context, p.ex_pareja_contexto, p.estructura_familiar_relevante, p.hijos_detalle]
    .filter(Boolean)
    .join('; ');
  return {
    nombre: p.nombre,
    edad: p.edad,
    genero: p.genero,
    orientacion: p.orientacion,
    tipo_relacion: p.tipo_relacion,
    attachment_style: conversation.simulation.attachmentStyle,
    escenario: conversation.simulation.scenario,
    contexto: contexto || undefined,
  };
}

async function runLivePersonalitySimulation(
  conversation: (typeof personalityTestConversations)[number],
  email: string,
  onUpdate: (run: LiveSimulationRun) => void
): Promise<LiveSimulationRun> {
  const password = `QA-${Date.now()}-aaq`;
  const startedAt = new Date();

  await qaRequest('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, preferred_language: 'es' }),
  });

  const login = (await qaRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })) as { access_token: string; user_id: string };

  const token = login.access_token;

  await qaRequest('/profile', {
    method: 'PUT',
    token,
    body: JSON.stringify(conversation.simulation.profile),
  });

  await qaRequest('/chat/session?language=es&debug=true', { method: 'GET', token });

  // Enter conversation mode and capture the bot's opening line.
  const opening = await sendQaMessage(token, 'A');
  const openingMessage = String(opening.data.message || '');

  const persona = buildLivePersona(conversation);
  const history: { role: 'persona' | 'bot'; content: string }[] = [];
  if (openingMessage) {
    history.push({ role: 'bot', content: openingMessage });
  }

  const turns: LiveSimulationTurn[] = [];
  const emitProgress = () =>
    onUpdate({
      status: 'running',
      email,
      userId: login.user_id,
      startedAt,
      opening: openingMessage,
      turns: [...turns],
      memories: [],
    });
  emitProgress();

  for (let turnNumber = 1; turnNumber <= LIVE_MAX_TURNS; turnNumber += 1) {
    const generated = (await qaRequest('/brain/simulate-user-turn', {
      method: 'POST',
      token,
      body: JSON.stringify({
        persona,
        history,
        language: 'es',
        turn_number: turnNumber,
        max_turns: LIVE_MAX_TURNS,
      }),
    })) as { message: string; should_end: boolean };

    const personaMessage = (generated.message || '').trim();
    if (!personaMessage) break;

    const botResponse = await sendQaMessage(token, personaMessage);
    turns.push({ persona: personaMessage, response: botResponse });
    history.push({ role: 'persona', content: personaMessage });
    history.push({ role: 'bot', content: String(botResponse.data.message || '') });
    emitProgress();

    if (generated.should_end) break;
  }

  const profile = (await qaRequest('/profile', { method: 'GET', token })) as UserProfile;
  const memoriesResponse = (await qaRequest('/memory', { method: 'GET', token })) as {
    memories: UserMemory[];
  };

  return {
    status: 'complete',
    email,
    userId: login.user_id,
    startedAt,
    completedAt: new Date(),
    opening: openingMessage,
    profile,
    turns,
    memories: memoriesResponse.memories,
  };
}

async function sendQaMessage(token: string, message: string): Promise<ChatResponse> {
  return qaRequest('/chat/message', {
    method: 'POST',
    token,
    body: JSON.stringify({
      message,
      language: 'es',
      debug: true,
    }),
  }) as Promise<ChatResponse>;
}

async function qaRequest(
  path: string,
  options: RequestInit & { token?: string }
): Promise<unknown> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`${path} failed (${response.status}): ${body.slice(0, 400)}`);
  }

  return response.json();
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
  addRow(rows, 'Attachment style', profile.attachment_style);
  addRow(rows, 'Partner attachment style', profile.partner_attachment_style);
  addRow(rows, 'Relationship status', profile.relationship_status);
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

function DocumentGroup({
  title,
  chunks,
  onOpen,
}: {
  title: string;
  chunks: KnowledgeChunk[];
  onOpen: (chunk: KnowledgeChunk) => void;
}) {
  const language = chunks[0]?.language;
  return (
    <article className="overflow-hidden rounded border border-[#042648]/12 bg-white">
      <div className="flex items-start justify-between gap-3 border-b border-[#042648]/10 bg-[#FFFDF8] px-3 py-2.5">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-bold text-[#042648]">{title}</h4>
          <p className="mt-0.5 text-xs text-[#042648]/55">
            {chunks.length} {chunks.length === 1 ? 'sección' : 'secciones'}
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-[#042648]/15 bg-white px-2 py-0.5 text-[11px] font-semibold text-[#042648]/60">
          {language || 'multi'}
        </span>
      </div>
      <ul className="divide-y divide-[#042648]/8">
        {chunks.map((chunk) => (
          <li key={chunk.id}>
            <button
              type="button"
              onClick={() => onOpen(chunk)}
              title={chunk.preview}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition hover:bg-[#F8FAF7] focus:bg-[#F8FAF7] focus:outline-none"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold text-[#042648]/85">
                  {chunk.section || 'Sin sección'}
                </span>
                <span className="mt-0.5 block truncate text-xs text-[#042648]/55">
                  {chunk.preview}
                </span>
              </span>
              <span className="shrink-0 text-xs font-bold text-[#042648]/45">Abrir →</span>
            </button>
          </li>
        ))}
      </ul>
    </article>
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
                {formatKnowledgeChunkCategory(chunk)} / {chunk.language || 'multi'}
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
    const groupKey = getKnowledgeGroupKey(chunk);
    const rows = grouped.get(groupKey) || [];
    rows.push(chunk);
    grouped.set(groupKey, rows);
  });
  return Array.from(grouped.entries());
}

function groupKnowledgeByDocument(chunks: KnowledgeChunk[]): [string, KnowledgeChunk[]][] {
  const grouped = new Map<string, KnowledgeChunk[]>();
  chunks.forEach((chunk) => {
    const rows = grouped.get(chunk.title) || [];
    rows.push(chunk);
    grouped.set(chunk.title, rows);
  });
  return Array.from(grouped.entries());
}

function getKnowledgeGroupKey(chunk: KnowledgeChunk): string {
  if (chunk.domain !== 'polarity') return chunk.domain;
  return `polarity:${normalizePolarityLane(chunk.polarity_lane)}`;
}

function normalizePolarityLane(value?: string): string {
  if (value === 'masculine_advice' || value === 'feminine_advice' || value === 'shared_principle') {
    return value;
  }
  return 'shared_principle';
}

function formatKnowledgeGroup(value: string): string {
  if (!value.startsWith('polarity:')) return formatType(value);
  const lane = value.split(':')[1];
  if (lane === 'masculine_advice') return 'Polarity / Masculine';
  if (lane === 'feminine_advice') return 'Polarity / Feminine';
  return 'Polarity / Mixed';
}

function formatKnowledgeChunkCategory(chunk: KnowledgeChunk): string {
  return formatKnowledgeGroup(getKnowledgeGroupKey(chunk));
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
