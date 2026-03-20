'use client';

import type { TestQuestionData } from '@/lib/types';

interface Props {
  data: TestQuestionData;
  onAnswer: (optionId: string) => void;
  disabled?: boolean;
}

export default function TestQuestion({ data, onAnswer, disabled }: Props) {
  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[90%] bg-[#F1DCF4] text-[#042648] px-4 py-4 rounded-2xl rounded-bl-md">
        <span className="text-xs font-semibold block mb-1 opacity-70">Eldric</span>

        {/* Progress */}
        <div className="flex items-center gap-2 mb-3">
          <div className="flex-1 h-2 bg-[#042648]/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#042648] rounded-full transition-all"
              style={{ width: `${(data.question_number / data.total_questions) * 100}%` }}
            />
          </div>
          <span className="text-xs font-medium">
            {data.question_number}/{data.total_questions}
          </span>
        </div>

        {/* Question */}
        <p className="font-medium mb-3">{data.question_text}</p>

        {/* Error */}
        {data.error && (
          <p className="text-red-500 text-sm mb-2">{data.error}</p>
        )}

        {/* Options */}
        <div className="space-y-2">
          {data.options.map((option) => (
            <button
              key={option.id}
              onClick={() => onAnswer(option.id)}
              disabled={disabled}
              className="w-full text-left px-3 py-2.5 bg-white/60 hover:bg-white rounded-lg text-sm transition disabled:opacity-50"
            >
              <span className="font-semibold">{option.id})</span> {option.text}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
