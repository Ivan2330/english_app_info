// Коментарі, оцінки й файли — однакові для завдань, звітів і майбутніх розділів.
import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { API_URL } from "../../config";
import { errorText } from "../../api/apiClientAuth";
import {
  addComment, deleteComment, deleteFile, deleteReview, editComment, getComments, getFiles,
  getReviews, saveReview, uploadFile,
} from "../../api/workspace";
import Markdown from "./Markdown.jsx";
import { AdminContext, ErrorBox, fmtDate, fmtSize, Hint } from "./ui.jsx";

/* ================================================================ коментарі */

export function Comments({ type, id, onChange }) {
  const [items, setItems] = useState([]);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState(null);      // {id, body}
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => getComments(type, id).then(setItems).catch((e) => setError(errorText(e))), [type, id]);
  useEffect(() => { load(); }, [load]);

  async function send(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      await addComment(type, id, text);
      setText("");
      await load();
      onChange?.();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit() {
    try {
      await editComment(editing.id, editing.body);
      setEditing(null);
      load();
    } catch (err) { setError(errorText(err)); }
  }

  async function remove(c) {
    if (!window.confirm("Видалити коментар?")) return;
    try { await deleteComment(c.id); load(); } catch (err) { setError(errorText(err)); }
  }

  return (
    <section className="ws-block">
      <h3>Коментарі {items.length > 0 && <span className="ws-count">{items.length}</span>}</h3>
      {items.length === 0 && <p className="ws-muted">Ще ніхто нічого не написав.</p>}
      <ul className="ws-comments">
        {items.map((c) => (
          <li key={c.id} className="ws-comment">
            <div className="ws-comment__head">
              <b>{c.author}</b>
              <span>{fmtDate(c.created_at, true)}{c.edited && " · змінено"}</span>
            </div>
            {editing?.id === c.id ? (
              <div className="ws-stack">
                <textarea className="ws-input" rows={3} value={editing.body}
                          onChange={(e) => setEditing({ ...editing, body: e.target.value })} />
                <div className="ws-row">
                  <button type="button" className="ws-btn ws-btn--primary" onClick={saveEdit}>Зберегти</button>
                  <button type="button" className="ws-btn" onClick={() => setEditing(null)}>Скасувати</button>
                </div>
              </div>
            ) : (
              <Markdown text={c.body} />
            )}
            {c.mine && editing?.id !== c.id && (
              <div className="ws-comment__actions">
                <button type="button" onClick={() => setEditing({ id: c.id, body: c.body })}>Змінити</button>
                <button type="button" onClick={() => remove(c)}>Видалити</button>
              </div>
            )}
          </li>
        ))}
      </ul>
      <form className="ws-stack" onSubmit={send}>
        <textarea className="ws-input" rows={3} value={text} onChange={(e) => setText(e.target.value)}
                  placeholder="Напишіть коментар…" />
        <Hint>Можна markdown: **жирний**, - список, [посилання](https://…)</Hint>
        <ErrorBox text={error} />
        <button type="submit" className="ws-btn ws-btn--primary" disabled={busy || !text.trim()}>
          {busy ? "Надсилаємо…" : "Додати коментар"}
        </button>
      </form>
    </section>
  );
}

/* ================================================================ оцінки */

export function Reviews({ type, id, onChange, maxScore = 10 }) {
  const [data, setData] = useState({ average: null, count: 0, items: [] });
  const [score, setScore] = useState(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    const d = await getReviews(type, id);
    setData(d);
    const mine = d.items.find((i) => i.mine);
    setScore(mine?.score ?? null);
    setBody(mine?.body ?? "");
  }, [type, id]);
  useEffect(() => { load().catch((e) => setError(errorText(e))); }, [load]);

  const mine = data.items.find((i) => i.mine);

  async function save() {
    setError("");
    try {
      setData(await saveReview(type, id, score, body));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onChange?.();
    } catch (e) { setError(errorText(e)); }
  }

  async function remove() {
    try {
      setData(await deleteReview(type, id));
      setScore(null);
      setBody("");
      onChange?.();
    } catch (e) { setError(errorText(e)); }
  }

  return (
    <section className="ws-block">
      <h3>
        Оцінки{" "}
        {data.average != null
          ? <span className="ws-score">середня {data.average} з {maxScore} · {data.count}</span>
          : <span className="ws-muted">поки без балів</span>}
      </h3>

      <div className="ws-review-form">
        <span className="ws-field__label">{maxScore === 5 ? "Ваш бал" : "Ваш бал (необовʼязково)"}</span>
        <div className={`ws-scale${maxScore === 5 ? " ws-scale--5" : ""}`} role="radiogroup" aria-label={`Бал від 1 до ${maxScore}`}>
          {Array.from({ length: maxScore }, (_, i) => i + 1).map((n) => (
            <button key={n} type="button" role="radio" aria-checked={score === n}
                    className={score === n ? "is-on" : ""} onClick={() => setScore(score === n ? null : n)}>
              {n}
            </button>
          ))}
        </div>
        <textarea className="ws-input" rows={2} value={body} onChange={(e) => setBody(e.target.value)}
                  placeholder="Що добре, що варто змінити" />
        <ErrorBox text={error} />
        <div className="ws-row">
          <button type="button" className="ws-btn ws-btn--primary" onClick={save}
                  disabled={score == null && (maxScore === 5 || !body.trim())}>
            {saved ? "Збережено ✓" : mine ? "Оновити мою оцінку" : "Зберегти оцінку"}
          </button>
          {mine && <button type="button" className="ws-btn" onClick={remove}>Прибрати мою</button>}
        </div>
      </div>

      {data.items.filter((i) => !i.mine).length > 0 && (
        <ul className="ws-reviews">
          {data.items.filter((i) => !i.mine).map((r) => (
            <li key={r.id}>
              <b>{r.author}</b>
              {r.score != null && <span className="ws-score">{r.score}/{maxScore}</span>}
              {r.body && <p>{r.body}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/* ================================================================ файли */

const ACCEPT = ".png,.jpg,.jpeg,.webp,.gif,.mp4,.mov,.pdf,.docx,.xlsx,.csv,.txt,.md";

export function fileUrl(f, download = false) {
  return `${API_URL}${f.url}${download ? "?download=true" : ""}`;
}

export function Attachments({ type, id, onChange, title = "Файли", accept = ACCEPT }) {
  const [items, setItems] = useState([]);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);           // переглядач для pdf
  const input = useRef(null);
  const { upload_limits: lim = { max_mb: 20, video_max_mb: 300 } } = useContext(AdminContext) || {};

  const load = useCallback(() => getFiles(type, id).then(setItems).catch((e) => setError(errorText(e))), [type, id]);
  useEffect(() => { load(); }, [load]);

  async function upload(files) {
    setError("");
    for (const file of files) {
      try {
        setProgress({ name: file.name, pct: 0 });
        await uploadFile(type, id, file, (pct) => setProgress({ name: file.name, pct }));
      } catch (e) {
        setError(`${file.name}: ${errorText(e)}`);
      }
    }
    setProgress(null);
    if (input.current) input.current.value = "";
    load();
    onChange?.();
  }

  async function remove(f) {
    if (!window.confirm(`Видалити файл «${f.name}»?`)) return;
    try { await deleteFile(f.id); load(); } catch (e) { setError(errorText(e)); }
  }

  return (
    <section className="ws-block">
      <h3>{title} {items.length > 0 && <span className="ws-count">{items.length}</span>}</h3>
      <div className="ws-files">
        {items.map((f) => (
          <div key={f.id} className="ws-file">
            {f.kind === "image" && (
              <a href={fileUrl(f)} target="_blank" rel="noreferrer" className="ws-file__preview">
                <img src={fileUrl(f)} alt={f.name} loading="lazy" />
              </a>
            )}
            {f.kind === "video" && (
              // eslint-disable-next-line jsx-a11y/media-has-caption
              <video className="ws-file__preview" src={fileUrl(f)} controls preload="metadata" />
            )}
            <div className="ws-file__meta">
              <b title={f.name}>{f.name}</b>
              <span>{fmtSize(f.size)} · {f.uploaded_by}</span>
              <div className="ws-file__actions">
                {f.mime === "application/pdf" && (
                  <button type="button" onClick={() => setOpen(open?.id === f.id ? null : f)}>
                    {open?.id === f.id ? "Сховати" : "Читати тут"}
                  </button>
                )}
                <a href={fileUrl(f, true)}>Завантажити</a>
                <button type="button" onClick={() => remove(f)}>Видалити</button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {open && <iframe className="ws-pdf" src={fileUrl(open)} title={open.name} />}

      <input ref={input} type="file" multiple accept={accept} hidden
             onChange={(e) => upload([...e.target.files])} />
      {progress ? (
        <div className="ws-progress"><span>{progress.name}</span><i style={{ width: `${progress.pct}%` }} />
          <b>{progress.pct}%</b></div>
      ) : (
        <button type="button" className="ws-btn" onClick={() => input.current?.click()}>+ Додати файл</button>
      )}
      <Hint>Картинки, відео (mp4, mov), pdf, docx, xlsx, csv, txt, md. Документи й картинки до {lim.max_mb} МБ, відео до {lim.video_max_mb} МБ.</Hint>
      <ErrorBox text={error} />
    </section>
  );
}
