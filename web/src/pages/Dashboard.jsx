import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDown, ArrowUp, Download, MessageSquare, Search } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

const pct = (v) => `${Math.round(v * 100)}%`;
const PALETTE = { Automate: "#83c9ff", Presse: "#0068c9", Robot: "#ffabab", "Robot peinture": "#ff2b2b", Visseuse: "#7defa3" };
const FALLBACK = ["#ffd16a", "#a78bfa", "#94a3b8", "#f59e0b"];
const colorOf = (name, i) => PALETTE[name] || FALLBACK[i % FALLBACK.length];
const tip = { background: "var(--bg)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" };
const axis = { fill: "var(--muted)", fontSize: 12 };
const RANK = { "Élevé": 3, "Modéré": 2, "Faible": 1 };
const PERIODS = [90, 180, 365];

const COLUMNS = [
  { key: "asset_tag", label: "Machine" },
  { key: "model", label: "Modèle" },
  { key: "workshop", label: "Atelier" },
  { key: "level", label: "Niveau" },
  { key: "risk", label: "Risque 30 j" },
  { key: "late", label: "Retard préventive (j)", num: true },
  { key: "n_fail_90", label: "Pannes 90 j", num: true },
  { key: "drivers", label: "Facteurs principaux", nosort: true },
];

function Kpi({ label, value, hint }) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <div className="kpi">{value}</div>
      {hint && <div className="muted small-text">{hint}</div>}
    </div>
  );
}

const delta = (now, prev, days, unit = "") =>
  `${now - prev >= 0 ? "+" : ""}${Math.round((now - prev) * 10) / 10}${unit} vs ${days} j précédents`;

function flatten(obj, prefix = "", out = []) {
  for (const [k, v] of Object.entries(obj || {})) {
    const name = prefix ? `${prefix} · ${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, name, out);
    else if (typeof v === "number") out.push([name, Number.isInteger(v) ? String(v) : v.toFixed(3)]);
    else if (typeof v === "string" && v.length < 40) out.push([name, v]);
  }
  return out;
}

const parseDrivers = (s) =>
  (s || "").split(";").map((x) => x.trim()).filter(Boolean).map((x) => {
    const i = x.lastIndexOf("=");
    return i === -1 ? { label: x, value: "" } : { label: x.slice(0, i).trim(), value: x.slice(i + 1).trim() };
  });

function exportCsv(rows) {
  const head = ["Machine", "Modèle", "Atelier", "Niveau", "Risque 30 j (%)", "Retard préventive (j)", "Pannes 90 j", "Facteurs principaux"];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = rows.map((m) => [m.asset_tag, m.model, m.workshop, m.level, Math.round(m.risk * 1000) / 10, m.late, m.n_fail_90, m.drivers].map(esc).join(";"));
  const blob = new Blob(["\ufeff" + [head.map(esc).join(";"), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "risques_machines.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Dashboard() {
  const navigate = useNavigate();
  const detailRef = useRef(null);
  const [days, setDays] = useState(90);
  const [summary, setSummary] = useState(null);
  const [fleet, setFleet] = useState([]);
  const [monthly, setMonthly] = useState({ categories: [], data: [] });
  const [codes, setCodes] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [workshop, setWorkshop] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: "risk", dir: "desc" });
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    Promise.all([api.fleet(), api.monthly(), api.modelMetrics()])
      .then(([f, m, mm]) => {
        setFleet(f.machines.map((x) => ({ ...x, late: Math.max(0, x.days_since_pm - x.pm_days) })));
        setMonthly(m);
        setMetrics(mm.available ? mm.metrics : null);
        if (f.machines[0]) setSelected(f.machines[0].asset_tag);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    Promise.all([api.summary(days), api.failureCodes(days)])
      .then(([s, c]) => {
        setSummary(s);
        setCodes(c);
      })
      .catch((e) => setError(e.message));
  }, [days]);

  useEffect(() => {
    if (!selected) return;
    api.machineDetail(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected]);

  const workshops = useMemo(() => [...new Set(fleet.map((m) => m.workshop))].sort(), [fleet]);
  const categories = useMemo(() => [...new Set(fleet.map((m) => m.category))].sort(), [fleet]);

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = fleet.filter((m) =>
      (!workshop || m.workshop === workshop) && (!category || m.category === category) &&
      (!q || `${m.asset_tag} ${m.model}`.toLowerCase().includes(q)));
    const val = (m) => (sort.key === "level" ? RANK[m.level] || 0 : m[sort.key]);
    return [...list].sort((a, b) => {
      const x = val(a), y = val(b);
      const c = typeof x === "string" ? x.localeCompare(y) : x - y;
      return sort.dir === "asc" ? c : -c;
    });
  }, [fleet, workshop, category, search, sort]);

  const maxRisk = Math.max(0.3, ...rows.map((m) => m.risk));
  const top10 = [...rows].sort((a, b) => b.risk - a.risk).slice(0, 10)
    .map((m) => ({ machine: m.asset_tag, risque: Math.round(m.risk * 1000) / 10 }));

  const toggleSort = (c) => {
    if (c.nosort) return;
    setSort((s) => (s.key === c.key ? { key: c.key, dir: s.dir === "asc" ? "desc" : "asc" } : { key: c.key, dir: "desc" }));
  };
  const open = (tag) => {
    setSelected(tag);
    detailRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  if (error) return <div className="page"><div className="error">{error}</div></div>;
  if (!summary) return <div className="page muted">Chargement...</div>;

  const d = detail?.machine;
  const late = d ? Math.max(0, d.days_since_pm - d.pm_days) : 0;
  const drivers = parseDrivers(d?.drivers);
  const metricItems = metrics ? flatten(metrics) : [];

  return (
    <div className="page">
      <div className="toolbar">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">Données arrêtées au {summary.as_of}. Modèle entraîné sur un historique synthétique.</p>
        </div>
        <div className="seg" role="group" aria-label="Période">
          {PERIODS.map((p) => (
            <button key={p} className={p === days ? "on" : ""} onClick={() => setDays(p)}>{p} j</button>
          ))}
        </div>
      </div>

      <div className="kpis">
        <Kpi label={`Pannes (${days} j)`} value={summary.failures} hint={delta(summary.failures, summary.failures_prev, days)} />
        <Kpi label={`Arrêt machine (h, ${days} j)`} value={summary.downtime_h} hint={delta(summary.downtime_h, summary.downtime_h_prev, days, " h")} />
        <Kpi label="Machines à risque élevé" value={summary.high_risk} hint={`sur ${summary.machines} machines`} />
        <Kpi label="Préventives en retard" value={summary.pm_late} />
      </div>

      <div className="toolbar">
        <h2 className="section-title">Machines classées par risque de panne à 30 jours</h2>
        <div className="filters">
          <label className="search-box">
            <Search size={14} />
            <input placeholder="Rechercher une machine" value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <select value={workshop} onChange={(e) => setWorkshop(e.target.value)}>
            <option value="">Tous les ateliers</option>
            {workshops.map((w) => <option key={w}>{w}</option>)}
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Tous les types</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <button className="btn" onClick={() => exportCsv(rows)}><Download size={15} />CSV</button>
        </div>
      </div>

      <div className="card flush">
        <div className="scroll-x tall">
          <table className="table">
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.key} className={c.nosort ? "" : "sortable"} onClick={() => toggleSort(c)}>
                    <span className="th-inner">
                      {c.label}
                      {sort.key === c.key && (sort.dir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.asset_tag} className={`clickable ${m.asset_tag === selected ? "sel" : ""}`} onClick={() => open(m.asset_tag)}>
                  <td className="nowrap">{m.asset_tag}</td>
                  <td className="nowrap">{m.model}</td>
                  <td className="nowrap">{m.workshop}</td>
                  <td><span className={`pill ${m.level === "Élevé" ? "high" : m.level === "Modéré" ? "mid" : ""}`}>{m.level}</span></td>
                  <td>
                    <div className="risk-cell">
                      <div className="bar red"><i style={{ width: `${(m.risk / maxRisk) * 100}%` }} /></div>
                      <span>{pct(m.risk)}</span>
                    </div>
                  </td>
                  <td className="num">{m.late}</td>
                  <td className="num">{m.n_fail_90}</td>
                  <td className="nowrap">{m.drivers}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={COLUMNS.length} className="muted">Aucune machine ne correspond.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="charts">
        <div>
          <h2 className="section-title">Top 10 des risques</h2>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={top10} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="machine" tick={{ ...axis, angle: -90, textAnchor: "end" }} height={100} interval={0} />
              <YAxis tick={axis} unit="%" />
              <Tooltip contentStyle={tip} formatter={(v) => [`${v}%`, "Risque 30 j"]} />
              <Bar dataKey="risque" fill="#83c9ff" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h2 className="section-title">Pannes par mois et type de machine (12 mois)</h2>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={monthly.data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="month" tick={{ ...axis, angle: -90, textAnchor: "end" }} height={70} interval={0} />
              <YAxis tick={axis} allowDecimals={false} />
              <Tooltip contentStyle={tip} />
              <Legend />
              {monthly.categories.map((c, i) => <Bar key={c} dataKey={c} stackId="a" fill={colorOf(c, i)} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <h2 className="section-title spaced">Pannes par code de panne ({days} j)</h2>
      <p className="muted small-text">Diagramme de Pareto : les barres donnent le nombre de pannes, la courbe le cumul en pourcentage.</p>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={codes} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="code" tick={axis} />
          <YAxis yAxisId="l" tick={axis} allowDecimals={false} />
          <YAxis yAxisId="r" orientation="right" tick={axis} domain={[0, 100]} unit="%" />
          <Tooltip contentStyle={tip} formatter={(v, n, p) => (n === "Cumul" ? [`${v}%`, n] : [`${v} (${p.payload.downtime_h} h d'arrêt)`, n])} />
          <Legend />
          <Bar yAxisId="l" dataKey="failures" name="Pannes" fill="#83c9ff" />
          <Line yAxisId="r" dataKey="cumulative" name="Cumul" stroke="#ff4b4b" strokeWidth={2} dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>

      {metricItems.length > 0 && (
        <>
          <h2 className="section-title spaced">Qualité du modèle prédictif</h2>
          <p className="muted small-text">Mesurée sur une période de test, avec un historique synthétique : elle valide la chaîne de traitement, pas une performance industrielle.</p>
          <div className="mini-grid">
            {metricItems.map(([k, v]) => (
              <div key={k} className="card mini"><div className="metric-label">{k}</div><div className="mini-value">{v}</div></div>
            ))}
          </div>
        </>
      )}

      <h2 className="section-title spaced" ref={detailRef}>Détail d'une machine</h2>
      <label className="field">Machine
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {fleet.map((m) => <option key={m.asset_tag} value={m.asset_tag}>{m.asset_tag}</option>)}
        </select>
      </label>

      {d && (
        <>
          <div className="metrics">
            <div><div className="metric-label">Risque 30 j</div><div className="metric-value">{pct(d.risk)}</div></div>
            <div><div className="metric-label">Niveau</div><div className="metric-value">{d.level}</div></div>
            <div>
              <div className="metric-label">Jours depuis préventive</div>
              <div className="metric-value">{d.days_since_pm}</div>
              <span className="metric-hint">{late > 0 ? "↑ " : ""}plan : {d.pm_days} j</span>
            </div>
          </div>
          {drivers.length > 0 && (
            <div className="drivers">
              <div className="metric-label">Facteurs qui augmentent le risque</div>
              <div className="chips">
                {drivers.map((x, i) => (
                  <span key={i} className="chip"><span>{x.label}</span>{x.value && <strong>{x.value}</strong>}</span>
                ))}
              </div>
            </div>
          )}
          <div className="row">
            <button className="btn primary" onClick={() => navigate("/", { state: { machine: d.asset_tag, question: "Quel est le risque de panne de cette machine ?" } })}>
              <MessageSquare size={15} />Demander à l'assistant
            </button>
          </div>
          <div className="card flush spaced-top">
            <div className="scroll-x">
              <table className="table">
                <thead><tr><th>date</th><th>type</th><th>code</th><th>arret_min</th><th>cost_mad</th></tr></thead>
                <tbody>
                  {detail.history.map((h, i) => (
                    <tr key={i}>
                      <td>{h.date}</td><td>{h.type}</td><td className={h.code ? "" : "muted"}>{h.code || "None"}</td>
                      <td className="num">{h.downtime_min}</td><td className="num">{Math.round(h.cost_mad * 10) / 10}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}