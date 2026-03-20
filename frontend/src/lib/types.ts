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
  type: 'greeting' | 'test_question' | 'test_results' | 'conversation' | 'paywall' | 'partner_offer' | 'affirmation' | 'collecting_info';
  data: Record<string, any>;
  language: string;
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
  tiene_pareja: boolean | null;
  nombre_pareja: string | null;
  tiempo_pareja: string | null;
  attachment_style: string | null;
  partner_attachment_style: string | null;
  relationship_status: string | null;
  preferred_language: string;
  is_premium: boolean;
  email_verified: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: ChatResponse['type'];
  data?: Record<string, any>;
  timestamp: Date;
}
