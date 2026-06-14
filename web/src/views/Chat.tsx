import { useEffect, useRef, useState } from "react";
import { api, ChatAction, CustomerStats } from "../api";

interface Bubble {
  role: "user" | "bot" | "tool" | "artifact";
  text?: string;
  action?: ChatAction;
}

const SUGGESTIONS: { icon: string; title: string; text: string }[] = [
  { icon: "💄", title: "Win back lapsed buyers", text: "Win back customers who bought lipstick but haven't ordered in 60 days" },
  { icon: "⭐", title: "Reward your VIPs", text: "Find my top spenders in Mumbai and offer them early access to a new fragrance" },
  { icon: "🔁", title: "Re-engage one-timers", text: "Re-engage one-time buyers with a skincare bundle over WhatsApp" },
];

export function Chat({ onOpenCampaign, seed }: { onOpenCampaign: (id: number) => void; seed?: string | null }) {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [input, setInput] = useState(seed ?? "");
  const [convId, setConvId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api.health().then((h) => setConfigured(h.configured)).catch(() => setConfigured(false)); }, []);
  useEffect(() => { api.customerStats().then(setStats).catch(() => {}); }, []);
  useEffect(() => { if (seed) setInput(seed); }, [seed]);
  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [bubbles, busy]);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setBubbles((b) => [...b, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(message, convId);
      setConvId(res.conversation_id);
      const newBubbles: Bubble[] = res.actions.map((a) => ({ role: "artifact", action: a }));
      if (res.reply) newBubbles.push({ role: "bot", text: res.reply });
      setBubbles((b) => [...b, ...newBubbles]);
    } catch (e) {
      setBubbles((b) => [...b, { role: "bot", text: "⚠️ " + (e as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        {bubbles.length === 0 && (
          <div className="chat-hero">
            <div className="cta-eyebrow">✨ AI MARKETING COPILOT</div>
            <h1 className="hero-title">Turn a goal into a launched campaign<br /><span className="accent">just by asking.</span></h1>
            <p className="hero-sub">
              I size the audience, draft on-brand copy, recommend a channel, and stage the campaign for your approval.
            </p>
            {stats && (
              <div className="hero-stats">
                <span><b>{stats.customers.toLocaleString()}</b> shoppers</span>
                <i />
                <span><b>{stats.orders.toLocaleString()}</b> orders</span>
                <i />
                <span><b>₹{Math.round(stats.lifetime_revenue / 1e5)}L</b> lifetime revenue</span>
              </div>
            )}
            <div className="hero-cards">
              {SUGGESTIONS.map((s) => (
                <button key={s.title} className="hero-card" onClick={() => send(s.text)}>
                  <div className="hero-card-icon">{s.icon}</div>
                  <div className="hero-card-title">{s.title}</div>
                  <div className="hero-card-text">{s.text}</div>
                </button>
              ))}
            </div>
          </div>
        )}
        {bubbles.map((b, i) =>
          b.role === "artifact" && b.action ? (
            <Artifact key={i} action={b.action} onOpenCampaign={onOpenCampaign} />
          ) : (
            <div key={i} className={`msg ${b.role}`}>{b.text}</div>
          )
        )}
        {busy && <div className="msg bot">Thinking…</div>}
      </div>

      {configured === false && (
        <div className="msg tool">No GEMINI_API_KEY configured — the copilot is disabled. The dashboard tabs still work.</div>
      )}

      <div className="composer">
        <input
          value={input}
          placeholder="e.g. Win back lapsed lipstick buyers with a WhatsApp offer…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={busy || configured === false}
        />
        <button className="btn" onClick={() => send(input)} disabled={busy || configured === false}>Send</button>
      </div>
    </div>
  );
}

function Artifact({ action, onOpenCampaign }: { action: ChatAction; onOpenCampaign: (id: number) => void }) {
  const { tool, result } = action;

  // The agent occasionally proposes an invalid filter; the DSL rejects it and
  // the agent self-corrects. Render that recovery as a subtle note, not noise.
  if (result?.error) {
    return <div className="msg tool">⤷ {tool}: adjusted and retried</div>;
  }

  if (tool === "preview_audience") {
    return (
      <div className="artifact">
        <h4>Audience preview</h4>
        <div className="big">{result.estimated_count?.toLocaleString()} shoppers</div>
        <div className="muted" style={{ marginTop: 6 }}>{result.description}</div>
        {result.sample?.length > 0 && (
          <div className="muted" style={{ marginTop: 8, fontSize: 12.5 }}>
            e.g. {result.sample.map((s: any) => `${s.name} (${s.city})`).join(", ")}
          </div>
        )}
      </div>
    );
  }

  if (tool === "create_segment") {
    return (
      <div className="artifact">
        <h4>Segment created</h4>
        <div className="big">{result.name}</div>
        <div className="muted" style={{ marginTop: 6 }}>{result.estimated_count?.toLocaleString()} shoppers · segment #{result.segment_id}</div>
      </div>
    );
  }

  if (tool === "stage_campaign") {
    if (result.error) return <div className="msg tool">stage_campaign: {result.error}</div>;
    return <StagedCampaign result={result} onOpenCampaign={onOpenCampaign} />;
  }

  if (tool === "get_campaign_performance") {
    const f = result.funnel;
    return (
      <div className="artifact">
        <h4>Performance · {result.campaign_name}</h4>
        {f ? (
          <div className="muted">
            {f.sent} sent · {f.delivered} delivered · {f.opened} opened · {f.clicked} clicked · {f.converted} converted ·
            <b style={{ color: "var(--text)" }}> ₹{result.attributed_revenue?.toLocaleString()}</b> attributed
          </div>
        ) : <div className="muted">No data.</div>}
      </div>
    );
  }

  return <div className="msg tool">{tool}() → {JSON.stringify(result).slice(0, 160)}</div>;
}

function StagedCampaign({ result, onOpenCampaign }: { result: any; onOpenCampaign: (id: number) => void }) {
  const [launched, setLaunched] = useState(false);
  const [busy, setBusy] = useState(false);

  async function approve() {
    setBusy(true);
    try {
      await api.launch(result.campaign_id);
      setLaunched(true);
      onOpenCampaign(result.campaign_id);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="artifact">
      <h4>Campaign staged · draft</h4>
      <div className="big">{result.name ?? "New campaign"}</div>
      <div className="muted" style={{ marginTop: 6 }}>
        <span className="badge b-queued" style={{ marginRight: 8 }}>{result.channel}</span>
        ≈ {result.estimated_recipients?.toLocaleString()} recipients
        {result.audience ? ` · ${result.audience}` : ""}
      </div>
      {result.message_template && (
        <div className="preview-msg">{result.message_template}</div>
      )}
      <div className="row-between" style={{ marginTop: 14 }}>
        <button className="btn" onClick={approve} disabled={busy || launched}>
          {launched ? "✓ Launched" : busy ? "Launching…" : "Approve & Launch"}
        </button>
        <button className="btn ghost sm" onClick={() => onOpenCampaign(result.campaign_id)}>Open campaign →</button>
      </div>
    </div>
  );
}
