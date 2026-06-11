import { useCallback, useEffect, useRef, useState } from "react";
import { api, Customer, CustomerStats } from "../api";
import { parseCsv, downloadFile } from "../csv";

export function Customers() {
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [rows, setRows] = useState<Customer[]>([]);

  const refresh = useCallback(() => {
    api.customerStats().then(setStats).catch(() => {});
    api.customers(50).then(setRows).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div>
      <h1 className="page-title">Customers</h1>
      <p className="page-sub">The shopper base the copilot segments over. Import your own, or use the seeded SUGAR Cosmetics data.</p>

      <div className="kpis">
        <Kpi v={stats?.customers.toLocaleString() ?? "—"} l="Customers" />
        <Kpi v={stats?.orders.toLocaleString() ?? "—"} l="Orders" />
        <Kpi v={stats ? `₹${stats.lifetime_revenue.toLocaleString()}` : "—"} l="Lifetime revenue" />
        <Kpi v={stats ? `₹${Math.round(stats.lifetime_revenue / Math.max(stats.customers, 1)).toLocaleString()}` : "—"} l="Avg LTV" />
      </div>

      <ImportPanel onDone={refresh} />

      <div className="card">
        <table>
          <thead><tr><th>Name</th><th>City</th><th>Email</th><th>Tags</th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.city}</td>
                <td className="muted">{c.email}</td>
                <td>{c.tags.map((t) => <span key={t} className="badge b-draft" style={{ marginRight: 4 }}>{t}</span>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ImportPanel({ onDone }: { onDone: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setMsg(null);
    try {
      const text = await file.text();
      let payload: { customers: any[]; orders: any[] };
      if (file.name.toLowerCase().endsWith(".json")) {
        const j = JSON.parse(text);
        payload = Array.isArray(j)
          ? { customers: j, orders: [] }
          : { customers: j.customers ?? [], orders: j.orders ?? [] };
      } else {
        // CSV is treated as a customers file (name,email,phone,city,gender,tags)
        const records = parseCsv(text);
        payload = {
          customers: records.map((r) => ({
            name: r.name, email: r.email, phone: r.phone || "",
            city: r.city || "Unknown", gender: r.gender || "other",
            tags: r.tags ? r.tags.split("|").filter(Boolean) : [],
          })),
          orders: [],
        };
      }
      const res = await api.ingest(payload);
      setMsg(
        `✓ Added ${res.customers_added} customers and ${res.orders_added} orders ` +
        `(skipped ${res.customers_skipped} dup customers, ${res.orders_skipped} unmatched orders).`
      );
      onDone();
    } catch (e) {
      setMsg("⚠️ " + (e as Error).message);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <h4 className="muted" style={{ marginTop: 0 }}>Ingest data</h4>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        Upload a <b>CSV</b> of customers, or a <b>JSON</b> file with customers + orders.
        New emails are added; existing ones are skipped (idempotent).
      </p>
      <div className="row-between" style={{ justifyContent: "flex-start", gap: 10 }}>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.json"
          disabled={busy}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          style={{ color: "var(--muted)" }}
        />
        <button className="btn ghost sm" onClick={() => downloadFile("customers-sample.csv", SAMPLE_CSV)}>Sample CSV</button>
        <button className="btn ghost sm" onClick={() => downloadFile("import-sample.json", SAMPLE_JSON)}>Sample JSON</button>
      </div>
      {busy && <div className="muted" style={{ marginTop: 10 }}>Importing…</div>}
      {msg && <div className="preview-msg" style={{ marginTop: 10 }}>{msg}</div>}
    </div>
  );
}

const SAMPLE_CSV = `name,email,phone,city,gender,tags
Asha Rao,asha@example.com,+919800000001,Mumbai,female,vip|skincare-fan
Ravi Kumar,ravi@example.com,+919800000002,Pune,male,new
Neha Singh,neha@example.com,+919800000003,Delhi,female,makeup-fan`;

const SAMPLE_JSON = JSON.stringify({
  customers: [
    { name: "Asha Rao", email: "asha@example.com", city: "Mumbai", gender: "female", tags: ["vip"] },
    { name: "Ravi Kumar", email: "ravi@example.com", city: "Pune", gender: "male" },
  ],
  orders: [
    { customer_email: "asha@example.com", amount: 799, category: "skincare", product_name: "Vitamin C Serum", ordered_at: "2026-05-01T10:00:00Z" },
    { customer_email: "ravi@example.com", amount: 499, category: "lipstick", product_name: "Matte Lipstick" },
  ],
}, null, 2);

const Kpi = ({ v, l }: { v: string; l: string }) => (
  <div className="kpi"><div className="v">{v}</div><div className="l">{l}</div></div>
);
