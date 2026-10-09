import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, AlertTriangle, ArrowDown, ArrowUp, ClipboardList, Clock, Download, MessageSquare, Search } from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../api";

const pct = (v) => `${Math.round(v * 100)}%`;
const SERIES = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)"];
const tip = { background: "var(--panel)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)" };
const axis = { fill: "var(--muted)", fontSize: 12 };
const RANK = { "Élevé": 3, "Modéré": 2, "Faible": 1 };
const PERIODS = [90, 180, 365];
const TYPES = { corrective: "Correctif", preventive: "Préventif", inspection: "Inspection" };

const COLUMNS = [
  { key: "asset_tag", label: "Machine" },
  { key: "model", label: "Modèle" },
  { key: "workshop", label: "Atelier" },
  { key: "level", label: "Niveau" },
  { key: "risk", label: "Risque 30 j" },
  { key: "late", label: "Retard préventive", num: true },
  { key: "n_fail_90", label: "Pannes 90 j", num: true },
  { key: "drivers", label: "Facteurs principaux", nosort: true },
];

const fmtPct = (v) => `${(v <= 1 ? v * 100 : v).toFixed(1)} %`;
const MODEL_CARDS = [
  { label: "AUC-ROC", re: /^(roc[_-]?)?auc([_-]?roc)?$/i, desc: "Capacité de discrimination", fmt: (v) => v.toFixed(2) },
  { label: "PRÉCISION (PRECISION)", re: /^precision$/i, desc: "Vrais positifs / prédictions", fmt: fmtPct },
  { label: "RAPPEL (RECALL)", re: /^recall$/i, desc: "Détection des pannes réelles", fmt: fmtPct },
  { label: "F1-SCORE", re: /^f1([_-]?score)?$/i, desc: "Équilibre prédictif global", fmt: (v) => v.toFixed(2) },
];

function flatten(obj, prefix = "", out = []) {
  for (const [k, v] of Object.entries(obj || {})) {
    const name = prefix ? `${prefix} · ${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, name, out);
    else if (typeof v === "number") out.push([name, v]);
  }
  return out;
}

function pickMetric(flat, re) {
  const found = flat.filter(([k]) => re.test(k.split(" · ").pop()) && !/base|règle|regle|rule|const|dummy|naive/i.test(k));
  found.sort((a, b) => Number(/test/i.test(b[0])) - Number(/test/i.test(a[0])));
  return found.length ? found[0][1] : null;
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

const delta = (now, prev, days, unit = "") =>
  `${now - prev >= 0 ? "+" : ""}${Math.round((now - prev) * 10) / 10}${unit} vs ${days} j précédents`;

function Kpi({ label, icon: Icon, value, hint, badge }) {
  return (
    <div className="card">
      <div className="kpi-head"><span>{label}</span><Icon size={15} /></div>
      <div className="kpi">{value}</div>
      <div className="kpi-foot">
        {badge && <span className="badge-alert">{badge}</span>}
        {hint && <span className="muted small-text">{hint}</span>}
      </div>
    </div>
  );
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
        setFleet(f.machines.map((x) => ({ ...x, late: x.days_since_pm - x.pm_days })));
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
  const critical = useMemo(() => fleet.filter((m) => m.late > 15).length, [fleet]);

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

  const flat = useMemo(() => (metrics ? flatten(metrics) : []), [metrics]);
  const modelCards = useMemo(
    () => MODEL_CARDS.map((c) => ({ ...c, value: pickMetric(flat, c.re) })).filter((c) => c.value !== null),
    [flat]
  );

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
  const late = d ? d.days_since_pm - d.pm_days : 0;
  const drivers = parseDrivers(d?.drivers);
  const avgRepair = summary.failures ? (summary.downtime_h / summary.failures).toFixed(1) : "0";

  return (
    <div className="page">
      <div className="toolbar">
        <div>
          <h1>Dashboard</h1>
          <p className="muted">Données arrêtées au {summary.as_of}.</p>
        </div>
        <div className="seg" role="group" aria-label="Période">
          {PERIODS.map((p) => (
            <button key={p} className={p === days ? "on" : ""} onClick={() => setDays(p)}>{p} j</button>
          ))}
        </div>
      </div>

      <div className="kpis">
        <Kpi label={`PANNES (${days} J)`} icon={AlertTriangle} value={summary.failures}
             hint={delta(summary.failures, summary.failures_prev, days)} />
        <Kpi label={`ARRÊT MACHINE (H, ${days} J)`} icon={Clock} value={`${summary.downtime_h} h`}
             hint={`Moy. ${avgRepair} h / panne`} />
        <Kpi label="MACHINES À RISQUE ÉLEVÉ" icon={Activity} value={summary.high_risk}
             badge={summary.high_risk > 0 ? "Alerte" : null} hint={`sur ${summary.machines} machines`} />
        <Kpi label="PRÉVENTIVES EN RETARD" icon={ClipboardList} value={summary.pm_late}
             hint={`Dont ${critical} critiques (> 15 j)`} />
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
                  <th key={c.key} className={`${c.nosort ? "" : "sortable"} ${c.num ? "num" : ""}`} onClick={() => toggleSort(c)}>
                    <span className="th-inner">
                      {c.label}
                      {sort.key === c.key && (sort.dir === "asc" ? <ArrowUp size={13} /> : <ArrowDown size={13} />)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                const high = m.level === "Élevé";
                return (
                  <tr key={m.asset_tag} className={`clickable ${m.asset_tag === selected ? "sel" : ""}`} onClick={() => open(m.asset_tag)}>
                    <td className="nowrap mono">{high && <i className="dot red" />}{m.asset_tag}</td>
                    <td className="nowrap">{m.model}</td>
                    <td className="nowrap">{m.workshop}</td>
                    <td><span className={`pill ${high ? "high" : m.level === "Modéré" ? "mid" : "low"}`}>{m.level}</span></td>
                    <td>
                      <div className="risk-cell">
                        <div className="bar"><i className={high ? "red" : ""} style={{ width: `${(m.risk / maxRisk) * 100}%` }} /></div>
                        <span className={high ? "danger-text" : ""}>{pct(m.risk)}</span>
                      </div>
                    </td>
                    <td className={`num ${m.late > 0 ? "danger-text" : "muted"}`}>{m.late > 0 ? "+" : ""}{m.late} j</td>
                    <td className="num">{m.n_fail_90}</td>
                    <td className="nowrap muted">{m.drivers}</td>
                  </tr>
                );
              })}
              {rows.length === 0 && <tr><td colSpan={COLUMNS.length} className="muted">Aucune machine ne correspond.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="charts">
        <div className="card">
          <h2 className="section-title">Top 10 des risques</h2>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={top10} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="machine" tick={{ ...axis, angle: -90, textAnchor: "end" }} height={100} interval={0} />
              <YAxis tick={axis} unit="%" />
              <Tooltip contentStyle={tip} formatter={(v) => [`${v}%`, "Risque 30 j"]} />
              <Bar dataKey="risque" fill="var(--c1)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h2 className="section-title">Pannes par mois et type de machine (12 mois)</h2>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={monthly.data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="month" tick={{ ...axis, angle: -90, textAnchor: "end" }} height={70} interval={0} />
              <YAxis tick={axis} allowDecimals={false} />
              <Tooltip contentStyle={tip} />
              <Legend />
              {monthly.categories.map((c, i) => <Bar key={c} dataKey={c} stackId="a" fill={SERIES[i % SERIES.length]} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card spaced-top">
        <h2 className="section-title">Pannes par code de panne ({days} j)</h2>
        <p className="muted small-text">Diagramme de Pareto : les barres donnent le nombre de pannes, la courbe le cumul en pourcentage.</p>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={codes} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis dataKey="code" tick={axis} />
            <YAxis yAxisId="l" tick={axis} allowDecimals={false} />
            <YAxis yAxisId="r" orientation="right" tick={axis} domain={[0, 100]} unit="%" />
            <Tooltip contentStyle={tip} formatter={(v, n, p) => (n === "Cumul" ? [`${v}%`, n] : [`${v} (${p.payload.downtime_h} h d'arrêt)`, n])} />
            <Legend />
            <Bar yAxisId="l" dataKey="failures" name="Pannes" fill="var(--c1)" radius={[3, 3, 0, 0]} />
            <Line yAxisId="r" dataKey="cumulative" name="Cumul" stroke="var(--c2)" strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {(modelCards.length > 0 || flat.length > 0) && (
        <>
          <h2 className="section-title spaced">Qualité du modèle prédictif</h2>
          <div className="mini-grid">
            {modelCards.length > 0
              ? modelCards.map((c) => (
                  <div key={c.label} className="mcard">
                    <div className="metric-label up">{c.label}</div>
                    <div className="mvalue">{c.fmt(c.value)}</div>
                    <div className="mdesc">{c.desc}</div>
                  </div>
                ))
              : flat.map(([k, v]) => (
                  <div key={k} className="mcard">
                    <div className="metric-label up">{k}</div>
                    <div className="mvalue">{Number.isInteger(v) ? v : v.toFixed(3)}</div>
                  </div>
                ))}
          </div>
          <p className="note">
            Modèle XGBoost entraîné sur un historique synthétique. Les mesures portent sur une période de test : elles valident la chaîne de traitement, pas une performance industrielle.
          </p>
        </>
      )}

      <div className="card detail" ref={detailRef}>
        <div className="detail-top">
          <select className="detail-select" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {fleet.map((m) => (
              <option key={m.asset_tag} value={m.asset_tag}>{`${m.asset_tag} (${m.model} - ${m.workshop})`}</option>
            ))}
          </select>
          {d && (
            <button className="btn inverse" onClick={() => navigate("/", { state: { machine: d.asset_tag, question: "Quel est le risque de panne de cette machine ?" } })}>
              <MessageSquare size={15} />Demander à l'assistant
            </button>
          )}
        </div>

        {d && (
          <>
            <div className="metrics divided">
              <div>
                <div className="metric-label up">Risque 30 j</div>
                <div className="metric-value">{Math.round(d.risk * 100)} %{d.level === "Élevé" && <i className="dot red" />}</div>
              </div>
              <div>
                <div className="metric-label up">Niveau</div>
                <span className={`pill ${d.level === "Élevé" ? "high" : d.level === "Modéré" ? "mid" : "low"}`}>{d.level}</span>
              </div>
              <div>
                <div className="metric-label up">Jours depuis préventive</div>
                <div className="metric-value">
                  {d.days_since_pm} j
                  <span className={`metric-hint ${late > 0 ? "late" : ""}`}>{late > 0 ? "↑ " : ""}plan : {d.pm_days} j</span>
                </div>
              </div>
            </div>

            {drivers.length > 0 && (
              <div className="drivers" style={{ marginTop: 16 }}>
                <div className="metric-label up">Facteurs qui augmentent le risque :</div>
                <div className="chips">
                  {drivers.map((x, i) => (
                    <span key={i} className="chip"><span>{x.label}{x.value ? " :" : ""}</span>{x.value && <strong>{x.value}</strong>}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="hist-title">Historique récent des interventions</div>
            <div className="card flush">
              <div className="scroll-x">
                <table className="table hist-table">
                  <thead>
                    <tr><th>Date</th><th>Type</th><th>Code</th><th className="num">Arrêt (min)</th><th className="num">Coût (MAD)</th></tr>
                  </thead>
                  <tbody>
                    {detail.history.map((h, i) => (
                      <tr key={i}>
                        <td className="mono">{h.date}</td>
                        <td>{TYPES[h.type] || h.type}</td>
                        <td className={h.code ? "mono" : "muted"}>{h.code || "-"}</td>
                        <td className="num">{h.downtime_min} min</td>
                        <td className="num">{Math.round(h.cost_mad).toLocaleString("fr-FR")} MAD</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}