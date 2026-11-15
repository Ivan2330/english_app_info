import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { createReport, deleteReport, extractReportText, getReport, getReports, updateReport } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import Markdown from "./ws/Markdown.jsx";
import { Attachments, Comments, Reviews } from "./ws/Discussion.jsx";
import { Empty, ErrorBox, Field, fmtDate, Hint, Modal, Tags, TagsInput } from "./ws/ui.jsx";

export const KINDS = [
  { value: "marketing", label: "Маркетинг" },
  { value: "analytics", label: "Аналітика" },
  { value: "development", label: "Розробка" },
  { value: "sales", label: "Продажі" },
  { value: "other", label: "Інше" },
];
export const STATUSES = [
  { value: "new", label: "Новий" },
  { value: "review", label: "На перегляді" },
  { value: "accepted", label: "Прийнято" },
  { value: "rework", label: "На допрацювання" },
];

export default function ReportsPage() {
  return (
    <Routes>
      <Route index element={<ReportList />} />
      <Route path=":id" element={<ReportView />} />
    </Routes>
  );
}

/* ================================================================ список */

function ReportList() {
  const [items, setItems] = useState([]);
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      setItems(await getReports({ ...(kind && { kind }), ...(status && { status }), ...(q && { q }) }));
      setError("");
    } catch (e) { setError(errorText(e)); }
  }, [kind, status, q]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead ws-pagehead--row">
        <div>
          <h1 className="ws-h1">Звіти</h1>
          <p className="ws-muted">Звіти агентів і людей. Читаєте прямо тут, ставите бал і коментуєте, зі звіту можна зробити завдання.</p>
        </div>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--big" onClick={() => setCreating(true)}>+ Додати звіт</button>
      </header>

      <div className="ws-filters">
        <select className="ws-input ws-input--auto" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Тип">
          <option value="">Усі типи</option>
          {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
        <select className="ws-input ws-input--auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Статус">
          <option value="">Усі статуси</option>
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <input className="ws-input ws-input--search" type="search" placeholder="Пошук у звітах"
               onKeyDown={(e) => e.key === "Enter" && setQ(e.currentTarget.value)} onBlur={(e) => setQ(e.currentTarget.value)} />
      </div>

      <ErrorBox text={error} />
      {!items.length ? <Empty title="Звітів поки немає">Додайте перший: вставте текст або завантажте файл .md, .txt чи .docx.</Empty> : (
        <div className="ws-list">
          {items.map((r) => (
            <Link key={r.id} to={`/admin/reports/${r.id}`} className="ws-card ws-report">
              <span className="ws-task__top">
                <span className={`ws-status rs-${r.status}`}>{r.status_label}</span>
                <span className="ws-tag">{r.kind_label}</span>
                {r.unread && <span className="ws-new">нове</span>}
              </span>
              <b>{r.title}</b>
              <span className="ws-muted ws-small">
                {r.agent || "джерело не вказано"} · {fmtDate(r.created_at)}
                {r.average_score != null && <> · <span className="ws-score">{r.average_score}/10</span></>}
                {r.comments_count > 0 && ` · коментарів: ${r.comments_count}`}
              </span>
              <Tags tags={r.tags} />
            </Link>
          ))}
        </div>
      )}

      {creating && <ReportForm onClose={() => setCreating(false)} onSaved={(r) => navigate(`/admin/reports/${r.id}`)} />}
    </div>
  );
}

/* ================================================================ форма */

function ReportForm({ report, onClose, onSaved }) {
  const [f, setF] = useState({
    title: report?.title || "", kind: report?.kind || "marketing", agent: report?.agent || "",
    body: report?.body || "", tags: report?.tags || [],
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const file = useRef(null);

  async function fromFile(e) {
    const picked = e.target.files?.[0];
    if (!picked) return;
    setError("");
    try {
      const { text, title } = await extractReportText(picked);
      setF((cur) => ({ ...cur, body: text, title: cur.title || title }));
    } catch (err) { setError(errorText(err)); }
    e.target.value = "";
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      onSaved(report ? await updateReport(report.id, f) : await createReport(f));
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }

  return (
    <Modal title={report ? "Змінити звіт" : "Новий звіт"} onClose={onClose} wide>
      <form className="ws-stack" onSubmit={submit}>
        <Field label="Назва">
          <input className="ws-input" required maxLength={200} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })}
                 placeholder="Наприклад: Аналіз Instagram конкурентів, листопад" />
        </Field>
        <div className="ws-form2">
          <Field label="Тип">
            <select className="ws-input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
              {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
          </Field>
          <Field label="Агент або джерело" hint="Хто підготував: назва агента, людина, сервіс">
            <input className="ws-input" maxLength={120} value={f.agent} onChange={(e) => setF({ ...f, agent: e.target.value })} />
          </Field>
        </div>
        <Field label="Текст звіту">
          <div className="ws-row ws-wrap">
            <div className="ws-seg ws-seg--small">
              <button type="button" className={!preview ? "is-on" : ""} onClick={() => setPreview(false)}>Писати</button>
              <button type="button" className={preview ? "is-on" : ""} onClick={() => setPreview(true)}>Як виглядатиме</button>
            </div>
            <button type="button" className="ws-btn ws-btn--small" onClick={() => file.current?.click()}>
              Взяти текст із файлу (.md, .txt, .docx)
            </button>
            <input ref={file} type="file" accept=".md,.txt,.docx" hidden onChange={fromFile} />
          </div>
          {preview ? <div className="ws-preview"><Markdown text={f.body} /></div> : (
            <textarea className="ws-input ws-input--mono" rows={14} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })}
                      placeholder="Вставте сюди текст звіту" />
          )}
        </Field>
        <Hint>PDF не перетворюється на текст: додайте його вкладенням після збереження, він відкриється прямо на сторінці.</Hint>
        <Field label="Теги" hint="Через кому">
          <TagsInput value={f.tags} onChange={(tags) => setF({ ...f, tags })} />
        </Field>
        <ErrorBox text={error} />
        <div className="ws-row">
          <button type="submit" className="ws-btn ws-btn--primary ws-btn--big" disabled={busy}>
            {busy ? "Зберігаємо…" : report ? "Зберегти зміни" : "Зберегти звіт"}
          </button>
          <button type="button" className="ws-btn" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </Modal>
  );
}

/* ================================================================ сторінка звіту */

function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [r, setR] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => getReport(id).then(setR).catch((e) => setError(errorText(e))), [id]);
  useEffect(() => { load(); }, [load]);

  async function setStatus(status) {
    try { setR(await updateReport(id, { status })); } catch (e) { setError(errorText(e)); }
  }

  async function remove() {
    if (!window.confirm("Видалити звіт разом з оцінками, коментарями й файлами?")) return;
    try { await deleteReport(id); navigate("/admin/reports"); } catch (e) { setError(errorText(e)); }
  }

  if (!r) return error ? <ErrorBox text={error} /> : <p className="ws-muted">Завантажуємо…</p>;

  const taskLink = `/admin/tasks?new=1&related_type=report&related_id=${r.id}&title=${encodeURIComponent(`За звітом: ${r.title}`)}`;

  return (
    <div className="ws-stack ws-gap-l">
      <Link to="/admin/reports" className="ws-back">← Усі звіти</Link>
      <header className="ws-pagehead">
        <span className="ws-task__top">
          <span className={`ws-status rs-${r.status}`}>{r.status_label}</span>
          <span className="ws-tag">{r.kind_label}</span>
          {r.source === "api" && <span className="ws-tag">автоматично</span>}
        </span>
        <h1 className="ws-h1">{r.title}</h1>
        <p className="ws-muted">{r.agent || "Джерело не вказано"} · додав {r.author || "—"} · {fmtDate(r.created_at, true)}</p>
        <Tags tags={r.tags} />
      </header>

      <div className="ws-row ws-wrap">
        <span className="ws-field__label">Статус:</span>
        {STATUSES.map((s) => (
          <button key={s.value} type="button" className={`ws-btn ws-btn--small${r.status === s.value ? " is-current" : ""}`}
                  disabled={r.status === s.value} onClick={() => setStatus(s.value)}>{s.label}</button>
        ))}
      </div>
      <ErrorBox text={error} />

      <div className="ws-detail">
        <article className="ws-card ws-detail__main ws-report-body">
          <Markdown text={r.body} empty="Текст звіту порожній. Можливо, він у вкладенні нижче." />
        </article>
        <aside className="ws-detail__side ws-stack">
          <Link to={taskLink} className="ws-btn ws-btn--primary ws-btn--big">Створити завдання з цього звіту</Link>
          <Reviews type="report" id={r.id} />
          <div className="ws-row">
            <button type="button" className="ws-btn" onClick={() => setEditing(true)}>Змінити звіт</button>
            {r.can_delete && <button type="button" className="ws-btn ws-btn--danger" onClick={remove}>Видалити</button>}
          </div>
        </aside>
      </div>
      <Attachments type="report" id={r.id} title="Вкладення" />
      <Comments type="report" id={r.id} />

      {editing && <ReportForm report={r} onClose={() => setEditing(false)} onSaved={(u) => { setR(u); setEditing(false); }} />}
    </div>
  );
}
