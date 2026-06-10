import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, Campaign, Communication } from "../api";
import { usePolling } from "../usePolling";
import { StatusBadge } from "../components";

export function Campaigns({ focusId, clearFocus }: { focusId: number | null; clearFocus: () => void }) {
  const [selected, setSelected] = useState<number | null>(focusId);
  useEffect(() => { if (focusId) setSelected(focusId); }, [focusId]);

  if (selected) return <CampaignDetail id={selected} onBack={() => { setSelected(null); clearFocus(); }} />;
  return <CampaignList onSelect={setSelected} />;
}

function CampaignList({ onSelect }: { onSelect: (id: number) => void }) {
  const { data: campaigns } = usePolling(() => api.campaigns(), 4000);

  return (
    <div>
      <h1 className="page-title">Campaigns</h1>
      <p className="page-sub">Every campaign the copilot staged. Open one to watch its live delivery funnel.</p>
      <div className="card">
        {!campaigns?.length ? (
          <div className="empty">No campaigns yet. Ask the AI Copilot to create one.</div>
        ) : (
          <table>
            <thead><tr><th>#</th><th>Name</th><th>Channel</th><th>Status</th><th>Created</th><th></th></tr></thead>
            <tbody>
              {campaigns.map((c: Campaign) => (
                <tr key={c.id}>
                  <td className="muted">{c.id}</td>
                  <td>{c.name}</td>
                  <td>{c.channel}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="muted">{new Date(c.created_at).toLocaleString()}</td>
                  <td><button className="btn ghost sm" onClick={() => onSelect(c.id)}>Open →</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const FUNNEL_COLORS: Record<string, string> = {
  sent: "#b14cff", delivered: "#36d399", opened: "#cda6ff",
  read: "#a78bfa", clicked: "#fbbd23", converted: "#ff2e74",
};

function CampaignDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const [launching, setLaunching] = useState(false);
  const { data: stats } = usePolling(() => api.campaignStats(id), 2000);
  const { data: comms } = usePolling(() => api.communications(id), 2500);
  const status = stats?.status ?? "";
  const isLive = status === "launching" || (status === "sent" && !!stats && stats.funnel.sent < stats.funnel.audience);

  async function launch() {
    setLaunching(true);
    try { await api.launch(id); } catch (e) { alert((e as Error).message); } finally { setLaunching(false); }
  }

  if (!stats) return <div className="empty">Loading…</div>;

  const f = stats.funnel;
  const chartData = (["sent", "delivered", "opened", "read", "clicked", "converted"] as const)
    .map((k) => ({ stage: k, value: f[k] }));

  return (
    <div>
      <button className="back" onClick={onBack}>← All campaigns</button>
      <div className="row-between">
        <div>
          <h1 className="page-title" style={{ marginBottom: 2 }}>{stats.campaign_name}</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {stats.channel} · <StatusBadge status={status} />
            {isLive && <span className="pill-live" style={{ marginLeft: 10 }}><span className="blink" /> live</span>}
          </p>
        </div>
        {status === "draft" && (
          <button className="btn" onClick={launch} disabled={launching}>
            {launching ? "Launching…" : "Approve & Launch"}
          </button>
        )}
      </div>

      <div className="kpis" style={{ marginTop: 18 }}>
        <Kpi v={f.audience.toLocaleString()} l="Audience" />
        <Kpi v={pct(stats.rates.delivery_rate)} l="Delivery rate" />
        <Kpi v={pct(stats.rates.open_rate)} l="Open rate" />
        <Kpi v={`₹${stats.attributed_revenue.toLocaleString()}`} l="Attributed revenue" />
      </div>

      <div className="grid-2">
        <div className="card">
          <h4 className="muted" style={{ marginTop: 0 }}>Delivery & engagement funnel</h4>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a2540" vertical={false} />
              <XAxis dataKey="stage" stroke="#9a93b3" fontSize={12} />
              <YAxis stroke="#9a93b3" fontSize={12} />
              <Tooltip contentStyle={{ background: "#16131f", border: "1px solid #2a2540", borderRadius: 10 }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {chartData.map((d) => <Cell key={d.stage} fill={FUNNEL_COLORS[d.stage]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {f.failed > 0 && <>⚠️ {f.failed} failed · </>}
            {f.clicked} clicked · {f.converted} converted
          </div>
        </div>

        <div className="card" style={{ maxHeight: 360, overflowY: "auto" }}>
          <h4 className="muted" style={{ marginTop: 0 }}>Recipients ({comms?.length ?? 0})</h4>
          <table>
            <thead><tr><th>Customer</th><th>Status</th><th>₹</th></tr></thead>
            <tbody>
              {comms?.map((c: Communication) => (
                <tr key={c.id}>
                  <td>{c.customer}</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td className="muted">{c.conversion_value ? `₹${c.conversion_value}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

const Kpi = ({ v, l }: { v: string; l: string }) => (
  <div className="kpi"><div className="v">{v}</div><div className="l">{l}</div></div>
);
const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
