import { useEffect, useState } from "react";
import { api, Customer, CustomerStats } from "../api";

export function Customers() {
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [rows, setRows] = useState<Customer[]>([]);

  useEffect(() => {
    api.customerStats().then(setStats).catch(() => {});
    api.customers(50).then(setRows).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="page-title">Customers</h1>
      <p className="page-sub">The shopper base the copilot segments over — simulated SUGAR Cosmetics data.</p>

      <div className="kpis">
        <Kpi v={stats?.customers.toLocaleString() ?? "—"} l="Customers" />
        <Kpi v={stats?.orders.toLocaleString() ?? "—"} l="Orders" />
        <Kpi v={stats ? `₹${stats.lifetime_revenue.toLocaleString()}` : "—"} l="Lifetime revenue" />
        <Kpi v={stats ? `₹${Math.round(stats.lifetime_revenue / Math.max(stats.customers, 1)).toLocaleString()}` : "—"} l="Avg LTV" />
      </div>

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

const Kpi = ({ v, l }: { v: string; l: string }) => (
  <div className="kpi"><div className="v">{v}</div><div className="l">{l}</div></div>
);
