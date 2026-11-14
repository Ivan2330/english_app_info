import { useCallback, useEffect, useState } from "react";
import { adminGetQuotes, adminUpdateQuote } from "../api/admin.js";

/**
 * Черга заявок на розрахунок (діти, корпоратив).
 *
 * Клієнт цін не бачить. Тут менеджер бачить параметри, попередній розрахунок
 * (це підказка, а не пропозиція) і особисто відписує клієнту.
 */
const STATUSES = [
  { value: "new", label: "Нова" },
  { value: "in_progress", label: "Рахую" },
  { value: "replied", label: "Відповів" },
  { value: "closed", label: "Закрито" },
];
const STATUS_LABEL = Object.fromEntries(STATUSES.map((s) => [s.value, s.label]));
const KIND_LABEL = { kids: "Діти", corporate: "Компанія" };
const FORMAT_LABEL = { individual: "індивідуально", pair: "у парі", group: "група" };

const uah = (n) => (n == null ? "—" : `${Number(n).toLocaleString("uk-UA")} ₴`);

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uk-UA", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function Params({ q }) {
  const p = q.params || {};
  if (q.kind === "kids") {
    return (
      <>
        <dt>Вік</dt><dd>{p.age}</dd>
        <dt>Формат</dt><dd>{FORMAT_LABEL[p.format] || p.format}</dd>
        <dt>Уроків</dt><dd>{p.lessons}</dd>
      </>
    );
  }
  return (
    <>
      {q.company && <><dt>Компанія</dt><dd>{q.company}</dd></>}
      <dt>Людей</dt><dd>{p.people}</dd>
      <dt>Формат</dt><dd>{FORMAT_LABEL[p.format] || p.format}</dd>
      <dt>Термін</dt><dd>{p.months} міс.</dd>
      <dt>Ціль</dt><dd>{p.goal}</dd>
    </>
  );
}

function Preview({ q }) {
  const c = q.calc_preview;
  if (!c) return null;
  return (
    <div className="adm-note">
      <b>Попередній розрахунок (не пропозиція):</b>{" "}
      {q.kind === "kids" ? (
        <>
          {c.lessons} × {uah(c.rate)}{c.per_person ? " з дитини" : ""} = <b>{uah(c.total)}</b>
          {c.age_in_range === false ? " · вік поза 5–12" : ""}
        </>
      ) : (
        <>
          {c.groups} гр. × {c.sessions_per_group} занять × {uah(c.price_per_session)}
          {c.discount_percent ? `, знижка −${c.discount_percent}%` : ""} = <b>{uah(c.total)}</b>
          {c.assessment_free ? " · оцінка рівня безкоштовна" : ""}
        </>
      )}
    </div>
  );
}

export default function QuotesPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);
  const [notes, setNotes] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetQuotes(status ? { status } : {});
      setItems(Array.isArray(data) ? data : []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  async function setQuoteStatus(q, value) {
    setItems((list) => list.map((x) => (x.id === q.id ? { ...x, status: value } : x)));
    try {
      await adminUpdateQuote(q.id, { status: value });
    } catch {
      load();
    }
  }

  async function saveNote(q) {
    const text = notes[q.id] ?? q.admin_note ?? "";
    try {
      await adminUpdateQuote(q.id, { admin_note: text });
      setItems((list) => list.map((x) => (x.id === q.id ? { ...x, admin_note: text } : x)));
    } catch {
      load();
    }
  }

  return (
    <>
      <header className="adm-head">
        <h1>Розрахунки</h1>
        <div className="adm-tabs">
          <button type="button" className={!status ? "is-on" : ""} onClick={() => setStatus("")}>Усі</button>
          {STATUSES.map((s) => (
            <button key={s.value} type="button" className={status === s.value ? "is-on" : ""}
                    onClick={() => setStatus(s.value)}>
              {s.label}
            </button>
          ))}
        </div>
      </header>

      {loading && <p className="adm-empty">Завантажуємо…</p>}
      {!loading && items.length === 0 && <p className="adm-empty">Заявок немає</p>}

      <div className="adm-rows">
        {items.map((q) => (
          <article key={q.id} className={`adm-row st-${q.status}`}>
            <div className="adm-row__main" onClick={() => setOpen(open === q.id ? null : q.id)}>
              <div className="adm-row__who">
                <b>{q.name}</b>
                <span>{q.phone || q.telegram || q.email || "без контакту"}</span>
              </div>
              <div className="adm-row__meta">
                <span className="adm-tag">{KIND_LABEL[q.kind] || q.kind}</span>
                <span className="adm-date">{fmt(q.created_at)}</span>
              </div>
              <select className="adm-select" value={q.status}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setQuoteStatus(q, e.target.value)}>
                {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            {open === q.id && (
              <div className="adm-row__body">
                <dl>
                  {q.phone && <><dt>Телефон</dt><dd><a href={`tel:${q.phone}`}>{q.phone}</a></dd></>}
                  {q.email && <><dt>Email</dt><dd><a href={`mailto:${q.email}`}>{q.email}</a></dd></>}
                  {q.telegram && <><dt>Telegram</dt><dd>{q.telegram}</dd></>}
                  <Params q={q} />
                  <dt>Статус</dt><dd>{STATUS_LABEL[q.status] || q.status}</dd>
                </dl>
                {q.comment && <pre className="adm-comment">{q.comment}</pre>}
                <Preview q={q} />
                <label className="adm-note">
                  <span>Нотатка (клієнту не видно)</span>
                  <textarea rows={3} value={notes[q.id] ?? q.admin_note ?? ""}
                            onChange={(e) => setNotes((n) => ({ ...n, [q.id]: e.target.value }))} />
                  <button type="button" onClick={() => saveNote(q)}>Зберегти нотатку</button>
                </label>
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
