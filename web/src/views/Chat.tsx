import { useEffect, useRef, useState } from "react";
import { api, ChatAction } from "../api";

interface Bubble {
  role: "user" | "bot" | "tool" | "artifact";
  text?: string;
  action?: ChatAction;
}

const SUGGESTIONS = [
  "Win back customers who bought lipstick but haven't ordered in 60 days",
  "Find my top spenders in Mumbai and offer them early access to a new fragrance",
  "Re-engage one-time buyers with a skincare bundle over WhatsApp",
];

export function Chat({ onOpenCampaign }: { onOpenCampaign: (id: number) => void }) {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [input, setInput] = useState("");
  const [convId, setConvId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { api.health().then((h) => setConfigured(h.configured)).catch(() => setConfigured(false)); }, []);
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
      <h1 className="page-title">AI Copilot</h1>
      <p className="page-sub">
        Describe a goal in plain English. I’ll size the audience, draft the copy, pick a channel, and stage a campaign for your approval.
      </p>

      <div className="chat-scroll" ref={scrollRef}>
        {bubbles.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)}>{s}</button>
            ))}
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
      <div className="big">≈ {result.estimated_recipients?.toLocaleString()} recipients</div>
      <div className="muted" style={{ marginTop: 4 }}>Campaign #{result.campaign_id} · awaiting your approval</div>
      <div className="row-between" style={{ marginTop: 14 }}>
        <button className="btn" onClick={approve} disabled={busy || launched}>
          {launched ? "✓ Launched" : busy ? "Launching…" : "Approve & Launch"}
        </button>
        <button className="btn ghost sm" onClick={() => onOpenCampaign(result.campaign_id)}>Open campaign →</button>
      </div>
    </div>
  );
}
