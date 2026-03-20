'use client';

import { useState, useCallback, useEffect } from 'react';
import type { Language } from '@/lib/constants';
import esMessages from '@/i18n/messages/es.json';
import enMessages from '@/i18n/messages/en.json';
import ruMessages from '@/i18n/messages/ru.json';

const messages: Record<Language, Record<string, any>> = {
  es: esMessages,
  en: enMessages,
  ru: ruMessages,
};

export function useLanguage() {
  const [language, setLanguageState] = useState<Language>('es');

  useEffect(() => {
    const stored = localStorage.getItem('language') as Language;
    if (stored && ['es', 'en', 'ru'].includes(stored)) {
      setLanguageState(stored);
    }
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('language', lang);
  }, []);

  const t = useCallback(
    (key: string): string => {
      const parts = key.split('.');
      let value: any = messages[language];
      for (const part of parts) {
        value = value?.[part];
      }
      return (typeof value === 'string' ? value : key) as string;
    },
    [language]
  );

  return { language, setLanguage, t };
}
