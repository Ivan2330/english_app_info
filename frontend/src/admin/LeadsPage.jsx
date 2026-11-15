import { useCallback, useEffect, useState } from "react";
import { adminGetLeads, adminLeadSources, adminUpdateLead } from "../api/admin.js";
import { AttributionBlock, SourceFilter, sourceLabel } from "./SourceBits.jsx";

const STATUSES = [
  { value: "new", label: "Нова" },
  { value: "contacted", label: "На зв'язку" },
  { value: "trial_scheduled", label: "Пробний призначено" },
  { value: "trial_done", label: "Був на пробному" },
  { value: "converted", label: "Оплатив" },
  { value: "lost", label: "Відмова" },
];

const STATUS_LABEL = Object.fromEntries(STATUSES.map((s) => [s.value, s.label]));

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uk-UA", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export default function LeadsPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);   // розгорнута заявка

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetLeads({ ...(status ? { status } : {}), ...(source ? { utm_source: source } : {}) });
      setItems(Array.isArray(data) ? data : data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [status, source]);

  useEffect(() => { load(); }, [load]);

  async function setLeadStatus(lead, value) {
    // Оптимістично: менеджер клацає статуси швидко, чекати відповідь
    // на кожен клік — це відчутна затримка в роботі.
    setItems((list) => list.map((l) => (l.id === lead.id ? { ...l, status: value } : l)));
    try {
      await adminUpdateLead(lead.id, { status: value });
    } catch {
      load();   // не вийшло — повертаємо реальний стан
    }
  }

  return (
    <>
      <header className="adm-head">
        <h1>Заявки</h1>
        <div className="adm-tabs">
          <button type="button" className={!status ? "is-on" : ""} onClick={() => setStatus("")}>
            Усі
          </button>
          {STATUSES.map((s) => (
            <button
              key={s.value}
              type="button"
              className={status === s.value ? "is-on" : ""}
              onClick={() => setStatus(s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <SourceFilter load={adminLeadSources} value={source} onChange={setSource} />
      </header>

      {loading && <p className="adm-empty">Завантажуємо…</p>}
      {!loading && items.length === 0 && <p className="adm-empty">Заявок немає</p>}

      <div className="adm-rows">
        {items.map((lead) => (
          <article key={lead.id} className={`adm-row st-${lead.status}`}>
            <div className="adm-row__main" onClick={() => setOpen(open === lead.id ? null : lead.id)}>
              <div className="adm-row__who">
                <b>{lead.name} {lead.status === "new" && <span className="adm-new">нова</span>}</b>
                <span>{lead.phone || lead.telegram || lead.email || "без контакту"}</span>
              </div>

              <div className="adm-row__meta">
                {/* Мітка джерела показує, звідки прийшла заявка.
                    site/level-quiz означає, що всередині є відповіді тесту —
                    їх викладач дивиться до пробного уроку. */}
                <span className="adm-tag">{lead.source || "site"}</span>
                {sourceLabel(lead.attribution) && <span className="adm-tag adm-tag--ad">{sourceLabel(lead.attribution)}</span>}
                <span className="adm-date">{fmt(lead.created_at)}</span>
              </div>

              <select
                className="adm-select"
                value={lead.status}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => setLeadStatus(lead, e.target.value)}
              >
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>

            {open === lead.id && (
              <div className="adm-row__body">
                <dl>
                  {lead.phone && <><dt>Телефон</dt><dd><a href={`tel:${lead.phone}`}>{lead.phone}</a></dd></>}
                  {lead.telegram && <><dt>Telegram</dt><dd>{lead.telegram}</dd></>}
                  {lead.email && <><dt>Email</dt><dd><a href={`mailto:${lead.email}`}>{lead.email}</a></dd></>}
                  {lead.audience && <><dt>Для кого</dt><dd>{lead.audience}</dd></>}
                  {lead.level && <><dt>Рівень</dt><dd>{lead.level}</dd></>}
                  {lead.preferred_time && <><dt>Зручний час</dt><dd>{lead.preferred_time}</dd></>}
                  <dt>Статус</dt><dd>{STATUS_LABEL[lead.status] || lead.status}</dd>
                  <AttributionBlock a={lead.attribution} />
                </dl>

                {lead.comment && (
                  /* Коментар зберігає переноси рядків: у заявках із тесту
                     рівня тут лежить розбивка по питаннях. */
                  <pre className="adm-comment">{lead.comment}</pre>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
