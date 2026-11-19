import { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { addAppEntry, deleteAppEntry, getAppEntries } from "../../api/workspace";
import { errorText } from "../../api/apiClientAuth";
import { AdminContext, Empty, ErrorBox, Field, fmtDate } from "../ws/ui";
import { topicColor } from "../ws/content";

const CTA = "Напиши ПРОБНИЙ у Direct";

function Copy({ text, children = "Копіювати" }) {
  const [status, setStatus] = useState("");
  async function copy() {
    try { await navigator.clipboard.writeText(text); setStatus("Скопійовано"); }
    catch { setStatus("Не вдалося скопіювати. Виділіть текст і скопіюйте його вручну."); }
  }
  return <div className="ws-row ws-wrap"><button type="button" className="ws-btn" onClick={copy}>{children}</button>
    {status && <span role="status" className="ws-muted ws-small">{status}</span>}</div>;
}

function TextField({ name, label, type = "text", maxLength, required = true, multiline = false, placeholder }) {
  const props = { name, maxLength, required, placeholder, className: "ws-input" };
  return <Field label={label}>{multiline ? <textarea rows={3} {...props} /> : <input type={type} {...props} />}</Field>;
}

function EntryBank({ kind, title, button, children, render, normalize = (values) => values, onCreated }) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [q, setQ] = useState("");
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = () => setRevision((value) => value + 1);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      getAppEntries(kind, { offset, q }).then((result) => { if (active) setData(result); })
        .catch((e) => { if (active) setError(errorText(e)); });
    }, 150);
    return () => { active = false; clearTimeout(timer); };
  }, [kind, offset, q, revision]);

  async function add(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = normalize(Object.fromEntries(new FormData(form)));
    setBusy(true);
    setError("");
    try {
      const saved = await addAppEntry({ kind, ...payload });
      if (kind !== "utm") form.reset();
      onCreated?.(saved);
      setQ(""); setOffset(0); refresh();
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  async function remove(item) {
    if (!window.confirm("Видалити цей запис?")) return;
    setError("");
    try { await deleteAppEntry(item.id); setOffset(0); refresh(); }
    catch (e) { setError(errorText(e)); }
  }

  return <section className="ws-stack">
    <form className="ws-card ws-stack" onSubmit={add}><h2>{title}</h2>{children}
      <button className="ws-btn ws-btn--primary" disabled={busy}>{busy ? "Зберігаємо…" : button}</button>
    </form>
    <Field label="Пошук у записах"><input className="ws-input" maxLength={200} value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} /></Field>
    <ErrorBox text={error} />
    {!data && !error && <p className="ws-muted" role="status">Завантажуємо…</p>}
    {data?.items.length === 0 && <Empty title="Записів не знайдено">Змініть пошук або додайте запис.</Empty>}
    <div className="apps-entry-grid">{data?.items.map((item) => <article key={item.id} className="ws-card ws-stack apps-entry">
      {render(item)}
      {item.can_delete && <button className="ws-btn" type="button" onClick={() => remove(item)}>Видалити</button>}
    </article>)}</div>
    {(offset > 0 || data?.has_more) && <div className="ws-row">
      <button type="button" className="ws-btn" disabled={!offset} onClick={() => setOffset(offset - 50)}>Назад</button>
      <button type="button" className="ws-btn" disabled={!data?.has_more} onClick={() => setOffset(offset + 50)}>Далі</button>
    </div>}
  </section>;
}

export function ContentTemplates() {
  const [tab, setTab] = useState("hashtags");
  return <div className="ws-stack">
    <div className="ws-seg" role="tablist">{Object.entries({ hashtags: "Набори хештегів", caption: "Шаблони підписів" }).map(([id, label]) =>
      <button type="button" role="tab" key={id} className={tab === id ? "is-on" : ""} aria-selected={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {tab === "hashtags" ? <EntryBank key="hashtags" kind="hashtags" title="Новий набір" button="Зберегти набір" render={(item) => <>
      <strong>{item.topic}</strong><p>{item.text}</p><Copy text={item.text} />
    </>}><TextField name="topic" label="Тема" maxLength={120} /><TextField name="text" label="Хештеги" maxLength={2000} multiline /></EntryBank>
      : <EntryBank key="caption" kind="caption" title="Новий шаблон" button="Зберегти шаблон" render={(item) => <>
        <strong>{item.title}</strong><p>{item.text}</p><p>{item.cta}</p><Copy text={`${item.text}\n\n${item.cta}`} />
      </>}><TextField name="title" label="Назва шаблону" maxLength={150} /><TextField name="text" label="Підпис" maxLength={10000} multiline />
        <p className="ws-muted">CTA: «{CTA}»</p></EntryBank>}
  </div>;
}

export function UtmBuilder() {
  const [result, setResult] = useState(null);
  return <div className="ws-stack">
    {result && <div className="ws-card ws-stack apps-entry" role="status"><strong>Готове посилання</strong><code>{result.result}</code><Copy text={result.result} /></div>}
    <EntryBank kind="utm" title="Нове UTM-посилання" button="Згенерувати й зберегти" onCreated={setResult} render={(item) => <>
      <strong>{item.utm_campaign}</strong><code>{item.result}</code><span className="ws-small ws-muted">{fmtDate(item.created_at)} · {item.utm_source} / {item.utm_medium}</span><Copy text={item.result} />
    </>}>
      <TextField name="url" label="Посилання" type="url" maxLength={2000} />
      <div className="apps-fields">
        <TextField name="utm_source" label="Джерело · utm_source" maxLength={120} placeholder="instagram" />
        <TextField name="utm_medium" label="Канал · utm_medium" maxLength={120} placeholder="paid_social" />
        <TextField name="utm_campaign" label="Кампанія · utm_campaign" maxLength={120} />
        <TextField name="utm_content" label="Креатив · utm_content" required={false} maxLength={120} />
      </div>
    </EntryBank>
  </div>;
}

export function PhraseBank() {
  const me = useContext(AdminContext);
  return <EntryBank kind="phrase" title="Нова фраза" button="Зберегти фразу"
    normalize={(values) => ({ ...values, tags: values.tags.split(",").map((tag) => tag.trim()).filter(Boolean) })} render={(item) => <>
      <strong lang="en">{item.text}</strong>
      {item.mistake && <p className="apps-phrase-mistake">Типова помилка: <span lang="en">{item.mistake}</span></p>}
      {item.translation && <p>{item.translation}</p>}
      <div className="ws-row ws-wrap">{item.tags.map((tag) => <span className="ws-tag" style={topicColor(tag)} key={tag}>{tag}</span>)}</div>
      <span className="ws-small ws-muted">Джерело: {item.source}</span>
      {me.sections.includes("creatives") && <Link className="ws-btn" to={`/admin/creatives?${new URLSearchParams({ open: "new", caption: [item.text, item.translation].filter(Boolean).join("\n") })}`}>Використати в креативі</Link>}
    </>}>
    <div className="apps-fields">
      <TextField name="text" label="Правильна фраза" maxLength={400} />
      <TextField name="mistake" label="Типова помилка" maxLength={400} required={false} />
      <TextField name="translation" label="Пояснення або переклад" maxLength={1000} required={false} />
      <TextField name="source" label="Джерело" maxLength={500} />
      <TextField name="tags" label="Теги через кому" maxLength={630} required={false} />
    </div>
  </EntryBank>;
}
