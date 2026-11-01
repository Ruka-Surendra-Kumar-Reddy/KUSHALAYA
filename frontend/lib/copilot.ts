import { api } from "./api";

export type CopilotSuggestions = {
  questions: string[];
  azure_openai_configured: boolean;
};

export type CopilotAskResponse = {
  answer: string;
  question: string;
  tenant_id: number;
  provider: string;
  model_version: string;
  data_sources: string[];
  context_as_of: string | null;
  suggested_follow_ups: string[];
};

export async function fetchCopilotSuggestions(): Promise<CopilotSuggestions> {
  return api<CopilotSuggestions>("/api/v1/copilot/suggestions");
}

export async function askCopilot(question: string): Promise<CopilotAskResponse> {
  return api<CopilotAskResponse>("/api/v1/copilot/ask", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
