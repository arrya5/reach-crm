import { useEffect, useState } from "react";
import { api, Segment } from "../api";

export function Segments() {
  const [rows, setRows] = useState<Segment[]>([]);
  useEffect(() => { api.segments().then(setRows).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="page-title">Segments</h1>
      <p className="page-sub">Audiences the copilot carved out of the shopper base, each a saved Filter DSL.</p>
      <div className="card">
        {!rows.length ? (
          <div className="empty">No segments yet. The AI Copilot creates these as it works.</div>
        ) : (
          <table>
            <thead><tr><th>#</th><th>Name</th><th>Size</th><th>Definition</th><th>By</th></tr></thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id}>
                  <td className="muted">{s.id}</td>
                  <td>{s.name}</td>
                  <td>{s.est_count.toLocaleString()}</td>
                  <td><code className="k">{describe(s.definition)}</code></td>
                  <td><span className="badge b-draft">{s.created_via}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function describe(def: any): string {
  if (!def?.conditions?.length) return "all customers";
  const join = def.match === "any" ? " OR " : " AND ";
  return def.conditions
    .map((c: any) => `${c.field} ${c.op} ${Array.isArray(c.value) ? `[${c.value.join(", ")}]` : c.value}`)
    .join(join);
}
