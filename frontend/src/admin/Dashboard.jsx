import { useEffect, useState } from "react";
import { adminStats } from "../api/admin.js";

const PERIODS = [
  { days: 7, label: "7 днів" },
  { days: 30, label: "30 днів" },
  { days: 90, label: "90 днів" },
];

const DEVICE_LABEL = { mobile: "Телефон", tablet: "Планшет", desktop: "Компʼютер" };

export default function Dashboard() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    adminStats(days)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setError("Не вдалося завантажити статистику"));
    return () => { cancelled = true; };
  }, [days]);

  if (error) return <p className="adm-empty">{error}</p>;
  if (!data) return <p className="adm-empty">Рахуємо…</p>;

  const maxVisits = Math.max(1, ...data.timeline.map((d) => d.visits));
  const totalDevices = Object.values(data.devices).reduce((a, b) => a + b, 0) || 1;

  return (
    <>
      <header className="adm-head">
        <h1>Дашборд</h1>
        <div className="adm-tabs">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              type="button"
              className={p.days === days ? "is-on" : ""}
              onClick={() => setDays(p.days)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </header>

      {/* ---------- ключові числа ---------- */}
      <div className="adm-cards">
        <Card
          label="Унікальних відвідувачів"
          value={data.uniques}
          change={data.uniques_change}
          hint={`${data.visits} переглядів сторінок`}
        />
        <Card
          label="Заявок"
          value={data.leads_total}
          hint={`${data.leads_new} нових · ${data.leads_converted} дійшли до оплати`}
        />
        <Card
          label="Оплачених замовлень"
          value={data.orders_paid}
          hint={`${data.orders_total} створено всього`}
        />
        <Card
          label="Виручка"
          value={`${data.revenue_uah.toLocaleString("uk-UA")} ₴`}
          hint="за фактично отриманими платежами"
        />
      </div>

      {/* ---------- воронка ----------
          Головний блок сторінки. Окремі числа вище не кажуть, де проблема;
          воронка показує, на якому саме кроці люди зникають. */}
      <section className="adm-panel">
        <h2>Воронка</h2>
        <div className="adm-funnel">
          {data.funnel.map((step, i) => {
            const width = data.funnel[0].value
              ? Math.max(4, (step.value / data.funnel[0].value) * 100)
              : 4;
            return (
              <div key={step.step} className="adm-funnel__row">
                <span className="adm-funnel__name">{step.step}</span>
                <div className="adm-funnel__bar">
                  <i style={{ width: `${width}%` }} />
                  <b>{step.value}</b>
                </div>
                <span className="adm-funnel__pct">
                  {i === 0 ? "—" : `${step.of_prev}% від попереднього`}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* ---------- динаміка ---------- */}
      <section className="adm-panel">
        <h2>Відвідування по днях</h2>
        {data.timeline.length === 0 ? (
          <p className="adm-empty">Даних поки немає. Лічильник рахує з моменту запуску.</p>
        ) : (
          <div className="adm-chart">
            {data.timeline.map((d) => (
              <div
                key={d.date}
                className="adm-chart__col"
                title={`${d.date}: ${d.visits} переглядів, ${d.uniques} унікальних`}
              >
                <i style={{ height: `${(d.visits / maxVisits) * 100}%` }} />
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="adm-grid2">
        <section className="adm-panel">
          <h2>Популярні сторінки</h2>
          <ul className="adm-list">
            {data.top_pages.map((p) => (
              <li key={p.path}><span>{p.path}</span><b>{p.visits}</b></li>
            ))}
            {data.top_pages.length === 0 && <li className="adm-empty">Порожньо</li>}
          </ul>
        </section>

        <section className="adm-panel">
          <h2>Джерела</h2>
          {/* «Прямі заходи» тут майже завжди Instagram: посилання
              з застосунку відкриваються без реферера. */}
          <ul className="adm-list">
            {data.sources.map((s) => (
              <li key={s.source}><span>{s.source}</span><b>{s.visitors}</b></li>
            ))}
            {data.sources.length === 0 && <li className="adm-empty">Порожньо</li>}
          </ul>
        </section>
      </div>

      <section className="adm-panel">
        <h2>Пристрої</h2>
        <div className="adm-devices">
          {Object.entries(data.devices).map(([k, v]) => (
            <div key={k} className="adm-device">
              <span>{DEVICE_LABEL[k] || k}</span>
              <b>{Math.round((v / totalDevices) * 100)}%</b>
              <i style={{ width: `${(v / totalDevices) * 100}%` }} />
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function Card({ label, value, change, hint }) {
  return (
    <article className="adm-card">
      <p className="adm-card__label">{label}</p>
      <div className="adm-card__value">
        {value}
        {change != null && (
          <span className={change >= 0 ? "is-up" : "is-down"}>
            {change >= 0 ? "↑" : "↓"} {Math.abs(change)}%
          </span>
        )}
      </div>
      {hint && <p className="adm-card__hint">{hint}</p>}
    </article>
  );
}
