'use client';

import { useLanguage } from '@/hooks/useLanguage';
import type { Language } from '@/lib/constants';

const labels: Record<Language, string> = {
  es: 'Espanol',
  en: 'English',
  ru: 'Русский',
};

export default function LanguageSwitcher() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="flex gap-2">
      {(['es', 'en', 'ru'] as Language[]).map((lang) => (
        <button
          key={lang}
          onClick={() => setLanguage(lang)}
          className={`px-3 py-1 text-sm rounded ${
            language === lang
              ? 'bg-[#042648] text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {labels[lang]}
        </button>
      ))}
    </div>
  );
}
