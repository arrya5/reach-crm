// Thin typed client over the CRM API. One place owns the base URL + fetch.
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// --- types ---------------------------------------------------------------
export interface Customer {
  id: number; name: string; email: string; phone: string; city: string; gender: string; tags: string[];
}
export interface CustomerStats { customers: number; orders: number; lifetime_revenue: number; }
export interface Campaign {
  id: number; name: string; goal_text: string; segment_id: number;
  channel: string; message_template: string; status: string; created_at: string;
}
export interface Funnel {
  audience: number; sent: number; delivered: number; opened: number;
  read: number; clicked: number; converted: number; failed: number;
}
export interface CampaignStats {
  campaign_id: number; campaign_name: string; channel: string; status: string;
  funnel: Funnel;
  rates: { delivery_rate: number; open_rate: number; click_rate: number; conversion_rate: number };
  attributed_revenue: number;
}
export interface Communication {
  id: number; customer: string; recipient: string; status: string;
  failure_reason: string | null; conversion_value: number | null; message: string;
}
export interface Segment {
  id: number; name: string; definition: any; est_count: number; created_via: string; created_at: string;
}
export interface ChatAction { tool: string; args: Record<string, any>; result: any; }
export interface ChatResponse { conversation_id: string; reply: string; actions: ChatAction[]; }

// --- calls ---------------------------------------------------------------
export const api = {
  health: () => req<{ llm_provider: string; configured: boolean }>("/agent/health"),
  customerStats: () => req<CustomerStats>("/customers/stats"),
  customers: (limit = 50, offset = 0) => req<Customer[]>(`/customers?limit=${limit}&offset=${offset}`),
  segments: () => req<Segment[]>("/segments"),
  campaigns: () => req<Campaign[]>("/campaigns"),
  campaignStats: (id: number) => req<CampaignStats>(`/campaigns/${id}/stats`),
  communications: (id: number) => req<Communication[]>(`/campaigns/${id}/communications?limit=200`),
  launch: (id: number) => req<{ campaign_id: number; recipients: number }>(`/campaigns/${id}/launch`, { method: "POST" }),
  chat: (message: string, conversation_id: string | null) =>
    req<ChatResponse>("/agent/chat", { method: "POST", body: JSON.stringify({ message, conversation_id }) }),
};
