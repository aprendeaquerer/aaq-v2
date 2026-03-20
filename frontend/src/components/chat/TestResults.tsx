'use client';

import type { TestResultsData } from '@/lib/types';

interface Props {
  data: TestResultsData;
}

const STYLE_COLORS: Record<string, string> = {
  secure: 'bg-green-100 text-green-800',
  anxious: 'bg-yellow-100 text-yellow-800',
  avoidant: 'bg-blue-100 text-blue-800',
  disorganized: 'bg-purple-100 text-purple-800',
};

const STYLE_LABELS: Record<string, string> = {
  secure: 'Seguro',
  anxious: 'Ansioso',
  avoidant: 'Evitativo',
  disorganized: 'Desorganizado',
};

export default function TestResults({ data }: Props) {
  const maxScore = Math.max(...Object.values(data.scores));

  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[90%] bg-[#F1DCF4] text-[#042648] px-4 py-4 rounded-2xl rounded-bl-md">
        <span className="text-xs font-semibold block mb-1 opacity-70">Eldric</span>

        <h3 className="font-bold text-lg mb-2">
          {data.test_type === 'partner' ? 'Resultado de tu pareja' : 'Tu resultado'}
        </h3>

        {/* Main style badge */}
        <div className={`inline-block px-4 py-2 rounded-full font-semibold text-sm mb-3 ${STYLE_COLORS[data.attachment_style] || 'bg-gray-100'}`}>
          {STYLE_LABELS[data.attachment_style] || data.attachment_style}
        </div>

        {/* Description */}
        <p className="text-sm mb-4">{data.description}</p>

        {/* Score bars */}
        <div className="space-y-2">
          {Object.entries(data.scores).map(([style, score]) => (
            <div key={style} className="flex items-center gap-2">
              <span className="text-xs w-24 capitalize">{STYLE_LABELS[style] || style}</span>
              <div className="flex-1 h-3 bg-[#042648]/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${score === maxScore ? 'bg-[#042648]' : 'bg-[#042648]/40'}`}
                  style={{ width: `${(score / 10) * 100}%` }}
                />
              </div>
              <span className="text-xs font-medium w-6 text-right">{score}</span>
            </div>
          ))}
        </div>

        {/* Relationship dynamic (for partner test) */}
        {data.relationship_description && (
          <div className="mt-4 p-3 bg-white/50 rounded-lg">
            <p className="text-sm font-medium mb-1">Dinamica de relacion:</p>
            <p className="text-sm">{data.relationship_description}</p>
          </div>
        )}
      </div>
    </div>
  );
}
