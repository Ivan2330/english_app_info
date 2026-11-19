import { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCreatives, setCreativeSchedule } from "../../api/workspace";
import { errorText } from "../../api/apiClientAuth";
import { AdminContext, Empty, ErrorBox, Field, fmtDate, Modal } from "../ws/ui";
import { FORMATS, topicColor } from "../ws/content";
import { fromKyiv, kyivInput } from "../ws/kyiv";

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"];
const iso = (date) => date.toISOString().slice(0, 10);
const toDate = (day) => new Date(`${day}T12:00:00Z`);
const step = (day, delta) => { const date = toDate(day); date.setUTCDate(date.getUTCDate() + delta); return iso(date); };
const monday = (day) => step(day, -((toDate(day).getUTCDay() + 6) % 7));
const monthFirst = (day) => `${day.slice(0, 7)}-01`;
function moveMonth(day, delta) {
  const first = toDate(monthFirst(day));
  first.setUTCMonth(first.getUTCMonth() + delta);
  return iso(first);
}

export default function PublicationCalendar() {
  const me = useContext(AdminContext);
  if (!me.sections.includes("creatives")) return <Empty title="Потрібен доступ до креативів">Власник може увімкнути «Креативи» в розділі «Команда».</Empty>;
  return <Calendar />;
}

function Calendar() {
  const today = kyivInput(new Date()).slice(0, 10);
  const [anchor, setAnchor] = useState(today);
  const [view, setView] = useState("week");
  const [items, setItems] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [editor, setEditor] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const start = monday(view === "week" ? anchor : monthFirst(anchor));
  const end = view === "week" ? step(start, 7) : step(monday(step(moveMonth(anchor, 1), -1)), 7);
  const days = [];
  for (let day = start; day < end; day = step(day, 1)) days.push(day);

  useEffect(() => {
    let active = true;
    async function load() {
      const all = [];
      let offset = 0;
      try {
        setItems(null);
        setError("");
        while (active) {
          const page = await getCreatives({ scheduled_from: fromKyiv(`${start}T00:00`), scheduled_to: fromKyiv(`${end}T00:00`), limit: 200, offset });
          if (!active) return;
          all.push(...page.items);
          if (!page.has_more) break;
          offset += page.items.length;
        }
        if (active) setItems(all);
      } catch (e) { if (active) setError(errorText(e)); }
    }
    load();
    return () => { active = false; };
  }, [start, end]);

  const grouped = new Map();
  for (const item of items || []) {
    const day = kyivInput(item.scheduled_at).slice(0, 10);
    if (!grouped.has(day)) grouped.set(day, []);
    grouped.get(day).push(item);
  }
  for (const dayItems of grouped.values()) dayItems.sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  async function reschedule(item, day) {
    if (busy || !day || day === kyivInput(item.scheduled_at).slice(0, 10)) return;
    setBusy(true);
    setError("");
    try {
      const saved = await setCreativeSchedule(item.id, fromKyiv(`${day}T${kyivInput(item.scheduled_at).slice(11)}`));
      setItems((rows) => rows?.map((row) => row.id === item.id ? saved : row));
      setEditor(null);
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  const change = (delta) => setAnchor(view === "week" ? step(anchor, delta * 7) : moveMonth(anchor, delta));
  const heading = view === "week" ? `${fmtDate(start)} – ${fmtDate(step(end, -1))}`
    : new Intl.DateTimeFormat("uk-UA", { month: "long", year: "numeric", timeZone: "UTC" }).format(toDate(anchor));
  return <div className="ws-stack">
    <div className="ws-row ws-wrap">
      <button className="ws-btn" type="button" onClick={() => change(-1)} aria-label="Попередній період">←</button>
      <strong>{heading}</strong>
      <button className="ws-btn" type="button" onClick={() => change(1)} aria-label="Наступний період">→</button>
      <button className="ws-btn" type="button" onClick={() => setAnchor(today)}>Сьогодні</button>
      <div className="ws-seg" role="group" aria-label="Період">
        <button type="button" onClick={() => setView("week")} aria-pressed={view === "week"} className={view === "week" ? "is-on" : ""}>Тиждень</button>
        <button type="button" onClick={() => setView("month")} aria-pressed={view === "month"} className={view === "month" ? "is-on" : ""}>Місяць</button>
      </div>
    </div>
    <p className="ws-muted ws-small">Час за Києвом. Перетягніть креатив на інший день або відкрийте картку, щоб змінити дату.</p>
    <ErrorBox text={error} />
    {!items && !error && <p role="status" className="ws-muted">Завантажуємо…</p>}
    {items?.length === 0 && <p className="ws-muted">На цей період нічого не заплановано. <Link className="ws-more" to="/admin/creatives">Запланувати креатив →</Link></p>}
    <div className="apps-calendar-scroll" tabIndex={0} aria-label="Календар публікацій">
      <div className="apps-calendar">
        {WEEKDAYS.map((day) => <div key={day} className="apps-weekday">{day}</div>)}
        {days.map((day) => <div key={day} className={`apps-day${day === today ? " apps-day--today" : ""}${view === "month" && day.slice(0, 7) !== anchor.slice(0, 7) ? " apps-day--other" : ""}`}
          onDragOver={(e) => { if (dragging && !busy) e.preventDefault(); }} onDrop={(e) => {
            e.preventDefault();
            if (dragging) reschedule(dragging, day);
            setDragging(null);
          }}>
          <time dateTime={day}>{Number(day.slice(-2))}</time>
          {grouped.get(day)?.map((item) => <button type="button" key={item.id} className="apps-event" style={topicColor(item.format)}
            draggable={!busy} onDragStart={(e) => { e.dataTransfer.setData("text/plain", String(item.id)); setDragging(item); }}
            onDragEnd={() => setDragging(null)} onClick={() => setEditor(item)}>
            <span>{kyivInput(item.scheduled_at).slice(11)} · {FORMATS[item.format]}</span>
            <strong>{item.title}</strong>
          </button>)}
        </div>)}
      </div>
    </div>
    {editor && <Modal title={editor.title} onClose={() => setEditor(null)}>
      <form className="ws-stack" onSubmit={(e) => { e.preventDefault(); reschedule(editor, new FormData(e.currentTarget).get("date")); }}>
        <Field label="Планова дата"><input name="date" className="ws-input" type="date" required defaultValue={kyivInput(editor.scheduled_at).slice(0, 10)} /></Field>
        <ErrorBox text={error} />
        <button className="ws-btn ws-btn--primary" disabled={busy}>Зберегти дату</button>
        <Link className="ws-btn" to={`/admin/creatives?open=${editor.id}`}>Відкрити креатив</Link>
      </form>
    </Modal>}
  </div>;
}
