export type PromptType =
  | 'zero-shot'
  | 'one-shot'
  | 'few-shot'
  | 'role-based'
  | 'json-based'
  | 'chain-of-thought';

export type OutputMode = 'text' | 'json';

export interface ModelSelection {
  id: string;
  name: string;
  symbol: string;
  provider: string;
}

export interface CompareRequest {
  prompt_type: PromptType;
  prompt_text: string;
  input_text: string;
  output_mode: OutputMode;
  role_override?: string;
  examples?: Array<{ input: string; output: string }>;
  models: ModelSelection[];
}

export interface ModelOutputResponse {
  output_id: number;
  model_name: string;
  model_symbol: string;
  provider_name: string;
  raw_response: string;
  parsed_json?: Record<string, unknown>;
  is_json_valid: boolean;
  latency_ms?: number;
}

export interface CompareResponse {
  run_id: number;
  created_at: string;
  outputs: ModelOutputResponse[];
}

export interface ModelsResponse {
  models: ModelSelection[];
}

export interface GlobalRunItem {
  run_id: number;
  created_at: string;
  prompt_type: string;
  output_mode: string;
  model_name: string;
  model_symbol: string;
  provider_name: string;
  input_text: string;
  prompt_text: string;
  raw_response: string;
  is_json_valid: boolean;
  accuracy?: number;
  clarity?: number;
  relevance?: number;
  failure_tags?: string[];
  notes?: string;
  is_saved: boolean;
}

export interface EvaluationRequest {
  output_id: number;
  accuracy: number;
  clarity: number;
  relevance: number;
  failure_tags: string[];
  notes?: string;
}
