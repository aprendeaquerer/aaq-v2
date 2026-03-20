'use client';

import type { ChatMessage } from '@/lib/types';

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-[#042648] text-white rounded-br-md'
            : 'bg-[#F1DCF4] text-[#042648] rounded-bl-md'
        }`}
      >
        {!isUser && (
          <span className="text-xs font-semibold block mb-1 opacity-70">Eldric</span>
        )}
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}
