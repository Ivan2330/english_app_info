import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PackageTabs from "./PackageTabs.jsx";
import { fetchPackages } from "../api/packages.js";
import { AUDIENCE, FORMAT, TRACK, money, lessonsWord } from "../lib/labels.js";

const AUDIENCE_ORDER = ["adults", "teens", "kids"];
const TRACK_ORDER = ["general", "speaking", "school"];
const FORMAT_ORDER = ["individual", "pair", "group"];

/**
 * Конструктор абонемента: аудиторія → напрям → формат → розмір пакета.
 *
 * Чотири кроки замість колишніх п'яти — крок «рівень супроводу»
 * (Standard / Premium) прибрано разом із самим тарифним рівнем.
 *
 * Розміри пакетів показані слайдером, а не десятьма картками поруч:
 * десять цін в один ряд читаються як шум, а повзунок дає відчуття вибору.
 */
export default function PackageBuilder({ combos, onSelect }) {
  const navigate = useNavigate();
  const [audience, setAudience] = useState("adults");
  const [track, setTrack] = useState("general");
  const [format, setFormat] = useState("individual");
  const [idx, setIdx] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  // Тільки абонементи: курси мають фіксовану довжину, їм слайдер не потрібен.
  const subs = useMemo(() => combos.filter((c) => c.family === "subscription"), [combos]);

  const tracks = useMemo(
    () => TRACK_ORDER.filter((t) => subs.some((c) => c.audience === audience && c.track === t)),
    [subs, audience]
  );

  const formats = useMemo(
    () =>
      FORMAT_ORDER.filter((f) =>
        subs.some((c) => c.audience === audience && c.track === track && c.format === f)
      ),
    [subs, audience, track]
  );

  // Якщо після зміни аудиторії поточний напрям/формат став недоступним —
  // мовчки переводимо на перший доступний, а не показуємо порожній екран.
  useEffect(() => {
    if (tracks.length && !tracks.includes(track)) setTrack(tracks[0]);
  }, [tracks, track]);

  useEffect(() => {
    if (formats.length && !formats.includes(format)) setFormat(formats[0]);
  }, [formats, format]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPackages({ family: "subscription", audience, track, format })
      .then((data) => {
        if (cancelled) return;
        const sorted = [...data].sort((a, b) => a.lessons_count - b.lessons_count);
        setItems(sorted);
        setIdx((prev) => Math.min(prev, Math.max(sorted.length - 1, 0)));
      })
      .catch(() => !cancelled && setItems([]))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [audience, track, format]);

  const current = items[idx] ?? null;

  const audienceOptions = AUDIENCE_ORDER.map((a) => ({
    value: a,
    label: AUDIENCE[a].label,
    note: AUDIENCE[a].note,
    disabled: !subs.some((c) => c.audience === a),
  }));

  const trackOptions = TRACK_ORDER.map((t) => ({
    value: t,
    label: TRACK[t].label,
    note: TRACK[t].note,
    disabled: !tracks.includes(t),
  }));

  const formatOptions = FORMAT_ORDER.map((f) => ({
    value: f,
    label: FORMAT[f].label,
    note: FORMAT[f].note,
    disabled: !formats.includes(f),
  }));

  return (
    <div className="builder">
      <div className="builder__steps">
        <Step n={1} title="Для кого" hint="аудиторія">
          <PackageTabs options={audienceOptions} value={audience} onChange={setAudience} ariaLabel="Аудиторія" />
        </Step>

        <Step n={2} title="Напрям" hint="що вивчаємо">
          <PackageTabs options={trackOptions} value={track} onChange={setTrack} ariaLabel="Напрям" />
        </Step>

        <Step n={3} title="Формат" hint="як вчимося">
          <PackageTabs options={formatOptions} value={format} onChange={setFormat} ariaLabel="Формат" />
        </Step>

        <Step n={4} title="Розмір пакета" hint="уроків">
          {items.length > 0 ? (
            <>
              <input
                type="range"
                className="pk-slider"
                min={0}
                max={items.length - 1}
                step={1}
                value={idx}
                onChange={(e) => setIdx(Number(e.target.value))}
                aria-label="Розмір пакета"
              />
              <div className="ladder">
                {items.map((p, i) => (
                  <button
                    key={p.id}
                    type="button"
                    className={`ladder__item${i === idx ? " is-active" : ""}`}
                    onClick={() => setIdx(i)}
                  >
                    {p.lessons_count}
                  </button>
                ))}
              </div>
              <p className="builder__hint">
                Потягніть повзунок або натисніть на число. Чим більший пакет — тим нижча ціна за урок.
              </p>
            </>
          ) : (
            <p className="builder__hint">{loading ? "Завантаження…" : "Для цієї комбінації пакетів немає."}</p>
          )}
        </Step>
      </div>

      <aside className="builder__summary">
        {current ? (
          <>
            <div className="summary__eyebrow">
              {TRACK[current.track]?.label} · {FORMAT[current.format]?.label}
            </div>

            <div className="summary__price">{money(current.total_price, current.currency)}</div>

            {current.discount_percent ? (
              <div className="summary__old">
                <s>{money(current.not_true_price, current.currency)}</s>
                <span className="summary__disc">-{current.discount_percent}%</span>
              </div>
            ) : null}

            <a className="summary__benefits" href="#benefits">
              Ще −20% кожному за друга · бали за успішність ↓
            </a>

            <div className="summary__grid">
              <Cell label="Уроків" value={`${current.lessons_count} ${lessonsWord(current.lessons_count)}`} />
              <Cell
                label="За урок"
                value={`${money(current.price_per_lesson, current.currency)}${
                  current.price_per_person ? " / особу" : ""
                }`}
              />
              <Cell label="Тривалість уроку" value={`${current.lesson_duration_min} хв`} />
              <Cell label="Вистачить на" value={current.duration_hint || "—"} />
              {current.validity_days ? (
                <Cell label="Діє" value={`${current.validity_days} днів`} />
              ) : null}
            </div>

            {current.group_size_max && current.format === "group" ? (
              <p className="summary__note">Група до {current.group_size_max} людей — удвічі менша, ніж у більшості шкіл.</p>
            ) : null}

            {current.chast_enabled ? (
              <p className="summary__note">
                Можна частинами: {money(Math.round(current.total_price / current.chast_max_parts), current.currency)} ×{" "}
                {current.chast_max_parts} без переплати
              </p>
            ) : null}

            {/* Дві дії замість однієї. Раніше кнопка вела тільки на пробний,
                і людина, готова купити зараз, не мала куди натиснути. */}
            <button type="button" className="btn btn-cta summary__cta" onClick={() => onSelect(current)}>
              Оформити замовлення
            </button>
            <button
              type="button"
              className="btn btn-ghost summary__cta"
              onClick={() => navigate("/contacts")}
            >
              Спершу пробний урок
            </button>
            <p className="summary__fine">Пробний безкоштовний, картка не потрібна</p>
          </>
        ) : (
          <p className="builder__hint">{loading ? "Рахуємо…" : "Оберіть параметри зліва"}</p>
        )}
      </aside>
    </div>
  );
}

function Step({ n, title, hint, children }) {
  return (
    <section className="bstep">
      <header className="bstep__head">
        <span className="bstep__n">{n}</span>
        <h3 className="bstep__title">{title}</h3>
        <span className="bstep__hint">{hint}</span>
      </header>
      {children}
    </section>
  );
}

function Cell({ label, value }) {
  return (
    <div className="summary__cell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
