import { useContext, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorText } from "../api/apiClientAuth";
import {
  bulkCreatives, createCreative, duplicateCreative, getCreative, getCreativeRankings, getCreatives,
  getCreativeUploadSettings, setCreativeUploadSettings, updateCreative,
} from "../api/workspace";
import { AdminContext, Empty, ErrorBox, Field, fmtDate, Modal } from "./ws/ui";
import { FORMATS, topicColor } from "./ws/content";
import { fromKyiv, kyivInput } from "./ws/kyiv";
import CreativeMedia, { fileSpecs, mediaUrl, MediaTile } from "./ws/CreativeMedia";
import CreativeReview from "./ws/CreativeReview";
import "../../styles/admin-content.css";

const STATUSES = { idea: "Ідея", draft: "Чернетка", review: "На перевірці", approved: "Затверджено", published: "Опубліковано", archived: "Архів" };
const PURPOSES = { organic: "Органіка", ad: "Реклама" };
const NEW = { title: "", description: "", format: "post", purpose: "organic", topic: "", status: "idea",
  scheduled_at: "", published_on: "", caption: "", hashtags: "", cta: "", notes: "", tags: [], published_url: "",
  reach: null, saves: null, shares: null };
const PAGE = 48;

function Select({ label, value, options, onChange, empty }) {
  return <Field label={label}><select className="ws-input" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
    {empty && <option value="">{empty}</option>}
    {Object.entries(options).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
  </select></Field>;
}

const optionMap = (values) => Object.fromEntries((values || []).map((value) => [value, value]));

export default function CreativesPage() {
  const me = useContext(AdminContext);
  const statusOptions = me.role === "owner" ? STATUSES : Object.fromEntries(Object.entries(STATUSES).filter(([key]) => key !== "approved"));
  const [params, setParams] = useSearchParams();
  const id = params.get("open");
  const [query, setQuery] = useState({});
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [view, setView] = useState("grid");
  const [selected, setSelected] = useState([]);
  const [bulkStatus, setBulkStatus] = useState("");
  const [tag, setTag] = useState("");
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(null);
  const [showRankings, setRankings] = useState(false);
  const refresh = () => setRevision((value) => value + 1);

  useEffect(() => { getCreativeUploadSettings().then(setSettings).catch((e) => setError(errorText(e))); }, []);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      const filters = Object.fromEntries(Object.entries(query).filter(([, value]) => value));
      getCreatives({ ...filters, limit: PAGE, offset }).then((result) => { if (active) { setData(result); setError(""); } })
        .catch((e) => { if (active) setError(errorText(e)); });
    }, 150);
    return () => { active = false; clearTimeout(timer); };
  }, [query, offset, revision]);

  const filter = (field) => (value) => { setQuery((state) => ({ ...state, [field]: value })); setOffset(0); setSelected([]); };
  const open = (key) => setParams(key == null ? {} : { open: key }, { replace: key == null });
  const toggle = (key) => setSelected((ids) => ids.includes(key) ? ids.filter((id) => id !== key) : [...ids, key]);

  async function apply(status = bulkStatus) {
    setBusy(true);
    setError("");
    try {
      await bulkCreatives({ ids: selected, status: status || null, tag });
      setSelected([]);
      setBulkStatus("");
      setTag("");
      refresh();
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  async function changeLimit(event) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    try { setSettings(await setCreativeUploadSettings({ max_mb: Number(fields.get("max_mb")) })); }
    catch (e) { setError(errorText(e)); }
  }

  const items = data?.items || [];
  const card = (item) => <article className={`ws-card ac-catalog-card ac-catalog-card--${view}`} key={item.id}>
    <input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} aria-label={`Вибрати «${item.title}»`} />
    <button type="button" onClick={() => open(item.id)} className="ac-catalog-button">
      <span className="ac-tile"><MediaTile file={item.cover} /></span>
      <span className="ac-catalog-title"><strong>{item.title}</strong><span className="ws-muted ws-small">{FORMATS[item.format]} · {STATUSES[item.status]}{item.average != null && ` · ${item.average}/5`}</span></span>
    </button>
  </article>;

  return <div className="ws-stack ws-gap-l">
    <header className="ws-pagehead ws-pagehead--row">
      <h1 className="ws-h1">Банк креативів</h1>
      <div className="ws-row ws-wrap">
        <button className="ws-btn" onClick={() => setRankings(true)}>Рейтинги</button>
        <button className="ws-btn ws-btn--primary" onClick={() => open("new")}>Новий креатив</button>
      </div>
    </header>
    {settings?.can_change && <details className="ws-card" key={settings.max_mb}><summary>Налаштування файлів · {settings.max_mb} МБ</summary>
      <form className="ws-row ws-wrap" onSubmit={changeLimit}>
        <Field label="Максимум МБ на файл"><input className="ws-input" name="max_mb" type="number" min={1} max={300} defaultValue={settings.max_mb} required /></Field>
        <button className="ws-btn">Зберегти ліміт</button>
      </form>
    </details>}
    <div className="ac-filters">
      <Field label="Пошук"><input className="ws-input" maxLength={200} value={query.q || ""} onChange={(e) => filter("q")(e.target.value)} placeholder="Назва або підпис" /></Field>
      <Select label="Тип" empty="Усі типи" options={FORMATS} value={query.format || ""} onChange={filter("format")} />
      <Select label="Призначення" empty="Усі" options={PURPOSES} value={query.purpose || ""} onChange={filter("purpose")} />
      <Select label="Тема" empty="Усі теми" options={optionMap(data?.topics)} value={query.topic || ""} onChange={filter("topic")} />
      <Select label="Статус" empty="Усі статуси" options={STATUSES} value={query.status || ""} onChange={filter("status")} />
      <Select label="Автор" empty="Усі автори" options={Object.fromEntries((data?.authors || []).map((user) => [user.id, user.name]))} value={query.author_id || ""} onChange={filter("author_id")} />
      <Select label="Оцінка" empty="Усі оцінки" options={{ 2: "Від 2", 3: "Від 3", 4: "Від 4", 5: "5 із 5" }} value={query.min_rating || ""} onChange={filter("min_rating")} />
      <Select label="Тег" empty="Усі теги" options={optionMap(data?.tags)} value={query.tag || ""} onChange={filter("tag")} />
      <Field label="Дата від"><input className="ws-input" type="date" value={query.date_from || ""} max={query.date_to || undefined} onChange={(e) => filter("date_from")(e.target.value)} /></Field>
      <Field label="Дата до"><input className="ws-input" type="date" value={query.date_to || ""} min={query.date_from || undefined} onChange={(e) => filter("date_to")(e.target.value)} /></Field>
    </div>
    <div className="ws-row ws-wrap">
      <div className="ws-seg" aria-label="Вигляд" role="group">
        {Object.entries({ grid: "Сітка", list: "Список", table: "Таблиця" }).map(([key, label]) => <button type="button" key={key} aria-pressed={view === key} className={view === key ? "is-on" : ""} onClick={() => setView(key)}>{label}</button>)}
      </div>
      {items.length > 0 && <button className="ws-btn" onClick={() => setSelected(selected.length === items.length ? [] : items.map((item) => item.id))}>{selected.length === items.length ? "Скасувати вибір" : "Вибрати всі на сторінці"}</button>}
    </div>
    {selected.length > 0 && <div className="ws-card ws-row ws-wrap">
      <strong>Вибрано {selected.length}</strong>
      <Select label="Змінити статус" empty="Без зміни" options={statusOptions} value={bulkStatus} onChange={setBulkStatus} />
      <Field label="Додати тег"><input className="ws-input" maxLength={40} value={tag} onChange={(e) => setTag(e.target.value)} /></Field>
      <button className="ws-btn ws-btn--primary" disabled={busy || !(bulkStatus || tag.trim())} onClick={() => apply()}>Застосувати</button>
      <button className="ws-btn" disabled={busy} onClick={() => apply("archived")}>Архівувати</button>
    </div>}
    <ErrorBox text={error} />
    {!data && !error && <p className="ws-muted" role="status">Завантажуємо…</p>}
    {data && items.length === 0 && <Empty title="Креативів не знайдено">Створіть перший креатив або змініть фільтри.</Empty>}
    {view === "table" && items.length > 0 ? <div className="ac-table"><table><thead><tr>
      {["Вибір", "Назва", "Тип", "Статус", "Тема", "Автор", "Оцінка", "Дата"].map((label) => <th key={label}>{label}</th>)}
    </tr></thead><tbody>{items.map((item) => <tr key={item.id}>
      <td><input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} aria-label={`Вибрати «${item.title}»`} /></td>
      <td><button className="ws-btn" onClick={() => open(item.id)}>{item.title}</button></td>
      <td>{FORMATS[item.format]}</td><td>{STATUSES[item.status]}</td><td>{item.topic || "—"}</td>
      <td>{item.author}</td><td>{item.average ?? "—"}</td><td>{fmtDate(item.published_on || item.scheduled_at)}</td>
    </tr>)}</tbody></table></div> : <div className={view === "grid" ? "ac-grid-three" : "ws-list"}>{items.map(card)}</div>}
    {(offset > 0 || data?.has_more) && <div className="ws-row">
      <button className="ws-btn" disabled={!offset} onClick={() => { setSelected([]); setOffset(offset - PAGE); }}>Назад</button>
      <button className="ws-btn" disabled={!data?.has_more} onClick={() => { setSelected([]); setOffset(offset + PAGE); }}>Далі</button>
    </div>}
    {id && <CreativeDialog key={id} id={id} statusOptions={statusOptions} maxMb={settings?.max_mb} onClose={() => open(null)} open={open} refreshList={refresh} />}
    {showRankings && <Rankings onClose={() => setRankings(false)} onOpen={(id) => { setRankings(false); open(id); }} />}
  </div>;
}

function CreativeDialog({ id, statusOptions, maxMb, onClose, open, refreshList }) {
  const [item, setItem] = useState(id === "new" ? NEW : null);
  const [tab, setTab] = useState(id === "new" ? "edit" : "preview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function reload() {
    if (id === "new") return;
    try { setItem(await getCreative(id)); refreshList(); }
    catch (e) { setError(errorText(e)); }
  }
  useEffect(() => { reload(); }, [id]);

  async function duplicate() {
    setBusy(true);
    try { open((await duplicateCreative(id)).id); refreshList(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  return <Modal title={item?.title || "Новий креатив"} onClose={onClose} wide>
    <div className="ws-stack">
      <ErrorBox text={error} />
      {!item && !error && <p className="ws-muted" role="status">Завантажуємо…</p>}
      {item?.id && <>
        <div className="ws-row ws-wrap">
          <span className="ws-tag">{STATUSES[item.status]}</span>
          <span className="ws-small ws-muted">{item.author} · версія {item.version}</span>
          {item.topic && <span className="ws-tag" style={topicColor(item.topic)}>{item.topic}</span>}
          {item.tags.map((tag) => <span key={tag} className="ws-tag" style={topicColor(tag)}>{tag}</span>)}
        </div>
        <div className="ws-row ws-wrap">
          <button className="ws-btn" disabled={busy} onClick={duplicate}>Дублювати креатив</button>
          {item.media.length > 0 && <a className="ws-btn" href={mediaUrl(`/api/admin/creatives/${id}/archive`)}>Завантажити архів</a>}
          {item.published_url && <a className="ws-btn" href={item.published_url} target="_blank" rel="noreferrer">Відкрити публікацію ↗</a>}
        </div>
        <div className="ws-seg" role="tablist">{Object.entries({ preview: "Перегляд", edit: "Поля", media: "Файли", review: "Оцінки" }).map(([key, name]) =>
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "is-on" : ""} onClick={() => setTab(key)}>{name}</button>)}</div>
      </>}
      {item && tab === "edit" && <CreativeEditor item={item} statusOptions={statusOptions} onSaved={(saved) => {
        if (id === "new") open(saved.id);
        else { reload(); setTab("preview"); }
      }} />}
      {item?.id && tab === "preview" && <CreativePreview key={item.id} item={item} />}
      {item?.id && tab === "media" && <CreativeMedia creative={item} refresh={reload} maxMb={maxMb} />}
      {item?.id && tab === "review" && <CreativeReview id={item.id} onSaved={refreshList} />}
    </div>
  </Modal>;
}

function CreativeEditor({ item, statusOptions, onSaved }) {
  const [fields, setFields] = useState(() => ({ ...Object.fromEntries(Object.keys(NEW).map((key) => [key, item[key]])),
    scheduled_at: kyivInput(item.scheduled_at), published_on: item.published_on || "", tags: item.tags.join(", "),
  }));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key) => (value) => setFields((state) => ({ ...state, [key]: value }));
  const input = (key) => (event) => set(key)(event.target.value);
  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = { ...fields, scheduled_at: fromKyiv(fields.scheduled_at), published_on: fields.published_on || null,
        tags: fields.tags.split(",").map((tag) => tag.trim()).filter(Boolean) };
      for (const key of ["reach", "saves", "shares"]) payload[key] = fields[key] === "" || fields[key] == null ? null : Number(fields[key]);
      onSaved(await (item.id ? updateCreative(item.id, payload) : createCreative(payload)));
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }
  const statuses = item.status === "approved" ? STATUSES : statusOptions;
  return <form className="ws-stack" onSubmit={save}>
    <Field label="Назва"><input className="ws-input" required maxLength={200} value={fields.title} onChange={input("title")} /></Field>
    <Field label="Опис"><textarea className="ws-input" maxLength={20000} rows={3} value={fields.description} onChange={input("description")} /></Field>
    <div className="ac-filters">
      <Select label="Тип" options={FORMATS} value={fields.format} onChange={set("format")} />
      <Select label="Призначення" options={PURPOSES} value={fields.purpose} onChange={set("purpose")} />
      <Select label="Статус" options={statuses} value={fields.status} onChange={set("status")} />
      <Field label="Тема або серія"><input className="ws-input" maxLength={120} value={fields.topic} onChange={input("topic")} /></Field>
      <Field label="Планова дата й час (Київ)"><input className="ws-input" type="datetime-local" value={fields.scheduled_at} onChange={input("scheduled_at")} /></Field>
      <Field label="Дата публікації"><input className="ws-input" type="date" value={fields.published_on} onChange={input("published_on")} /></Field>
    </div>
    {Object.entries({ caption: ["Підпис", 20000], hashtags: ["Хештеги", 2000], notes: ["Примітки", 20000] }).map(([key, [label, maxLength]]) =>
      <Field label={label} key={key}><textarea className="ws-input" rows={key === "caption" ? 5 : 2} maxLength={maxLength} value={fields[key]} onChange={input(key)} /></Field>)}
    <Field label="Заклик до дії (CTA)"><input className="ws-input" maxLength={500} value={fields.cta} onChange={input("cta")} /></Field>
    <Field label="Теги через кому"><input className="ws-input" maxLength={840} value={fields.tags} onChange={input("tags")} /></Field>
    <Field label="Посилання на публікацію"><input className="ws-input" type="url" maxLength={500} value={fields.published_url} onChange={input("published_url")} /></Field>
    <div className="ac-filters">
      {Object.entries({ reach: "Охоплення", saves: "Збереження", shares: "Репости" }).map(([key, label]) => <Field label={label} key={key}>
        <input className="ws-input" type="number" min={0} max={2147483647} step={1} value={fields[key] ?? ""} onChange={input(key)} />
      </Field>)}
    </div>
    <ErrorBox text={error} />
    <button className="ws-btn ws-btn--primary" disabled={busy || !fields.title.trim()}>{busy ? "Зберігаємо…" : "Зберегти креатив"}</button>
  </form>;
}

function CreativePreview({ item }) {
  const [index, setIndex] = useState(0);
  const [touch, setTouch] = useState(null);
  const [status, setStatus] = useState("");
  const files = item.media.map((slot) => slot.current);
  const file = files[index];
  const vertical = ["stories", "reels"].includes(item.format);
  const advance = (distance) => setIndex((current) => (current + distance + files.length) % files.length);
  async function copy() {
    try { await navigator.clipboard.writeText([item.caption, item.hashtags, item.cta].filter(Boolean).join("\n\n")); setStatus("Скопійовано"); }
    catch { setStatus("Не вдалося скопіювати. Виділіть і скопіюйте текст вручну."); }
  }
  return <article className="ac-post ws-card ws-stack">
    <header className="ws-row"><strong>Prime Academy</strong><span className="ws-tag">{FORMATS[item.format]}</span></header>
    <div className={`ac-post-frame${vertical ? " ac-post-frame--vertical" : ""}`} onTouchStart={(e) => setTouch(e.touches[0].clientX)} onTouchEnd={(e) => {
      if (files.length > 1 && touch !== null && Math.abs(e.changedTouches[0].clientX - touch) > 40) advance(e.changedTouches[0].clientX < touch ? 1 : -1);
      setTouch(null);
    }}>
      <MediaTile key={file?.id} file={file} controls />
    </div>
    {file && <p className="ws-muted ws-small">{fileSpecs(file)}</p>}
    {files.length > 1 && <div className="ac-carousel" aria-label="Слайди">
      <button className="ws-btn" onClick={() => advance(-1)} aria-label="Попередній слайд">‹</button>
      {files.map((file, i) => <button className="ac-dot" aria-pressed={i === index} aria-label={`Слайд ${i + 1}`} key={file.id} onClick={() => setIndex(i)} />)}
      <button className="ws-btn" onClick={() => advance(1)} aria-label="Наступний слайд">›</button>
    </div>}
    <strong>{item.title}</strong>
    {item.description && <p className="ac-copy ws-muted">{item.description}</p>}
    {item.caption && <p className="ac-copy">{item.caption}</p>}
    {item.hashtags && <p className="ac-copy ac-hashtags">{item.hashtags}</p>}
    {item.cta && <p className="ac-copy">{item.cta}</p>}
    {(item.caption || item.hashtags || item.cta) && <button className="ws-btn" onClick={copy}>Скопіювати підпис</button>}
    {status && <p className="ws-muted" role="status">{status}</p>}
  </article>;
}

function Rankings({ onClose, onOpen }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [group, setGroup] = useState("topic");
  useEffect(() => { getCreativeRankings().then(setData).catch((e) => setError(errorText(e))); }, []);
  return <Modal title="Рейтинги креативів" onClose={onClose} wide>
    <div className="ws-stack">
      <Select label="Групувати" options={{ topic: "За темою", format: "За типом" }} value={group} onChange={setGroup} />
      <ErrorBox text={error} />
      {data && Object.keys(data[group]).length === 0 && <p className="ws-muted">Поки немає оцінених креативів у цій групі.</p>}
      {Object.entries(data?.[group] || {}).map(([label, items]) => <section key={label} className="ws-card ws-stack">
        <h3>{group === "format" ? FORMATS[label] : label}</h3>
        {items.map((item) => <button className="ws-btn" key={item.id} onClick={() => onOpen(item.id)}>{item.title} · {item.average}/5</button>)}
      </section>)}
    </div>
  </Modal>;
}
