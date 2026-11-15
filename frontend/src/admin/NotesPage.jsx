import { useCallback, useEffect, useState } from "react";
import { createNote, deleteNote, getNotes, updateNote } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import Markdown from "./ws/Markdown.jsx";
import { Empty, ErrorBox, Field, fmtDate, Hint, Modal } from "./ws/ui.jsx";

const SCOPES = [
  { value: "all", label: "Усі доступні" },
  { value: "mine", label: "Мої" },
  { value: "shared", label: "Поділені" },
];

/** Особисті нотатки. Приватну бачите лише ви — власник школи теж ні. */
export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [scope, setScope] = useState("all");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [edit, setEdit] = useState(null);       // {} — нова, note — правка
  const [view, setView] = useState(null);

  const load = useCallback(async () => {
    try {
      setNotes(await getNotes({ scope, ...(q ? { q } : {}) }));
      setError("");
    } catch (e) { setError(errorText(e)); }
  }, [scope, q]);
  useEffect(() => { load(); }, [load]);

  async function togglePin(n) {
    try { await updateNote(n.id, { pinned: !n.pinned }); load(); } catch (e) { setError(errorText(e)); }
  }

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead ws-pagehead--row">
        <div>
          <h1 className="ws-h1">Нотатки</h1>
          <p className="ws-muted">Нотатка приватна, доки ви не позначите «Поділитися з усіма адмінами». Приватні не бачить ніхто, навіть власник.</p>
        </div>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--big" onClick={() => setEdit({})}>+ Нова нотатка</button>
      </header>

      <div className="ws-filters">
        <div className="ws-seg">
          {SCOPES.map((s) => (
            <button key={s.value} type="button" className={scope === s.value ? "is-on" : ""} onClick={() => setScope(s.value)}>{s.label}</button>
          ))}
        </div>
        <input className="ws-input ws-input--search" type="search" placeholder="Пошук у нотатках"
               onKeyDown={(e) => e.key === "Enter" && setQ(e.currentTarget.value)} onBlur={(e) => setQ(e.currentTarget.value)} />
      </div>

      <ErrorBox text={error} />
      {!notes.length ? <Empty title="Нотаток поки немає">Запишіть ідею, скрипт розмови чи список справ.</Empty> : (
        <div className="ws-notes">
          {notes.map((n) => (
            <article key={n.id} className={`ws-card ws-note${n.pinned && n.mine ? " is-pinned" : ""}`}>
              <button type="button" className="ws-note__open" onClick={() => setView(n)}>
                <b>{n.title || "Без заголовка"}</b>
                <span className="ws-note__body">{n.body.slice(0, 220)}</span>
              </button>
              <footer>
                <span className="ws-muted ws-small">
                  {n.shared ? (n.mine ? "Поділено з усіма" : `Від: ${n.author}`) : "Лише для вас"} · {fmtDate(n.updated_at, true)}
                </span>
                {n.mine && (
                  <span className="ws-row">
                    <button type="button" className="ws-btn ws-btn--small" onClick={() => togglePin(n)}>
                      {n.pinned ? "Відкріпити" : "Закріпити"}
                    </button>
                    <button type="button" className="ws-btn ws-btn--small" onClick={() => setEdit(n)}>Змінити</button>
                  </span>
                )}
              </footer>
            </article>
          ))}
        </div>
      )}

      {view && (
        <Modal title={view.title || "Нотатка"} onClose={() => setView(null)} wide>
          <Markdown text={view.body} />
          <p className="ws-muted ws-small">{view.mine ? "Ваша нотатка" : `Автор: ${view.author}`} · змінено {fmtDate(view.updated_at, true)}</p>
          {view.mine && <button type="button" className="ws-btn" onClick={() => { setEdit(view); setView(null); }}>Змінити</button>}
        </Modal>
      )}
      {edit && <NoteForm note={edit.id ? edit : null} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
    </div>
  );
}

function NoteForm({ note, onClose, onSaved }) {
  const [f, setF] = useState({ title: note?.title || "", body: note?.body || "", shared: note?.shared || false,
                               pinned: note?.pinned || false });
  const [preview, setPreview] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    try {
      if (note) await updateNote(note.id, f); else await createNote(f);
      onSaved();
    } catch (err) { setError(errorText(err)); }
  }

  async function remove() {
    if (!window.confirm("Видалити нотатку назавжди?")) return;
    try { await deleteNote(note.id); onSaved(); } catch (err) { setError(errorText(err)); }
  }

  return (
    <Modal title={note ? "Змінити нотатку" : "Нова нотатка"} onClose={onClose} wide>
      <form className="ws-stack" onSubmit={submit}>
        <Field label="Заголовок">
          <input className="ws-input" maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} autoFocus />
        </Field>
        <Field label="Текст">
          <div className="ws-seg ws-seg--small">
            <button type="button" className={!preview ? "is-on" : ""} onClick={() => setPreview(false)}>Писати</button>
            <button type="button" className={preview ? "is-on" : ""} onClick={() => setPreview(true)}>Як виглядатиме</button>
          </div>
          {preview ? <div className="ws-preview"><Markdown text={f.body} /></div> : (
            <textarea className="ws-input" rows={12} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
          )}
        </Field>
        <Hint>Форматування: **жирний**, - список, - [ ] справа, ## заголовок</Hint>
        <label className="ws-check">
          <input type="checkbox" checked={f.shared} onChange={(e) => setF({ ...f, shared: e.target.checked })} />
          Поділитися з усіма адмінами (вони зможуть читати, змінювати — лише ви)
        </label>
        <label className="ws-check">
          <input type="checkbox" checked={f.pinned} onChange={(e) => setF({ ...f, pinned: e.target.checked })} />
          Закріпити вгорі списку
        </label>
        <ErrorBox text={error} />
        <div className="ws-row">
          <button type="submit" className="ws-btn ws-btn--primary ws-btn--big">Зберегти</button>
          <button type="button" className="ws-btn" onClick={onClose}>Скасувати</button>
          {note && <button type="button" className="ws-btn ws-btn--danger" onClick={remove}>Видалити</button>}
        </div>
      </form>
    </Modal>
  );
}
