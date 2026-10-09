import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Bot, Check, Copy, Cpu, Languages, Lock, ScanLine } from "lucide-react";

const textOf = (n) =>
  typeof n === "string" ? n : Array.isArray(n) ? n.map(textOf).join("") : n?.props?.children ? textOf(n.props.children) : "";

const CITE = /(\[[^\]]+\.pdf[^\]]*\])/g;
function decorate(children) {
  const arr = Array.isArray(children) ? children : [children];
  return arr.flatMap((c, i) =>
    typeof c === "string"
      ? c.split(CITE).map((s, j) => (j % 2 ? <span key={`${i}-${j}`} className="cite">{s}</span> : s))
      : [c]
  );
}

const components = {
  p({ children }) {
    const t = textOf(children).trim();
    if (/^cause probable/i.test(t))
      return <div className="callout"><AlertTriangle size={16} /><div>{decorate(children)}</div></div>;
    if (/^(consigne|s[ée]curit[ée]|attention)/i.test(t))
      return <div className="callout safety"><Lock size={16} /><div>{decorate(children)}</div></div>;
    return <p>{decorate(children)}</p>;
  },
  li({ children }) {
    return <li>{decorate(children)}</li>;
  },
};

function CopyButton({ text }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    } catch {
      /* presse-papiers indisponible */
    }
  };
  return (
    <button className="btn small" onClick={copy}>
      {done ? <Check size={14} /> : <Copy size={14} />}{done ? "Copié" : "Copier"}
    </button>
  );
}

export function Message({ m }) {
  if (m.role === "user") {
    return (
      <div className="msg user">
        <div className="stack">
          <div className="bubble user">{m.content}</div>
          {m.asset_tag && <span className="tag"><Cpu size={12} />{m.asset_tag}</span>}
        </div>
      </div>
    );
  }
  const understood = m.meta?.understood_as;
  return (
    <div className="msg assistant">
      <div className="stack wide">
        <div className="answer">
          <div className="answer-head"><span className="bot"><Bot size={14} /></span>Assistant de maintenance</div>
          <div className="md">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{m.content}</ReactMarkdown>
          </div>
          <div className="answer-foot"><CopyButton text={m.content} /></div>
        </div>
        {understood && <span className="tag"><Languages size={12} />Compris comme : {understood}</span>}
      </div>
    </div>
  );
}

export function Typing() {
  return (
    <div className="msg assistant">
      <div className="answer dots"><span /><span /><span /></div>
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
    body = <span>Machine identifiée : <strong>{label(r.asset_tag)}</strong> · {r.method} · <span className="conf">{Math.round(r.confidence * 100)} % de confiance</span></span>;
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
          {r.candidates.slice(0, 8).map((c) => (
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
        <div className="card-title"><ScanLine size={15} />IDENTIFICATION PAR IMAGE</div>
        {body}
      </div>
    </div>
  );
}