import { useEffect, useRef, useState } from "react";
import { ArrowUp, Camera, ChevronDown, Plus, Search, Upload } from "lucide-react";
import CameraModal from "./CameraModal";

function useOutside(ref, onOutside) {
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onOutside();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ref, onOutside]);
}

function MachinePicker({ machines, value, onChange }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef(null);
  useOutside(ref, () => setOpen(false));

  const list = machines.filter((m) =>
    `${m.asset_tag} ${m.manufacturer} ${m.model_name} ${m.line_name}`.toLowerCase().includes(q.toLowerCase())
  );
  const pick = (tag) => {
    onChange(tag);
    setOpen(false);
    setQ("");
  };

  return (
    <div className="picker" ref={ref}>
      <button className="chip-btn" onClick={() => setOpen((o) => !o)} aria-label="Choisir une machine">
        <span>{value || "Aucune machine"}</span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="popover wide">
          <div className="search">
            <Search size={14} />
            <input autoFocus placeholder="Rechercher" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="list">
            <button className={!value ? "sel" : ""} onClick={() => pick(null)}>Aucune</button>
            {list.map((m) => (
              <button key={m.asset_tag} className={m.asset_tag === value ? "sel" : ""} onClick={() => pick(m.asset_tag)}>
                <span>{m.asset_tag}</span>
                <small>{m.manufacturer} {m.model_name}</small>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Composer({ machines, machine, onMachine, onSend, onImage, busy }) {
  const [text, setText] = useState("");
  const [menu, setMenu] = useState(false);
  const [camera, setCamera] = useState(false);
  const area = useRef(null);
  const upload = useRef(null);
  const capture = useRef(null);
  const menuRef = useRef(null);
  useOutside(menuRef, () => setMenu(false));

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const submit = () => {
    if (!text.trim() || busy) return;
    onSend(text.trim());
    setText("");
  };
  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  const pickFile = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) onImage(f);
  };
  const openCamera = () => {
    setMenu(false);
    if (navigator.mediaDevices?.getUserMedia) setCamera(true);
    else capture.current.click();      // repli : appareil photo du téléphone
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <div className="plus" ref={menuRef}>
          <button className="icon-btn" onClick={() => setMenu((o) => !o)} aria-label="Ajouter une image">
            <Plus size={20} />
          </button>
          {menu && (
            <div className="popover">
              <button onClick={() => { setMenu(false); upload.current.click(); }}><Upload size={16} />Importer une image</button>
              <button onClick={openCamera}><Camera size={16} />Prendre une photo</button>
            </div>
          )}
        </div>
        <textarea ref={area} rows={1} value={text} placeholder="Pose ta question"
                  onChange={(e) => setText(e.target.value)} onKeyDown={onKey} />
        <MachinePicker machines={machines} value={machine} onChange={onMachine} />
        <button className="icon-btn send" onClick={submit} disabled={!text.trim() || busy} aria-label="Envoyer">
          <ArrowUp size={18} />
        </button>
      </div>
      <input ref={upload} type="file" accept="image/*" hidden onChange={pickFile} />
      <input ref={capture} type="file" accept="image/*" capture="environment" hidden onChange={pickFile} />
      {camera && <CameraModal onClose={() => setCamera(false)} onCapture={(f) => { setCamera(false); onImage(f); }} />}
    </div>
  );
}