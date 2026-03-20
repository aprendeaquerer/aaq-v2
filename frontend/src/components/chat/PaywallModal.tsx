'use client';

import { useState } from 'react';
import { createCheckout } from '@/lib/api';

interface Props {
  message: string;
  onClose: () => void;
}

export default function PaywallModal({ message, onClose }: Props) {
  const [loading, setLoading] = useState(false);

  const handleUpgrade = async () => {
    setLoading(true);
    try {
      const { checkout_url } = await createCheckout(
        `${window.location.origin}/chat?success=true`,
        `${window.location.origin}/chat`
      );
      window.location.href = checkout_url;
    } catch {
      alert('Error creating checkout session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-start mb-3">
      <div className="max-w-[90%] bg-gradient-to-br from-[#F1DCF4] to-[#FFF6EA] text-[#042648] px-4 py-4 rounded-2xl rounded-bl-md border border-[#042648]/10">
        <span className="text-xs font-semibold block mb-1 opacity-70">Eldric</span>
        <p className="text-sm mb-4">{message}</p>

        <div className="flex gap-2">
          <button
            onClick={handleUpgrade}
            disabled={loading}
            className="bg-[#042648] text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-[#042648]/90 disabled:opacity-50"
          >
            {loading ? '...' : 'Premium $9.99'}
          </button>
          <button
            onClick={onClose}
            className="text-[#042648] px-4 py-2.5 rounded-lg text-sm hover:bg-white/50"
          >
            Mas tarde
          </button>
        </div>
      </div>
    </div>
  );
}
