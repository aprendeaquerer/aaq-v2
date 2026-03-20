'use client';

import Link from 'next/link';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import { useLanguage } from '@/hooks/useLanguage';

export default function Home() {
  const { t } = useLanguage();

  return (
    <>
      <Header />
      <main className="flex-1">
        {/* Hero */}
        <section className="bg-gradient-to-b from-[#FFF6EA] to-white py-20 px-4">
          <div className="max-w-4xl mx-auto text-center">
            <h1 className="text-5xl font-bold text-[#042648] mb-4">
              {t('landing.title')}
            </h1>
            <p className="text-xl text-[#042648]/70 mb-2">
              {t('landing.subtitle')}
            </p>
            <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
              {t('landing.description')}
            </p>
            <Link
              href="/chat"
              className="inline-block bg-[#042648] text-white px-8 py-4 rounded-xl text-lg font-semibold hover:bg-[#042648]/90 transition"
            >
              {t('landing.cta')}
            </Link>
          </div>
        </section>

        {/* Features */}
        <section className="py-16 px-4">
          <div className="max-w-5xl mx-auto grid md:grid-cols-3 gap-8">
            {[
              { title: t('landing.feature1_title'), desc: t('landing.feature1_desc'), icon: '📋' },
              { title: t('landing.feature2_title'), desc: t('landing.feature2_desc'), icon: '💬' },
              { title: t('landing.feature3_title'), desc: t('landing.feature3_desc'), icon: '📚' },
            ].map((feature) => (
              <div
                key={feature.title}
                className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 text-center"
              >
                <div className="text-4xl mb-4">{feature.icon}</div>
                <h3 className="text-lg font-semibold text-[#042648] mb-2">
                  {feature.title}
                </h3>
                <p className="text-gray-600">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
