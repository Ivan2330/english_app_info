import { useEffect, useState } from "react";
import { LEVELS } from "../lib/content.js";

/**
 * Інтерактивна шкала CEFR: клік по рівню показує, що людина на ньому вміє,
 * скільки часу до наступного і скільки це приблизно годин практики.
 */
export default function LevelScale() {
  const [i, setI] = useState(0);
  const [width, setWidth] = useState(0);
  const lv = LEVELS[i];
  const isLast = i === LEVELS.length - 1;

  // Смужка заповнюється після перемикання, а не стрибає — інакше
  // зміна рівня виглядає як помилка рендеру.
  useEffect(() => {
    setWidth(0);
    const t = setTimeout(() => setWidth(lv.width), 60);
    return () => clearTimeout(t);
  }, [i, lv.width]);

  return (
    <div className="lv">
      <div className="lv__bar" role="tablist" aria-label="Рівні CEFR">
        {LEVELS.map((l, idx) => (
          <button
            key={l.code}
            type="button"
            role="tab"
            aria-selected={idx === i}
            className={`lv__btn${idx === i ? " is-active" : ""}`}
            onClick={() => setI(idx)}
          >
            {l.code}
            <small>{l.sub}</small>
          </button>
        ))}
      </div>

      <div className="lv__body">
        <div className="lv__text" key={lv.code}>
          <h3 className="lv__title">{lv.title}</h3>
          <p className="lv__lead">{lv.text}</p>
          <ul className="lv__can">
            {lv.can.map((c) => (
              <li key={c}><b>✓</b>{c}</li>
            ))}
          </ul>
        </div>

        {/* У рядку під смужкою стояв сам код рівня — і число поруч
            читалося як «годин на A1», тобто як підсумок, а не як крок.
            Тепер видно сам перехід: «A1 → A2 · 50 годин уроків».
            C2 — останній, наступного немає, тому в нього інша шапка
            й немає годин. */}
        <aside className="lv__meter">
          <h4>{isLast ? "Далі" : "До наступного рівня"}</h4>
          <div className="lv__time">{lv.time}</div>
          <div className="lv__track"><i style={{ width: `${width}%` }} /></div>
          <div className="lv__row">
            <span>{isLast ? lv.code : `${lv.code} → ${LEVELS[i + 1].code}`}</span>
            {lv.hours ? <span>{lv.hours}</span> : null}
          </div>
          <a href="/level-test" className="btn btn-lime btn--full">Пройти тест рівня</a>
        </aside>
      </div>
    </div>
  );
}
