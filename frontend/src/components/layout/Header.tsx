'use client';

import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { useLanguage } from '@/hooks/useLanguage';
import type { Language } from '@/lib/constants';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const { language, setLanguage, t } = useLanguage();

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-[#042648]">
          Aprende a Querer
        </Link>

        <div className="flex items-center gap-4">
          {/* Language switcher */}
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className="text-sm border rounded px-2 py-1"
          >
            <option value="es">ES</option>
            <option value="en">EN</option>
            <option value="ru">RU</option>
          </select>

          <Link href="/chat" className="text-sm text-[#042648] hover:underline">
            {t('nav.chat')}
          </Link>

          {isAuthenticated ? (
            <>
              <span className="text-sm text-gray-500">{user?.email}</span>
              <button
                onClick={logout}
                className="text-sm text-red-500 hover:underline"
              >
                {t('nav.logout')}
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-[#042648] hover:underline">
                {t('nav.login')}
              </Link>
              <Link
                href="/register"
                className="text-sm bg-[#042648] text-white px-4 py-2 rounded-lg hover:bg-[#042648]/90"
              >
                {t('nav.register')}
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
