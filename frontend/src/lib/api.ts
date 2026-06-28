import { API_URL } from './constants';
import knowledgeBrainFallback from '@/data/knowledgeBrain.json';
import type { LoginResponse, ChatResponse, UserProfile, UserMemory, KnowledgeBrain, KnowledgeChunk } from './types';

function getTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === 'undefined') return { access: null, refresh: null };
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  };
}

function setTokens(access: string, refresh: string) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
  window.dispatchEvent(new Event('aaq-auth-updated'));
}

export function hasAuthTokens(): boolean {
  const { access, refresh } = getTokens();
  return Boolean(access || refresh);
}

export function clearTokens() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.dispatchEvent(new Event('aaq-auth-cleared'));
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  let { access, refresh } = getTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (!access && refresh) {
    access = await refreshAccessToken(refresh);
    refresh = getTokens().refresh;
  }

  if (access) {
    headers['Authorization'] = `Bearer ${access}`;
  }

  let response = await fetch(url, { ...options, headers });

  // If 401, try refreshing the token
  if (response.status === 401) {
    refresh = getTokens().refresh;
    if (refresh) {
      const nextAccess = await refreshAccessToken(refresh);
      if (nextAccess) {
        headers['Authorization'] = `Bearer ${nextAccess}`;
        response = await fetch(url, { ...options, headers });
      }
    }
  }

  return response;
}

async function refreshAccessToken(refresh: string): Promise<string | null> {
  const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!refreshRes.ok) {
    clearTokens();
    return null;
  }

  const data: LoginResponse = await refreshRes.json();
  setTokens(data.access_token, data.refresh_token);
  localStorage.setItem('user', JSON.stringify({
    user_id: data.user_id,
    email: data.email,
    is_premium: data.is_premium,
    preferred_language: data.preferred_language,
  }));
  return data.access_token;
}

async function fetchWithoutAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  delete headers.Authorization;
  delete headers.authorization;
  return fetch(url, { ...options, headers });
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const body = await response.text().catch(() => '');
  const detail = body ? `${fallback} (${response.status}): ${body.slice(0, 300)}` : `${fallback} (${response.status})`;
  return new Error(detail);
}

// --- Auth ---

export async function register(email: string, password: string, language: string = 'es') {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, preferred_language: language }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Registration failed');
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Login failed');
  }
  const data: LoginResponse = await res.json();
  setTokens(data.access_token, data.refresh_token);
  localStorage.setItem('user', JSON.stringify({
    user_id: data.user_id,
    email: data.email,
    is_premium: data.is_premium,
    preferred_language: data.preferred_language,
  }));
  return data;
}

export async function sendVerificationCode(email: string) {
  const res = await fetch(`${API_URL}/auth/send-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error('Failed to send verification code');
  return res.json();
}

export async function verifyEmail(email: string, code: string) {
  const res = await fetch(`${API_URL}/auth/verify-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error('Verification failed');
  return res.json();
}

// --- Chat ---

export async function getChatSession(
  language: string = 'es',
  guestId?: string,
  debug: boolean = false
): Promise<ChatResponse> {
  const params = new URLSearchParams({ language, debug: String(debug) });
  if (guestId) params.set('guest_id', guestId);

  const res = await fetchWithAuth(`${API_URL}/chat/session?${params.toString()}`);
  if (res.ok) return res.json();

  const fallbackRes = await fetchWithoutAuth(`${API_URL}/chat/session?${params.toString()}`);
  if (fallbackRes.ok) return fallbackRes.json();

  throw await responseError(res, 'Failed to load chat session');
}

export async function sendMessage(
  message: string,
  language: string = 'es',
  guestId?: string,
  debug: boolean = false
): Promise<ChatResponse> {
  const body: Record<string, string | boolean> = { message, language, debug };
  if (guestId) body.guest_id = guestId;

  const res = await fetchWithAuth(`${API_URL}/chat/message`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (res.ok) return res.json();

  const fallbackRes = await fetchWithoutAuth(`${API_URL}/chat/message`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  if (fallbackRes.ok) return fallbackRes.json();

  throw await responseError(res, 'Failed to send message');
}

// --- Profile ---

export async function getProfile(): Promise<UserProfile> {
  const res = await fetchWithAuth(`${API_URL}/profile`);
  if (!res.ok) throw new Error('Failed to fetch profile');
  return res.json();
}

export async function updateProfile(updates: Partial<UserProfile>): Promise<UserProfile> {
  const res = await fetchWithAuth(`${API_URL}/profile`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error('Failed to update profile');
  return res.json();
}

// --- Memory ---

export async function getUserMemories(): Promise<UserMemory[]> {
  const res = await fetchWithAuth(`${API_URL}/memory`);
  if (!res.ok) throw new Error('Failed to fetch memories');
  const data: { memories: UserMemory[] } = await res.json();
  return data.memories;
}

export async function updateUserMemory(id: string, updates: Partial<UserMemory>): Promise<UserMemory> {
  const res = await fetchWithAuth(`${API_URL}/memory/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error('Failed to update memory');
  return res.json();
}

// --- Brain ---

export async function getKnowledgeBrain(language?: string): Promise<KnowledgeBrain> {
  const query = language ? `?language=${encodeURIComponent(language)}` : '';
  try {
    const res = await fetchWithAuth(`${API_URL}/brain/knowledge${query}`);
    if (!res.ok) throw new Error('Failed to fetch knowledge brain');
    return res.json();
  } catch {
    const fallback = {
      ...knowledgeBrainFallback,
      chunks: knowledgeBrainFallback.chunks.map((chunk) => {
        const lane = (chunk as { polarity_lane?: unknown }).polarity_lane;
        return {
          ...chunk,
          polarity_lane: typeof lane === 'string' ? lane : '',
        };
      }),
    } as KnowledgeBrain;
    if (!language) return fallback;
    const chunks = fallback.chunks.filter((chunk) => chunk.language === language || chunk.language === 'multi' || chunk.language === '');
    return {
      chunks,
      domains: countBy(chunks, 'domain'),
      articles: countBy(chunks, 'article_id'),
    };
  }
}

function countBy(rows: KnowledgeChunk[], key: 'domain' | 'article_id'): Record<string, number> {
  return rows.reduce<Record<string, number>>((counts, row) => {
    counts[row[key]] = (counts[row[key]] || 0) + 1;
    return counts;
  }, {});
}

// --- Payment ---

export async function createCheckout(successUrl: string, cancelUrl: string) {
  const res = await fetchWithAuth(`${API_URL}/payment/create-checkout`, {
    method: 'POST',
    body: JSON.stringify({ success_url: successUrl, cancel_url: cancelUrl }),
  });
  if (!res.ok) throw new Error('Failed to create checkout');
  return res.json();
}
