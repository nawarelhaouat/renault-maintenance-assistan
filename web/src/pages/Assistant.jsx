import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";
import { api } from "../api";
import Composer from "../components/Composer";
import { IdentCard, Message, Typing } from "../components/Message";

const SUGGESTIONS = [
  "Quelle est la dernière panne de cette machine ?",
  "Combien d'interventions cette machine a-t-elle eues ?",
  "Quel est le risque de panne de cette machine ?",
];

export default function Assistant() {
  const { id } = useParams();
    const { key, state } = useLocation();
  const { refresh } = useOutletContext();
  const navigate = useNavigate();
  const [machines, setMachines] = useState([]);
  const [machine, setMachine] = useState(null);
  const [messages, setMessages] = useState([]);
  const [convId, setConvId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const created = useRef(null);
  const epoch = useRef(0);
  const bottom = useRef(null);

  useEffect(() => {
    api.machines().then(setMachines).catch(() => {});
  }, []);

  useEffect(() => {
    epoch.current += 1;
    setError("");
    if (!id) {
      setConvId(null);
      setMessages([]);
      setMachine(state?.machine ?? null);
      return;
    }
    if (created.current === Number(id)) {      // discussion tout juste créée : déjà à l'écran
      created.current = null;
      return;
    }
    api.conversation(id)
      .then((d) => {
        setConvId(d.conversation.id);
        setMessages(d.messages);
        setMachine(d.conversation.asset_tag);
      })
      .catch((e) => setError(e.message));
  }, [id, key]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text) => {
    if (!text.trim() || busy) return;
    const ticket = epoch.current;
    setError("");
    setBusy(true);
    setMessages((m) => [...m, { id: `u${Date.now()}`, role: "user", content: text, asset_tag: machine }]);
    try {
      const res = await api.chat({ question: text, asset_tag: machine, conversation_id: convId });
      refresh();
      if (epoch.current !== ticket) return;          // l'utilisateur a changé de discussion entre-temps
      setMessages((m) => [...m, res.answer]);
      if (!convId) {
        created.current = res.conversation_id;
        setConvId(res.conversation_id);
        navigate(`/c/${res.conversation_id}`, { replace: true });
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const identify = async (file) => {
    const noteId = `i${Date.now()}`;
    const patch = (extra) => setMessages((m) => m.map((x) => (x.id === noteId ? { ...x, ...extra } : x)));
    setMessages((m) => [...m, { id: noteId, role: "ident", pending: true }]);
    try {
      const result = await api.identify(file);
      patch({ pending: false, result });
      if (result.asset_tag && !result.needs_confirmation) setMachine(result.asset_tag);
    } catch (e) {
      patch({ pending: false, result: { error: e.message } });
    }
  };

  const empty = messages.length === 0 && !busy;

  return (
    <div className="chat-page">
      <div className="chat">
        {empty ? (
          <div className="empty">
            <h1>Assistant de maintenance</h1>
            <p>Sélectionne une machine ou envoie une photo, puis pose ta question en français ou en darija.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="thread">
            {messages.map((m) =>
              m.role === "ident"
                ? <IdentCard key={m.id} item={m} machines={machines} onPick={setMachine} />
                : <Message key={m.id} m={m} />
            )}
            {busy && <Typing />}
            <div ref={bottom} />
          </div>
        )}
      </div>
      {error && <div className="error banner">{error}</div>}
      <Composer machines={machines} machine={machine} onMachine={setMachine}
                onSend={send} onImage={identify} busy={busy} draft={!id ? state?.question : ""} />
    </div>
  );
}