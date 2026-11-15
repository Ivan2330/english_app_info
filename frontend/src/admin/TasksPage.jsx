import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createTask, deleteTask, getPeople, getTask, getTasks, updateTask } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import Markdown from "./ws/Markdown.jsx";
import { Attachments, Comments } from "./ws/Discussion.jsx";
import { AdminContext, Empty, ErrorBox, Field, fmtDate, Hint, Modal, Tags, TagsInput } from "./ws/ui.jsx";

export const STATUSES = [
  { value: "new", label: "Нове" },
  { value: "in_progress", label: "В роботі" },
  { value: "review", label: "На перевірці" },
  { value: "done", label: "Готово" },
];
const PRIORITIES = [
  { value: "P0", label: "P0 — терміново" },
  { value: "P1", label: "P1 — звичайне" },
  { value: "P2", label: "P2 — коли буде час" },
];
const SCOPES = [
  { value: "mine", label: "Мої" },
  { value: "created", label: "Я поставив" },
  { value: "all", label: "Усі" },
];

/**
 * Завдання: список або дошка. Фільтри живуть в адресі (?scope=mine&overdue=1),
 * тож посилання з головної відкривають одразу потрібний зріз, і його можна переслати.
 */
export default function TasksPage() {
  const me = useContext(AdminContext);
  const [params, setParams] = useSearchParams();
  const [tasks, setTasks] = useState([]);
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(null);         // початкові значення нового завдання
  const view = params.get("view") || (typeof window !== "undefined" && window.innerWidth < 700 ? "list" : "board");

  const filters = useMemo(() => ({
    scope: params.get("scope") || "mine",
    status: params.get("status") || "",
    assignee_id: params.get("assignee_id") || "",
    overdue: params.get("overdue") === "1",
    q: params.get("q") || "",
  }), [params]);
  const openId = params.get("open");

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value === "" || value === false || value == null) next.delete(key); else next.set(key, value === true ? "1" : value);
    setParams(next, { replace: true });
  }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = { scope: filters.scope };
      if (filters.status) p.status = filters.status;
      if (filters.assignee_id) p.assignee_id = filters.assignee_id;
      if (filters.overdue) p.overdue = true;
      if (filters.q) p.q = filters.q;
      setTasks(await getTasks(p));
      setError("");
    } catch (e) { setError(errorText(e)); } finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { getPeople().then(setPeople).catch(() => {}); }, []);

  // «Створити завдання з цього звіту» приходить сюди з ?new=1&related_type=report…
  useEffect(() => {
    if (params.get("new") === "1") {
      setCreating({ title: params.get("title") || "", related_type: params.get("related_type"),
                    related_id: params.get("related_id") ? Number(params.get("related_id")) : null });
      const next = new URLSearchParams(params);
      ["new", "title", "related_type", "related_id"].forEach((k) => next.delete(k));
      setParams(next, { replace: true });
    }
  }, [params, setParams]);

  async function quickStatus(t, status) {
    try {
      const upd = await updateTask(t.id, { status });
      setTasks((list) => list.map((x) => (x.id === t.id ? upd : x)));
    } catch (e) { setError(errorText(e)); }
  }

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead ws-pagehead--row">
        <div>
          <h1 className="ws-h1">Завдання</h1>
          <p className="ws-muted">Ставте задачі одне одному. Виконавець здає «На перевірку», автор приймає і закриває.</p>
        </div>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--big" onClick={() => setCreating({})}>
          + Нове завдання
        </button>
      </header>

      <div className="ws-filters">
        <div className="ws-seg" role="group" aria-label="Чиї завдання">
          {SCOPES.map((s) => (
            <button key={s.value} type="button" className={filters.scope === s.value ? "is-on" : ""}
                    onClick={() => setParam("scope", s.value)}>{s.label}</button>
          ))}
        </div>
        <select className="ws-input ws-input--auto" value={filters.assignee_id} aria-label="Виконавець"
                onChange={(e) => setParam("assignee_id", e.target.value)}>
          <option value="">Будь-хто виконує</option>
          {people.map((p) => <option key={p.id} value={p.id}>Виконує: {p.name}</option>)}
        </select>
        <select className="ws-input ws-input--auto" value={filters.status} aria-label="Статус"
                onChange={(e) => setParam("status", e.target.value)}>
          <option value="">Усі статуси</option>
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <label className="ws-check">
          <input type="checkbox" checked={filters.overdue} onChange={(e) => setParam("overdue", e.target.checked)} />
          Лише прострочені
        </label>
        <input className="ws-input ws-input--search" type="search" placeholder="Пошук за назвою чи описом"
               defaultValue={filters.q} onKeyDown={(e) => e.key === "Enter" && setParam("q", e.currentTarget.value)}
               onBlur={(e) => setParam("q", e.currentTarget.value)} />
        <div className="ws-seg" role="group" aria-label="Вигляд">
          <button type="button" className={view === "board" ? "is-on" : ""} onClick={() => setParam("view", "board")}>Дошка</button>
          <button type="button" className={view === "list" ? "is-on" : ""} onClick={() => setParam("view", "list")}>Список</button>
        </div>
      </div>

      <ErrorBox text={error} />
      {loading && !tasks.length ? <p className="ws-muted">Завантажуємо…</p> : !tasks.length ? (
        <Empty title="Завдань немає">Змініть фільтри або створіть нове завдання кнопкою вгорі.</Empty>
      ) : view === "board" ? (
        <div className="ws-board">
          {STATUSES.map((s) => {
            const col = tasks.filter((t) => t.status === s.value);
            return (
              <section key={s.value} className={`ws-col st-${s.value}`}>
                <h2>{s.label} <span className="ws-count">{col.length}</span></h2>
                {col.map((t) => <TaskCard key={t.id} t={t} onOpen={() => setParam("open", t.id)} onStatus={quickStatus} me={me} />)}
              </section>
            );
          })}
        </div>
      ) : (
        <div className="ws-list">
          {tasks.map((t) => <TaskCard key={t.id} t={t} wide onOpen={() => setParam("open", t.id)} onStatus={quickStatus} me={me} />)}
        </div>
      )}

      {creating && (
        <TaskForm initial={creating} people={people} me={me}
                  onClose={() => setCreating(null)}
                  onSaved={(t) => { setCreating(null); load(); setParam("open", t.id); }} />
      )}
      {openId && (
        <TaskDetail id={Number(openId)} people={people} me={me}
                    onClose={() => setParam("open", "")}
                    onChanged={() => { load(); me.refreshCounters?.(); }} />
      )}
    </div>
  );
}

function nextStatuses(t) {
  const out = [];
  if (!t.can_change_status) return out;
  if (t.status === "new") out.push({ v: "in_progress", l: "Взяти в роботу" });
  if (t.status === "in_progress") out.push({ v: "review", l: "Здати на перевірку" });
  if (t.status === "review" && t.can_close) out.push({ v: "done", l: "Прийняти й закрити" });
  if (t.status === "review" && t.can_close) out.push({ v: "in_progress", l: "Повернути в роботу" });
  return out;
}

function TaskCard({ t, onOpen, onStatus, wide }) {
  return (
    <article className={`ws-task${wide ? " is-wide" : ""}${t.overdue ? " is-overdue" : ""}`}>
      <button type="button" className="ws-task__main" onClick={onOpen}>
        <span className="ws-task__top">
          <span className={`ws-prio p-${t.priority}`}>{t.priority}</span>
          {t.unread && <span className="ws-new">нове</span>}
          {wide && <span className={`ws-status st-${t.status}`}>{t.status_label}</span>}
        </span>
        <b>{t.title}</b>
        <span className="ws-task__meta">
          {t.assignee}{t.author !== t.assignee ? ` ← ${t.author}` : ""}
          {t.due_date && <> · <span className={t.overdue ? "ws-late" : ""}>до {fmtDate(t.due_date)}</span></>}
        </span>
        <Tags tags={t.tags} />
      </button>
      {nextStatuses(t).length > 0 && (
        <div className="ws-task__actions">
          {nextStatuses(t).map((s) => (
            <button key={s.v} type="button" className="ws-btn ws-btn--small" onClick={() => onStatus(t, s.v)}>{s.l}</button>
          ))}
        </div>
      )}
    </article>
  );
}

function TaskForm({ initial, people, me, onClose, onSaved, task }) {
  const [f, setF] = useState(() => ({
    title: task?.title ?? initial?.title ?? "",
    description: task?.description ?? "",
    assignee_id: task?.assignee_id ?? people.find((p) => !p.is_me)?.id ?? me.id,
    priority: task?.priority ?? "P1",
    due_date: task?.due_date ?? "",
    tags: task?.tags ?? [],
  }));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e?.target ? e.target.value : e });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const body = { ...f, assignee_id: Number(f.assignee_id), due_date: f.due_date || null };
    try {
      let saved;
      if (task) {
        if (!f.due_date) { delete body.due_date; body.clear_due_date = true; }
        saved = await updateTask(task.id, body);
      } else {
        if (initial?.related_type) Object.assign(body, { related_type: initial.related_type, related_id: initial.related_id });
        saved = await createTask(body);
      }
      onSaved(saved);
    } catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  }

  return (
    <Modal title={task ? "Змінити завдання" : "Нове завдання"} onClose={onClose} wide>
      <form className="ws-stack" onSubmit={submit}>
        <Field label="Що зробити">
          <input className="ws-input" required maxLength={200} value={f.title} onChange={set("title")}
                 placeholder="Наприклад: зняти Reel про пробний урок" autoFocus />
        </Field>
        <div className="ws-form2">
          <Field label="Хто виконує">
            <select className="ws-input" value={f.assignee_id} onChange={set("assignee_id")}>
              {people.map((p) => <option key={p.id} value={p.id}>{p.name}{p.is_me ? " (я)" : ""}</option>)}
            </select>
          </Field>
          <Field label="Терміновість">
            <select className="ws-input" value={f.priority} onChange={set("priority")}>
              {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </Field>
          <Field label="Дедлайн" hint="Необовʼязково">
            <input className="ws-input" type="date" value={f.due_date || ""} onChange={set("due_date")} />
          </Field>
          <Field label="Теги" hint="Через кому">
            <TagsInput value={f.tags} onChange={set("tags")} />
          </Field>
        </div>
        <Field label="Опис">
          <div className="ws-seg ws-seg--small">
            <button type="button" className={!preview ? "is-on" : ""} onClick={() => setPreview(false)}>Писати</button>
            <button type="button" className={preview ? "is-on" : ""} onClick={() => setPreview(true)}>Як виглядатиме</button>
          </div>
          {preview ? <div className="ws-preview"><Markdown text={f.description} /></div> : (
            <textarea className="ws-input" rows={7} value={f.description} onChange={set("description")}
                      placeholder="Деталі, посилання, що вважати готовим результатом" />
          )}
        </Field>
        <Hint>Форматування: **жирний**, *курсив*, - список, ## заголовок, [текст](https://посилання)</Hint>
        {initial?.related_type === "report" && <p className="ws-muted">Завдання буде повʼязане зі звітом №{initial.related_id}.</p>}
        <ErrorBox text={error} />
        <div className="ws-row">
          <button type="submit" className="ws-btn ws-btn--primary ws-btn--big" disabled={busy}>
            {busy ? "Зберігаємо…" : task ? "Зберегти зміни" : "Створити завдання"}
          </button>
          <button type="button" className="ws-btn" onClick={onClose}>Скасувати</button>
        </div>
      </form>
    </Modal>
  );
}

function TaskDetail({ id, people, me, onClose, onChanged }) {
  const [t, setT] = useState(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => getTask(id).then(setT).catch((e) => setError(errorText(e))), [id]);
  useEffect(() => { load(); }, [load]);

  async function setStatus(status) {
    try { setT(await updateTask(id, { status })); onChanged(); } catch (e) { setError(errorText(e)); }
  }

  async function remove() {
    if (!window.confirm("Видалити завдання разом із коментарями й файлами?")) return;
    try { await deleteTask(id); onChanged(); onClose(); } catch (e) { setError(errorText(e)); }
  }

  if (!t) return <Modal title="Завдання" onClose={onClose}>{error ? <ErrorBox text={error} /> : <p className="ws-muted">Завантажуємо…</p>}</Modal>;

  if (editing) {
    return <TaskForm task={t} people={people} me={me} onClose={() => setEditing(false)}
                     onSaved={(u) => { setT(u); setEditing(false); onChanged(); }} />;
  }

  return (
    <Modal title={t.title} onClose={onClose} wide>
      <div className="ws-detail">
        <div className="ws-detail__main ws-stack">
          <dl className="ws-facts">
            <div><dt>Статус</dt><dd><span className={`ws-status st-${t.status}`}>{t.status_label}</span></dd></div>
            <div><dt>Виконує</dt><dd>{t.assignee}</dd></div>
            <div><dt>Поставив</dt><dd>{t.author}</dd></div>
            <div><dt>Терміновість</dt><dd><span className={`ws-prio p-${t.priority}`}>{t.priority}</span></dd></div>
            <div><dt>Дедлайн</dt><dd className={t.overdue ? "ws-late" : ""}>{t.due_date ? fmtDate(t.due_date) : "без дедлайну"}</dd></div>
            {t.related_type === "report" && (
              <div><dt>Повʼязано</dt><dd><Link to={`/admin/reports/${t.related_id}`}>Звіт №{t.related_id}</Link></dd></div>
            )}
          </dl>
          <Tags tags={t.tags} />
          <ErrorBox text={error} />
          <div className="ws-row ws-wrap">
            {t.can_change_status && STATUSES.filter((s) => s.value !== t.status && (s.value !== "done" || t.can_close)
              && (t.status !== "done" || t.can_close)).map((s) => (
              <button key={s.value} type="button" className={`ws-btn${s.value === "done" ? " ws-btn--primary" : ""}`}
                      onClick={() => setStatus(s.value)}>→ {s.label}</button>
            ))}
          </div>
          {t.status === "review" && !t.can_close && (
            <Hint>Завдання на перевірці. Закрити його може автор — {t.author}.</Hint>
          )}
          <section className="ws-block">
            <h3>Опис</h3>
            <Markdown text={t.description} empty="Опису немає." />
          </section>
          <Attachments type="task" id={t.id} onChange={onChanged} />
          <div className="ws-row">
            {t.can_edit && <button type="button" className="ws-btn" onClick={() => setEditing(true)}>Змінити завдання</button>}
            {t.can_edit && <button type="button" className="ws-btn ws-btn--danger" onClick={remove}>Видалити</button>}
          </div>
        </div>
        <div className="ws-detail__side">
          <Comments type="task" id={t.id} onChange={onChanged} />
          <p className="ws-muted ws-small">Створено {fmtDate(t.created_at, true)}{t.done_at ? ` · закрито ${fmtDate(t.done_at, true)}` : ""}</p>
        </div>
      </div>
    </Modal>
  );
}
