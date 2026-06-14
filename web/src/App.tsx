import { useState } from "react";
import { Overview } from "./views/Overview";
import { Chat } from "./views/Chat";
import { Campaigns } from "./views/Campaigns";
import { Customers } from "./views/Customers";
import { Segments } from "./views/Segments";

type View = "overview" | "chat" | "campaigns" | "customers" | "segments";

const NAV: { key: View; label: string; icon: string }[] = [
  { key: "overview", label: "Home", icon: "🏠" },
  { key: "chat", label: "AI Copilot", icon: "✨" },
  { key: "campaigns", label: "Campaigns", icon: "📣" },
  { key: "segments", label: "Segments", icon: "🎯" },
  { key: "customers", label: "Customers", icon: "👥" },
];

export function App() {
  const [view, setView] = useState<View>("overview");
  const [campaignFocus, setCampaignFocus] = useState<number | null>(null);
  const [chatSeed, setChatSeed] = useState<string | null>(null);

  const goCampaign = (id: number) => { setCampaignFocus(id); setView("campaigns"); };
  const goChat = (seed?: string) => { setChatSeed(seed ?? null); setView("chat"); };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          Reach<span className="dot">.</span>
          <small>AI CRM · SUGAR Cosmetics (demo)</small>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <button
              key={n.key}
              className={view === n.key ? "active" : ""}
              onClick={() => { setView(n.key); if (n.key !== "campaigns") setCampaignFocus(null); }}
            >
              <span>{n.icon}</span> {n.label}
            </button>
          ))}
        </nav>
        <div className="spacer" />
        <div className="foot">
          Simulated data — not affiliated with SUGAR Cosmetics. Built for the Xeno take-home.
        </div>
      </aside>

      <main className="main">
        {view === "overview" && <Overview onStartChat={goChat} onOpenCampaign={goCampaign} />}
        {view === "chat" && <Chat onOpenCampaign={goCampaign} seed={chatSeed} />}
        {view === "campaigns" && <Campaigns focusId={campaignFocus} clearFocus={() => setCampaignFocus(null)} />}
        {view === "segments" && <Segments />}
        {view === "customers" && <Customers />}
      </main>
    </div>
  );
}
