import { API_URL } from './constants';
import type { LoginResponse, ChatResponse, UserProfile, UserMemory, KnowledgeBrain } from './types';

function getTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === 'undefined') return { access: null, refresh: null };
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  };
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

export function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const { access } = getTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (access) {
    headers['Authorization'] = `Bearer ${access}`;
  }

  let response = await fetch(url, { ...options, headers });

  // If 401, try refreshing the token
  if (response.status === 401) {
    const { refresh } = getTokens();
    if (refresh) {
      const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (refreshRes.ok) {
        const data: LoginResponse = await refreshRes.json();
        setTokens(data.access_token, data.refresh_token);
        headers['Authorization'] = `Bearer ${data.access_token}`;
        response = await fetch(url, { ...options, headers });
      } else {
        clearTokens();
      }
    }
  }

  return response;
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
  if (!res.ok) throw new Error('Failed to send message');
  return res.json();
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
  const res = await fetchWithAuth(`${API_URL}/brain/knowledge${query}`);
  if (!res.ok) throw new Error('Failed to fetch knowledge brain');
  return res.json();
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
