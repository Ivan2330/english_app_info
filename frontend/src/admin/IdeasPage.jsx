import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_URL } from "../config";
import { errorText } from "../api/apiClientAuth";
import { convertIdea, createIdea, getIdeas, updateIdea } from "../api/workspace";
import { Attachments, Reviews } from "./ws/Discussion";
import { AdminContext, Empty, ErrorBox, Field, fmtDate, Modal } from "./ws/ui";
import { FORMATS, topicColor } from "./ws/content";
import "../../styles/admin-content.css";

const STATUSES = { new: "Нова", suitable: "Підходить", in_progress: "У роботі", rejected: "Відхилена" };
const SOURCES = { trend: "Тренд", competitor: "Конкурент", original: "Власна" };
const PRIORITIES = { 1: "Низький", 2: "Середній", 3: "Високий" };
const NEW = { title: "", description: "", format: "post", topic: "", source: "original", reference_url: "", priority: 2, status: "new" };

function SelectField({ label, value, onChange, options, empty }) {
  return <Field label={label}>
    <select className="ws-input" aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      {empty && <option value="">{empty}</option>}
      {Object.entries(options).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
    </select>
  </Field>;
}

export default function IdeasPage() {
  const [query, setQuery] = useState({});
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [revision, setRevision] = useState(0);
  const [title, setTitle] = useState("");
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      getIdeas({ ...Object.fromEntries(Object.entries(query).filter(([, value]) => value)), offset })
        .then((result) => { if (active) { setData(result); setError(""); } })
        .catch((e) => { if (active) setError(errorText(e)); });
    }, 150);
    return () => { active = false; clearTimeout(timer); };
  }, [query, offset, revision]);

  const filter = (key) => (value) => { setQuery((current) => ({ ...current, [key]: value })); setOffset(0); };
  const refresh = () => setRevision((current) => current + 1);

  async function quickAdd(event) {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try { await createIdea({ title }); setTitle(""); setOffset(0); refresh(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  return <div className="ws-stack ws-gap-l">
    <header className="ws-pagehead"><h1 className="ws-h1">Банк ідей</h1></header>
    <form className="ws-card ac-quick" onSubmit={quickAdd}>
      <input className="ws-input" aria-label="Назва нової ідеї" placeholder="Запишіть ідею…" maxLength={200}
             value={title} onChange={(e) => setTitle(e.target.value)} />
      <button className="ws-btn ws-btn--primary" disabled={busy || !title.trim()}>Додати</button>
      <button type="button" className="ws-btn" onClick={() => setEditor({ ...NEW, title })}>Розгорнути</button>
    </form>
    <div className="ac-filters">
      <Field label="Пошук"><input className="ws-input" value={query.q || ""} maxLength={200} onChange={(e) => filter("q")(e.target.value)} /></Field>
      <SelectField label="Формат" empty="Усі формати" options={FORMATS} value={query.format || ""} onChange={filter("format")} />
      <SelectField label="Тема" empty="Усі теми" options={Object.fromEntries((data?.topics || []).map((topic) => [topic, topic]))} value={query.topic || ""} onChange={filter("topic")} />
      <SelectField label="Статус" empty="Усі статуси" options={STATUSES} value={query.status || ""} onChange={filter("status")} />
      <SelectField label="Автор" empty="Усі автори" options={Object.fromEntries((data?.authors || []).map((a) => [a.id, a.name]))} value={query.author_id || ""} onChange={filter("author_id")} />
      <SelectField label="Оцінка" empty="Усі оцінки" options={{ 2: "Від 2", 3: "Від 3", 4: "Від 4", 5: "5 із 5" }} value={query.min_rating || ""} onChange={filter("min_rating")} />
      <SelectField label="Сортування" options={{ recent: "Нові спочатку", oldest: "Старі спочатку", priority: "За пріоритетом", rating: "За оцінкою" }} value={query.sort || "recent"} onChange={filter("sort")} />
    </div>
    <ErrorBox text={error} />
    {!data && !error && <p role="status" className="ws-muted">Завантажуємо…</p>}
    {data?.items.length === 0 && <Empty title="Ідей не знайдено">Додайте ідею або змініть фільтри.</Empty>}
    <div className="ac-cards">
      {data?.items.map((item) => <button key={item.id} type="button" className="ws-card ac-card" onClick={() => setEditor(item)}>
        {item.cover_id && <img className="ac-cover" src={`${API_URL}/api/admin/files/${item.cover_id}?thumbnail=true`} alt="" loading="lazy" />}
        <span className="ws-row ws-wrap">
          <span className="ws-tag">{FORMATS[item.format]}</span>
          <span className="ws-tag">{STATUSES[item.status]}</span>
          {item.topic && <span className="ws-tag" style={topicColor(item.topic)}>{item.topic}</span>}
        </span>
        <strong>{item.title}</strong>
        {item.description && <span className="ac-description">{item.description}</span>}
        <span className="ws-muted ws-small">{item.author} · {fmtDate(item.created_at)}{item.average !== null && ` · ${item.average}/5`}</span>
      </button>)}
    </div>
    {(data?.has_more || offset > 0) && <div className="ws-row">
      <button className="ws-btn" disabled={!offset} onClick={() => setOffset((value) => value - 50)}>Назад</button>
      <button className="ws-btn" disabled={!data?.has_more} onClick={() => setOffset((value) => value + 50)}>Далі</button>
    </div>}
    {editor && <IdeaEditor key={editor.id || "new"} item={editor} onClose={() => setEditor(null)} onSaved={(saved) => {
      if (!editor.id) setTitle("");
      setEditor(saved);
      refresh();
    }} refresh={refresh} />}
  </div>;
}

function IdeaEditor({ item, onClose, onSaved, refresh }) {
  const me = useContext(AdminContext);
  const navigate = useNavigate();
  const [fields, setFields] = useState(() => Object.fromEntries(Object.keys(NEW).map((key) => [key, item[key]])));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key) => (value) => setFields((current) => ({ ...current, [key]: value }));
  const input = (key) => (event) => set(key)(event.target.value);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = { ...fields, priority: Number(fields.priority) };
      onSaved(await (item.id ? updateIdea(item.id, body) : createIdea(body)));
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  async function convert() {
    setBusy(true);
    setError("");
    try {
      const creative = await convertIdea(item.id);
      navigate(`/admin/creatives?open=${creative.id}`);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  return <Modal title={item.id ? item.title : "Нова ідея"} onClose={onClose} wide>
    <div className="ws-stack">
      <form className="ws-stack" onSubmit={save}>
        <Field label="Назва"><input className="ws-input" required maxLength={200} value={fields.title} onChange={input("title")} /></Field>
        <Field label="Опис"><textarea className="ws-input" rows={4} maxLength={20000} value={fields.description} onChange={input("description")} /></Field>
        <div className="ac-filters">
          <SelectField label="Формат" value={fields.format} options={FORMATS} onChange={set("format")} />
          <Field label="Тема або серія"><input className="ws-input" maxLength={120} value={fields.topic} onChange={input("topic")} /></Field>
          <SelectField label="Джерело" value={fields.source} options={SOURCES} onChange={set("source")} />
          <SelectField label="Пріоритет" value={fields.priority} options={PRIORITIES} onChange={set("priority")} />
          <SelectField label="Статус" value={fields.status} options={STATUSES} onChange={set("status")} />
        </div>
        <Field label="Посилання на референс"><input className="ws-input" type="url" maxLength={500} value={fields.reference_url} onChange={input("reference_url")} /></Field>
        {item.reference_url && <a className="ws-more" href={item.reference_url} target="_blank" rel="noreferrer">Відкрити референс ↗</a>}
        <ErrorBox text={error} />
        <button className="ws-btn ws-btn--primary" disabled={busy || !fields.title.trim()}>{busy ? "Зберігаємо…" : "Зберегти ідею"}</button>
      </form>
      {item.id && <>
        <p className="ws-muted ws-small">{item.author} · {fmtDate(item.created_at)}</p>
        {me.sections.includes("creatives") && <button type="button" className="ws-btn" disabled={busy}
          onClick={convert}>Перетворити на креатив</button>}
        <Attachments type="idea" id={item.id} title="Зображення для референсу" accept=".jpg,.jpeg,.png,.webp" onChange={refresh} />
        <Reviews type="idea" id={item.id} maxScore={5} onChange={refresh} />
      </>}
    </div>
  </Modal>;
}
