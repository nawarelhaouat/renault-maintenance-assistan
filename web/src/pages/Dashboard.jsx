import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { api } from "../api";

const pct = (v) => `${Math.round(v * 100)} %`;

function Kpi({ label, value, hint }) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <div className="kpi">{value}</div>
      {hint && <div className="muted small-text">{hint}</div>}
    </div>
  );
}

const delta = (now, prev, unit = "") => `${now - prev >= 0 ? "+" : ""}${Math.round((now - prev) * 10) / 10}${unit} vs 90 j précédents`;

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [fleet, setFleet] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [error, setError] = useState("");
  const [workshop, setWorkshop] = useState("");
  const [category, setCategory] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    Promise.all([api.summary(), api.fleet(), api.monthly()])
      .then(([s, f, m]) => {
        setSummary(s);
        setFleet(f.machines);
        setMonthly(m);
      })
      .catch((e) => setError(e.message));
  }, []);

  const workshops = useMemo(() => [...new Set(fleet.map((m) => m.workshop))].sort(), [fleet]);
  const categories = useMemo(() => [...new Set(fleet.map((m) => m.category))].sort(), [fleet]);
  const rows = fleet.filter((m) => (!workshop || m.workshop === workshop) && (!category || m.category === category));
  const maxRisk = Math.max(0.3, ...rows.map((m) => m.risk));
  const maxMonth = Math.max(1, ...monthly.map((m) => m.failures));

  if (error) return <div className="page"><div className="error">{error}</div></div>;
  if (!summary) return <div className="page muted">Chargement...</div>;

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <p className="muted">Données arrêtées au {summary.as_of}. Modèle entraîné sur un historique synthétique.</p>

      <div className="kpis">
        <Kpi label="Pannes (90 j)" value={summary.failures_90} hint={delta(summary.failures_90, summary.failures_prev)} />
        <Kpi label="Arrêt machine (h, 90 j)" value={summary.downtime_h_90} hint={delta(summary.downtime_h_90, summary.downtime_h_prev, " h")} />
        <Kpi label="Machines à risque élevé" value={summary.high_risk} hint={`sur ${summary.machines} machines`} />
        <Kpi label="Préventives en retard" value={summary.pm_late} />
      </div>

      <div className="toolbar">
        <h2>Risque de panne à 30 jours</h2>
        <div className="filters">
          <select value={workshop} onChange={(e) => setWorkshop(e.target.value)}>
            <option value="">Tous les ateliers</option>
            {workshops.map((w) => <option key={w}>{w}</option>)}
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Tous les types</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="card flush">
        <div className="scroll-x">
          <table className="table">
            <thead>
              <tr><th>Machine</th><th>Atelier</th><th>Niveau</th><th>Risque</th><th>Préventive</th><th>Pannes 90 j</th></tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.asset_tag} className="clickable" onClick={() => api.machineDetail(m.asset_tag).then(setDetail)}>
                  <td>{m.asset_tag}<div className="muted small-text">{m.model}</div></td>
                  <td>{m.workshop}</td>
                  <td><span className={`pill ${m.level === "Élevé" ? "high" : m.level === "Modéré" ? "mid" : ""}`}>{m.level}</span></td>
                  <td className="risk-cell">
                    <div className="bar"><i style={{ width: `${(m.risk / maxRisk) * 100}%` }} /></div>
                    <span>{pct(m.risk)}</span>
                  </td>
                  <td>{m.days_since_pm} j / {m.pm_days} j</td>
                  <td>{m.n_fail_90}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {detail && (
        <div className="card detail">
          <div className="row spread">
            <h2>{detail.machine.asset_tag} · {detail.machine.model}</h2>
            <button className="icon-btn" onClick={() => setDetail(null)} aria-label="Fermer"><X size={16} /></button>
          </div>
          <p>Risque à 30 jours : <strong>{pct(detail.machine.risk)}</strong> ({detail.machine.level}).</p>
          {detail.machine.drivers && <p className="muted">Facteurs : {detail.machine.drivers}</p>}
          <table className="table">
            <thead><tr><th>Date</th><th>Type</th><th>Code</th><th>Arrêt (min)</th><th>Coût (MAD)</th></tr></thead>
            <tbody>
              {detail.history.map((h, i) => (
                <tr key={i}><td>{h.date}</td><td>{h.type}</td><td>{h.code || "-"}</td><td>{h.downtime_min}</td><td>{Math.round(h.cost_mad)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="spaced">Pannes par mois (12 mois)</h2>
      <div className="card">
        {monthly.map((m) => (
          <div key={m.month} className="month-row">
            <span className="muted">{m.month}</span>
            <div className="bar"><i style={{ width: `${(m.failures / maxMonth) * 100}%` }} /></div>
            <span>{m.failures}</span>
          </div>
        ))}
      </div>
    </div>
  );
}