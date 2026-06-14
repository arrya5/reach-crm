import { useEffect, useState } from "react";
import { api, Campaign, CustomerStats } from "../api";
import { StatusBadge } from "../components";

const STARTERS = [
  "Win back customers who bought lipstick but haven't ordered in 60 days",
  "Reward my top spenders in Mumbai with early access to a new fragrance",
  "Re-engage one-time buyers with a skincare bundle over WhatsApp",
];

const CHANNEL_COLOR: Record<string, string> = {
  whatsapp: "#2fe0a0", email: "#b14cff", sms: "#ffc24b", rcs: "#6d5cff",
};

export function Overview({
  onStartChat, onOpenCampaign,
}: { onStartChat: (seed?: string) => void; onOpenCampaign: (id: number) => void }) {
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  useEffect(() => {
    api.customerStats().then(setStats).catch(() => {});
    api.campaigns().then(setCampaigns).catch(() => {});
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  const mix = channelMix(campaigns);

  return (
    <div>
      <div className="hello">
        <h1 className="page-title" style={{ fontSize: 30, marginBottom: 4 }}>{greeting} 👋</h1>
        <p className="page-sub" style={{ marginBottom: 22 }}>
          Here's your shopper base — describe a goal and the AI copilot turns it into a launched campaign.
        </p>
      </div>

      <div className="kpis">
        <Kpi v={stats?.customers.toLocaleString() ?? "—"} l="Shoppers" />
        <Kpi v={stats?.orders.toLocaleString() ?? "—"} l="Orders" />
        <Kpi v={stats ? `₹${fmtMoney(stats.lifetime_revenue)}` : "—"} l="Lifetime revenue" />
        <Kpi v={stats ? `₹${Math.round(stats.lifetime_revenue / Math.max(stats.customers, 1)).toLocaleString()}` : "—"} l="Avg LTV" />
      </div>

      {/* AI launch CTA */}
      <div className="cta-card">
        <div className="cta-glow" />
        <div className="cta-eyebrow">✨ AI COPILOT</div>
        <h2 className="cta-title">Launch a campaign just by describing it</h2>
        <p className="muted" style={{ margin: "0 0 16px", maxWidth: 560 }}>
          No filters, no forms. State the goal — Reach sizes the audience, drafts the copy, picks the channel, and stages it for your approval.
        </p>
        <div className="starter-grid">
          {STARTERS.map((s) => (
            <button key={s} className="starter" onClick={() => onStartChat(s)}>
              <span className="starter-arrow">→</span> {s}
            </button>
          ))}
        </div>
        <button className="btn" style={{ marginTop: 16 }} onClick={() => onStartChat()}>Open the AI Copilot</button>
      </div>

      <div className="grid-2" style={{ marginTop: 18 }}>
        <div className="card">
          <h4 className="muted" style={{ marginTop: 0 }}>Recent campaigns</h4>
          {!campaigns.length ? (
            <div className="empty" style={{ padding: 28 }}>No campaigns yet — start one above.</div>
          ) : (
            <table>
              <tbody>
                {campaigns.slice(0, 6).map((c) => (
                  <tr key={c.id} style={{ cursor: "pointer" }} onClick={() => onOpenCampaign(c.id)}>
                    <td>{c.name}</td>
                    <td className="muted">{c.channel}</td>
                    <td style={{ textAlign: "right" }}><StatusBadge status={c.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <h4 className="muted" style={{ marginTop: 0 }}>Channel mix</h4>
          {!mix.length ? (
            <div className="empty" style={{ padding: 28 }}>Channels appear as you launch campaigns.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 6 }}>
              {mix.map((m) => (
                <div key={m.channel}>
                  <div className="row-between" style={{ marginBottom: 6 }}>
                    <span style={{ textTransform: "capitalize" }}>{m.channel}</span>
                    <span className="muted">{m.pct}%</span>
                  </div>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${m.pct}%`, background: CHANNEL_COLOR[m.channel] ?? "#b14cff" }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function channelMix(campaigns: Campaign[]) {
  if (!campaigns.length) return [];
  const counts: Record<string, number> = {};
  campaigns.forEach((c) => (counts[c.channel] = (counts[c.channel] ?? 0) + 1));
  const total = campaigns.length;
  return Object.entries(counts)
    .map(([channel, n]) => ({ channel, pct: Math.round((n / total) * 100) }))
    .sort((a, b) => b.pct - a.pct);
}

function fmtMoney(n: number): string {
  if (n >= 1e7) return `${(n / 1e7).toFixed(1)}Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(1)}L`;
  return n.toLocaleString();
}

const Kpi = ({ v, l }: { v: string; l: string }) => (
  <div className="kpi"><div className="v">{v}</div><div className="l">{l}</div></div>
);
