export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user_id: string;
  email: string;
  is_premium: boolean;
  preferred_language: string;
}

export interface ChatResponse {
  type: 'session' | 'greeting' | 'test_question' | 'test_results' | 'conversation' | 'paywall' | 'partner_offer' | 'affirmation' | 'collecting_info';
  data: ChatData;
  language: string;
}

export type ChatData = Record<string, unknown> & {
  message?: string;
  recap_message?: string;
  history_count?: number;
  messages?: StoredChatMessage[];
  options?: TestOption[];
  debug?: BotDebugTrace;
};

export interface StoredChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface BotDebugTrace {
  enabled: boolean;
  mode: string;
  note: string;
  reasoning_summary: string;
  steps: BotDebugStep[];
}

export interface BotDebugStep {
  stage: string;
  title: string;
  detail: string;
  payload: Record<string, unknown>;
}

export interface DebugSession {
  id: string;
  userMessage: string;
  status: 'processing' | 'complete' | 'error';
  startedAt: Date;
  completedAt?: Date;
  trace?: BotDebugTrace;
}

export interface TestOption {
  id: string;
  text: string;
}

export interface TestQuestionData {
  question_number: number;
  total_questions: number;
  question_text: string;
  options: TestOption[];
  test_type: string;
  error?: string;
}

export interface TestResultsData {
  attachment_style: string;
  scores: {
    secure: number;
    anxious: number;
    avoidant: number;
    disorganized: number;
  };
  description: string;
  test_type: string;
  relationship_status?: string;
  relationship_description?: string;
}

export interface GreetingData {
  message: string;
  options: TestOption[];
  is_first_visit: boolean;
}

export interface UserProfile {
  nombre: string | null;
  edad: number | null;
  genero: string | null;
  tiene_pareja: boolean | null;
  nombre_pareja: string | null;
  edad_pareja: number | null;
  genero_pareja: string | null;
  tiempo_pareja: string | null;
  orientacion: string | null;
  tipo_relacion: string | null;
  convive_con_pareja: boolean | null;
  tiene_hijos: boolean | null;
  attachment_style: string | null;
  partner_attachment_style: string | null;
  relationship_status: string | null;
  preferred_language: string;
  is_premium: boolean;
  email_verified: boolean;
}

export interface UserMemory {
  id: string;
  type: string;
  summary: string;
  curated_summary: string | null;
  visibility: string;
  sensitivity: string;
  confidence: number;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface KnowledgeChunk {
  id: string;
  article_id: string;
  title: string;
  section: string;
  content: string;
  preview: string;
  domain: string;
  language: string;
  topics: string[];
  source_notes: string | null;
}

export interface KnowledgeBrain {
  chunks: KnowledgeChunk[];
  domains: Record<string, number>;
  articles: Record<string, number>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: ChatResponse['type'];
  data?: ChatData;
  timestamp: Date;
}
