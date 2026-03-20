'use client';

import { useLanguage } from '@/hooks/useLanguage';

export default function TypingIndicator() {
  const { t } = useLanguage();

  return (
    <div className="flex justify-start mb-3">
      <div className="bg-[#F1DCF4] text-[#042648] px-4 py-3 rounded-2xl rounded-bl-md">
        <span className="text-xs font-semibold block mb-1 opacity-70">Eldric</span>
        <div className="flex items-center gap-1">
          <span className="text-sm italic opacity-70">{t('chat.thinking')}</span>
          <span className="flex gap-1 ml-1">
            <span className="w-1.5 h-1.5 bg-[#042648]/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-[#042648]/40 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-[#042648]/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        </div>
      </div>
    </div>
  );
}
