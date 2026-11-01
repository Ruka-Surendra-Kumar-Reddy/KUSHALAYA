import { api } from "@/lib/api";

export type RecommendationChatMessage = {
  id: number;
  role: string;
  content: string;
  structured?: {
    answer?: string;
    recommendations?: Array<{
      product_id?: string | null;
      solution_id?: string | null;
      priority?: string;
      reason?: string;
      linked_rubric_item_ids?: string[];
      requires_human_review?: boolean;
      review_reason?: string | null;
    }>;
    confidence?: number;
    requires_human_review?: boolean;
    reason_for_review?: string | null;
    cited_rubric_item_ids?: string[];
  } | null;
  validation_status?: string | null;
  requires_human_review: boolean;
  latency_ms?: number | null;
  created_at: string;
};

export type RecommendationConversation = {
  id: string;
  assessment_id: string;
  elder_id?: number | null;
  prospect_id?: number | null;
  title: string;
  status: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  messages?: RecommendationChatMessage[];
};

export type SendRecommendationMessageResult = {
  conversation: RecommendationConversation;
  user_message: RecommendationChatMessage;
  assistant_message: RecommendationChatMessage;
  azure_configured: boolean;
};

export async function createRecommendationConversation(
  assessmentId: string,
  title?: string,
): Promise<RecommendationConversation> {
  return api<RecommendationConversation>("/api/v1/home-safety/recommendation-chat/conversations", {
    method: "POST",
    body: JSON.stringify({
      assessment_id: assessmentId,
      title: title || undefined,
    }),
  });
}

export async function listRecommendationConversations(
  assessmentId: string,
): Promise<RecommendationConversation[]> {
  const qs = new URLSearchParams({ assessment_id: assessmentId });
  return api<RecommendationConversation[]>(
    `/api/v1/home-safety/recommendation-chat/conversations?${qs.toString()}`,
  );
}

export async function getRecommendationConversation(
  conversationId: string,
): Promise<RecommendationConversation> {
  return api<RecommendationConversation>(
    `/api/v1/home-safety/recommendation-chat/conversations/${encodeURIComponent(conversationId)}`,
  );
}

export async function sendRecommendationMessage(
  conversationId: string,
  content: string,
): Promise<SendRecommendationMessageResult> {
  return api<SendRecommendationMessageResult>(
    `/api/v1/home-safety/recommendation-chat/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ content }),
    },
  );
}
