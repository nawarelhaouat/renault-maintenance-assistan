import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ScanLine } from "lucide-react";

export function Message({ m }) {
  if (m.role === "user") {
    return (
      <div className="msg user">
        <div className="stack">
          <div className="bubble user">{m.content}</div>
          {m.asset_tag && <span className="tag">{m.asset_tag}</span>}
        </div>
      </div>
    );
  }
  const understood = m.meta?.understood_as;
  return (
    <div className="msg assistant">
      <div className="stack">
        {understood && <span className="tag">Compris comme : {understood}</span>}
        <div className="bubble assistant md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export function Typing() {
  return (
    <div className="msg assistant">
      <div className="bubble assistant dots"><span /><span /><span /></div>
    </div>
  );
}

export function IdentCard({ item, machines, onPick }) {
  const [confirmed, setConfirmed] = useState(false);
  const r = item.result;
  const label = (tag) => {
    const m = machines.find((x) => x.asset_tag === tag);
    return m ? `${tag} · ${m.manufacturer} ${m.model_name}` : tag;
  };

  let body;
  if (item.pending) {
    body = <div className="dots"><span /><span /><span /></div>;
  } else if (r.error) {
    body = <span>{r.error}</span>;
  } else if (r.asset_tag && (!r.needs_confirmation || confirmed)) {
    body = <span>Machine identifiée : <strong>{label(r.asset_tag)}</strong> · {r.method} · {Math.round(r.confidence * 100)} %</span>;
  } else if (r.asset_tag) {
    body = (
      <>
        <span>Lecture à confirmer : <strong>{label(r.asset_tag)}</strong> ({r.method}, {Math.round(r.confidence * 100)} %)</span>
        <div className="row">
          <button className="btn primary" onClick={() => { setConfirmed(true); onPick(r.asset_tag); }}>Confirmer</button>
          <button className="btn" onClick={() => setConfirmed(null)}>Ignorer</button>
        </div>
      </>
    );
  } else if (r.candidates) {
    body = (
      <>
        <span>Type probable : <strong>{r.category}</strong>. Choisis la machine :</span>
        <div className="cands">
          {r.candidates.map((c) => (
            <button key={c.asset_tag} className="btn" onClick={() => onPick(c.asset_tag)}>
              {c.asset_tag} · {c.manufacturer} {c.model_name}
            </button>
          ))}
        </div>
      </>
    );
  } else {
    body = <span>Machine non reconnue. Sélectionne-la dans la liste.</span>;
  }
  if (confirmed === null) return null;

  return (
    <div className="msg assistant">
      <div className="card-inline">
        <div className="card-title"><ScanLine size={15} />Identification par image</div>
        {body}
      </div>
    </div>
  );
}