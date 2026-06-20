'use client';

import type { BotDebugStep, DebugSession } from '@/lib/types';

interface Props {
  sessions: DebugSession[];
}

export default function DebugPanel({ sessions }: Props) {
  const latest = sessions.at(-1);

  return (
    <aside className="h-full w-full border-t lg:border-l lg:border-t-0 border-[#042648]/15 bg-[#F8FAF7] text-[#042648] lg:w-[430px]">
      <div className="flex h-full flex-col">
        <div className="border-b border-[#042648]/15 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-[0.08em]">Brain Debug</h2>
              <p className="mt-1 text-xs text-[#042648]/65">
                Routing, retrieval, memory, and prompt packet.
              </p>
            </div>
            <span className="rounded-full border border-[#042648]/20 px-2 py-1 text-[11px] font-semibold">
              {sessions.length} traces
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3">
          {!latest && (
            <div className="rounded border border-dashed border-[#042648]/25 bg-white px-3 py-4 text-sm text-[#042648]/65">
              Waiting for the first message trace.
            </div>
          )}

          {sessions.map((session, index) => (
            <section
              key={session.id}
              className={`mb-3 rounded border bg-white ${
                index === sessions.length - 1 ? 'border-[#042648]/35' : 'border-[#042648]/12'
              }`}
            >
              <div className="border-b border-[#042648]/10 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase tracking-[0.06em]">
                    Message {index + 1}
                  </span>
                  <StatusPill status={session.status} />
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-[#042648]/70">{session.userMessage}</p>
              </div>

              {session.status === 'processing' && <ProcessingSteps />}

              {session.trace && (
                <div className="px-3 py-2">
                  <div className="mb-2 rounded bg-[#FFF6EA] px-3 py-2 text-xs leading-relaxed">
                    <span className="font-semibold">Summary: </span>
                    {session.trace.reasoning_summary}
                  </div>
                  <div className="space-y-2">
                    {session.trace.steps.map((step, stepIndex) => (
                      <DebugStepView key={`${session.id}-${step.stage}-${stepIndex}`} step={step} />
                    ))}
                  </div>
                </div>
              )}
            </section>
          ))}
        </div>
      </div>
    </aside>
  );
}

function StatusPill({ status }: { status: DebugSession['status'] }) {
  const label = status === 'processing' ? 'Processing' : status === 'complete' ? 'Complete' : 'Error';
  const className =
    status === 'processing'
      ? 'border-[#B88700]/35 bg-[#FFF6EA] text-[#7A5600]'
      : status === 'complete'
        ? 'border-[#1F7A4D]/25 bg-[#EAF7EF] text-[#145C39]'
        : 'border-[#A33A3A]/25 bg-[#FFF0F0] text-[#7A1F1F]';

  return (
    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${className}`}>
      {label}
    </span>
  );
}

function ProcessingSteps() {
  const steps = ['Sending message', 'Waiting for backend trace', 'Preparing brain panel'];
  return (
    <div className="space-y-2 px-3 py-3">
      {steps.map((step) => (
        <div key={step} className="flex items-center gap-2 text-xs text-[#042648]/65">
          <span className="h-2 w-2 animate-pulse rounded-full bg-[#042648]/45" />
          {step}
        </div>
      ))}
    </div>
  );
}

function DebugStepView({ step }: { step: BotDebugStep }) {
  return (
    <div className="rounded border border-[#042648]/10 px-3 py-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-semibold">{step.title}</div>
          <div className="mt-0.5 text-[11px] uppercase tracking-[0.06em] text-[#042648]/45">
            {step.stage}
          </div>
        </div>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-[#042648]/72">{step.detail}</p>
      <PayloadView payload={step.payload} />
    </div>
  );
}

function PayloadView({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload).filter(([, value]) => value !== undefined && value !== null);
  if (entries.length === 0) return null;

  const chunks = getArrayPayload(payload, 'chunks');
  const memories = getArrayPayload(payload, 'memories');
  const candidates = getArrayPayload(payload, 'candidates');

  if (chunks.length > 0) {
    return <ListPayload title="Knowledge chunks" rows={chunks} />;
  }

  if (memories.length > 0) {
    return <ListPayload title="Memory matches" rows={memories} />;
  }

  if (candidates.length > 0) {
    return <ListPayload title="Captured candidates" rows={candidates} />;
  }

  return (
    <dl className="mt-2 grid grid-cols-1 gap-1 text-xs">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded bg-[#F8FAF7] px-2 py-1">
          <dt className="font-semibold">{formatLabel(key)}</dt>
          <dd className="mt-0.5 break-words text-[#042648]/70">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ListPayload({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  return (
    <div className="mt-2">
      <div className="mb-1 text-[11px] font-bold uppercase tracking-[0.06em] text-[#042648]/50">
        {title}
      </div>
      <div className="space-y-1">
        {rows.map((row, index) => (
          <div key={index} className="rounded bg-[#F8FAF7] px-2 py-2 text-xs">
            <div className="font-semibold">
              {stringValue(row.title) || stringValue(row.type) || stringValue(row.id) || `Item ${index + 1}`}
            </div>
            {stringValue(row.section) && (
              <div className="mt-0.5 text-[11px] text-[#042648]/55">{stringValue(row.section)}</div>
            )}
            {stringValue(row.summary) && (
              <div className="mt-1 text-[#042648]/70">{stringValue(row.summary)}</div>
            )}
            {stringValue(row.preview) && (
              <div className="mt-1 text-[#042648]/70">{stringValue(row.preview)}</div>
            )}
            <div className="mt-1 flex flex-wrap gap-1 text-[11px] text-[#042648]/55">
              {stringValue(row.domain) && <span>{stringValue(row.domain)}</span>}
              {typeof row.score === 'number' && <span>score {row.score}</span>}
              {typeof row.confidence === 'number' && <span>confidence {row.confidence}</span>}
              {stringValue(row.status) && <span>{stringValue(row.status)}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getArrayPayload(payload: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = payload[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item));
}

function formatLabel(value: string) {
  return value.replaceAll('_', ' ');
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => formatValue(item)).join(', ');
  if (typeof value === 'object' && value !== null) return JSON.stringify(value);
  return String(value);
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

