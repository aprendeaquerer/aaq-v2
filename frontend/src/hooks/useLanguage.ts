'use client';

import { useState, useCallback } from 'react';
import type { Language } from '@/lib/constants';
import esMessages from '@/i18n/messages/es.json';
import enMessages from '@/i18n/messages/en.json';
import ruMessages from '@/i18n/messages/ru.json';

type TranslationTree = {
  [key: string]: string | TranslationTree;
};

const languages: Language[] = ['es', 'en', 'ru'];

const messages: Record<Language, TranslationTree> = {
  es: esMessages,
  en: enMessages,
  ru: ruMessages,
};

function getStoredLanguage(): Language {
  if (typeof window === 'undefined') return 'es';

  const stored = localStorage.getItem('language');
  return languages.includes(stored as Language) ? (stored as Language) : 'es';
}

export function useLanguage() {
  const [language, setLanguageState] = useState<Language>(() => getStoredLanguage());

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('language', lang);
  }, []);

  const t = useCallback(
    (key: string): string => {
      const parts = key.split('.');
      let value: string | TranslationTree | undefined = messages[language];
      for (const part of parts) {
        value = typeof value === 'object' ? value[part] : undefined;
      }
      return typeof value === 'string' ? value : key;
    },
    [language]
  );

  return { language, setLanguage, t };
}
