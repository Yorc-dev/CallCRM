export interface User {
  id: number;
  username: string;
  role: 'operator' | 'chief' | 'admin';
}

export interface Client {
  id: number;
  full_name: string;
  phone: string;
  gender?: 'male' | 'female' | 'unknown';
  language?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

export interface CallRecording {
  id: number;
  file: string;
  uploaded_at: string;
}

export interface ScriptCompliance {
  [step: string]: boolean;
}

export interface CallAnalysis {
  id: number;
  call: number;
  transcript_text?: string;
  summary_short?: string;
  summary_structured?: Record<string, unknown>;
  script_compliance?: ScriptCompliance;
  operator_coaching?: string[];
  script_score?: number;
  category?: string;
  client_draft?: Partial<Client>;
  created_at: string;
}

export interface Call {
  id: number;
  client?: number;
  client_detail?: Client;
  operator: number;
  operator_detail?: User;
  started_at: string;
  ended_at?: string;
  duration?: number;
  status: 'new' | 'uploaded' | 'processing' | 'done' | 'failed';
  category?: string;
  recording?: CallRecording;
  analysis?: CallAnalysis;
}

export interface AnalyticsOverview {
  total_calls: number;
  done_calls: number;
  avg_script_score: number;
  categories_count: number;
  calls_per_day: { date: string; count: number }[];
}

export interface AnalyticsOperator {
  operator_id: number;
  username: string;
  total_calls: number;
  avg_script_score: number;
}

export interface AnalyticsCategory {
  category: string;
  count: number;
}
