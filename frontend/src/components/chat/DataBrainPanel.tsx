'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import * as api from '@/lib/api';
import type { DebugSession, UserMemory } from '@/lib/types';

type BrainMode = 'text' | 'constellation';
type BrainTab = 'data' | 'live';

interface Props {
  activeTab: BrainTab;
  debugSessions: DebugSession[];
  isAuthenticated: boolean;
  refreshKey: number;
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
}: Props) {
  const [mode, setMode] = useState<BrainMode>('text');
  const [memories, setMemories] = useState<UserMemory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    void loadMemories();
  }, [loadMemories, refreshKey]);

  useEffect(() => {
    if (!isAuthenticated || activeTab !== 'live') return;

    const interval = window.setInterval(() => {
      void loadMemories();
    }, 3000);

    return () => window.clearInterval(interval);
  }, [activeTab, isAuthenticated, loadMemories]);

  const liveCandidates = useMemo(() => extractLiveCandidates(debugSessions), [debugSessions]);
  const groupedMemories = useMemo(() => groupMemoriesByType(memories), [memories]);

  if (!isAuthenticated) {
    return (
      <BrainShell
        title={activeTab === 'data' ? 'Data Brain' : 'Live Fill'}
        subtitle="Sign in to see user memory data."
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
      subtitle="Persistent user-visible memories."
      countLabel={`${memories.length} memories`}
      toolbar={
        <div className="flex rounded border border-[#042648]/15 bg-white p-1">
          <button
            type="button"
            onClick={() => setMode('text')}
            className={`px-3 py-1.5 text-xs font-semibold transition ${
              mode === 'text' ? 'bg-[#042648] text-white' : 'text-[#042648]/70 hover:bg-[#F8FAF7]'
            }`}
          >
            Text
          </button>
          <button
            type="button"
            onClick={() => setMode('constellation')}
            className={`px-3 py-1.5 text-xs font-semibold transition ${
              mode === 'constellation' ? 'bg-[#042648] text-white' : 'text-[#042648]/70 hover:bg-[#F8FAF7]'
            }`}
          >
            Constellation
          </button>
        </div>
      }
    >
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
          <Constellation memories={memories} />
        </div>
      )}
    </BrainShell>
  );
}

function BrainShell({
  title,
  subtitle,
  countLabel,
  toolbar,
  children,
}: {
  title: string;
  subtitle: string;
  countLabel?: string;
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
        </div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
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

function Constellation({ memories }: { memories: UserMemory[] }) {
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
          <g key={node.memory.id}>
            <circle
              cx={node.x}
              cy={node.y}
              r={node.radius}
              fill={node.color.bg}
              stroke={node.color.border}
              strokeWidth="2"
            />
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
          <div key={`legend-${node.memory.id}`} className="rounded border border-[#042648]/10 bg-white/95 px-3 py-2 text-xs">
            <div className="font-bold text-[#042648]">{formatType(node.memory.type)}</div>
            <div className="mt-1 line-clamp-2 text-[#042648]/65">
              {node.memory.curated_summary || node.memory.summary}
            </div>
          </div>
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
