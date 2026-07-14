'use client';

import { useState } from 'react';
import DataBrainPanel, { type BrainTab } from '@/components/chat/DataBrainPanel';
import { useAuth } from '@/hooks/useAuth';

const BRAIN_TABS: { id: BrainTab; label: string }[] = [
  { id: 'data', label: 'Data Brain' },
  { id: 'knowledge', label: 'Knowledge Brain' },
  { id: 'live', label: 'Live Fill' },
  { id: 'new-tests', label: 'New Personality Test' },
];

export default function BrainWindow({ initialTab }: { initialTab: BrainTab }) {
  const { isAuthenticated } = useAuth();
  const [activeTab, setActiveTab] = useState<BrainTab>(initialTab);

  const handleTabChange = (tab: BrainTab) => {
    setActiveTab(tab);
    window.history.replaceState(null, '', `/brain?tab=${tab}`);
  };

  return (
    <main className="flex h-[calc(100vh-4rem)] min-h-0 flex-col bg-[#FFF6EA]">
      <div className="border-b border-[#042648]/15 bg-white px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {BRAIN_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleTabChange(tab.id)}
              className={`rounded px-3 py-2 text-sm font-semibold transition ${
                activeTab === tab.id
                  ? 'bg-[#042648] text-white'
                  : 'border border-[#042648]/15 bg-white text-[#042648]/70 hover:bg-[#F8FAF7]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <DataBrainPanel
        activeTab={activeTab}
        debugSessions={[]}
        isAuthenticated={isAuthenticated}
        refreshKey={0}
        standalone
      />
    </main>
  );
}
