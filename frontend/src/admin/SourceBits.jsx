import { useEffect, useState } from "react";

/** Випадаючий фільтр «Джерело». `load` повертає [{value, label, count}] з бекенда. */
export function SourceFilter({ load, value, onChange }) {
  const [options, setOptions] = useState([]);
  useEffect(() => { load().then(setOptions).catch(() => setOptions([])); }, [load]);
  return (
    <label className="adm-source">
      <span>Джерело</span>
      <select className="adm-select" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Усі джерела</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label} ({o.count})</option>
        ))}
      </select>
    </label>
  );
}

/** Коротка мітка «facebook · кампанія» для рядка списку; null, якщо джерело невідоме. */
export function sourceLabel(a) {
  if (!a || !a.utm_source) return null;
  return a.utm_campaign ? `${a.utm_source} · ${a.utm_campaign}` : a.utm_source;
}

/** Деталі джерела в розгорнутій картці. */
export function AttributionBlock({ a }) {
  if (!a) return null;
  const has = a.utm_source || a.utm_campaign || a.utm_content || a.referrer || a.landing_page || a.fbclid;
  return (
    <>
      <dt>Звідки прийшла людина</dt>
      <dd>
        {has ? (
          <>
            {a.utm_source && <div>Джерело: <b>{a.utm_source}</b>{a.utm_medium ? ` / ${a.utm_medium}` : ""}</div>}
            {a.utm_campaign && <div>Кампанія: {a.utm_campaign}</div>}
            {a.utm_content && <div>Оголошення (utm_content): {a.utm_content}</div>}
            {a.utm_term && <div>Ключ (utm_term): {a.utm_term}</div>}
            {a.fbclid && <div>З реклами Meta (є fbclid)</div>}
            {a.referrer && <div>Перейшов із: {a.referrer}</div>}
            {a.landing_page && <div>Перша сторінка: {a.landing_page}</div>}
          </>
        ) : "невідомо (прямий захід або UTM не передано)"}
      </dd>
    </>
  );
}
