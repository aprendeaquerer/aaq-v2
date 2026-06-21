import Header from '@/components/layout/Header';
import type { BrainTab } from '@/components/chat/DataBrainPanel';
import BrainWindow from './BrainWindow';

type BrainPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function BrainPage({ searchParams }: BrainPageProps) {
  const params = searchParams ? await searchParams : {};
  const initialTab = parseBrainTab(params.tab);

  return (
    <>
      <Header />
      <BrainWindow initialTab={initialTab} />
    </>
  );
}

function parseBrainTab(value: string | string[] | undefined): BrainTab {
  const tab = Array.isArray(value) ? value[0] : value;
  if (tab === 'data' || tab === 'knowledge' || tab === 'live') {
    return tab;
  }
  return 'knowledge';
}

