import { useEffect, useState } from "react";
import { fetchPackages } from "../api/packages.js";

/**
 * Бонусні уроки: реальна кількість для кожного розміру пакета.
 *
 * Числа беремо з API (bonus_lessons у пакеті — таблиця в pricing.py),
 * у тексті їх немає: Іван міняє таблицю, сайт іде за нею.
 * Це значення за ПЕРШУ покупку; для наступних умови задаються окремо.
 */
export default function BonusLessons({ id }) {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    let cancelled = false;
    fetchPackages({ family: "subscription", audience: "adults", track: "general", format: "individual" })
      .then((data) => {
        if (cancelled) return;
        setRows(
          data
            .filter((p) => p.bonus_lessons > 0)
            .sort((a, b) => a.lessons_count - b.lessons_count)
        );
      })
      .catch(() => !cancelled && setRows([]));
    return () => { cancelled = true; };
  }, []);

  const max = rows.reduce((m, p) => Math.max(m, p.bonus_lessons), 0);

  return (
    <aside id={id} className="bonus-lessons" aria-label="Бонусні уроки до пакета">
      <div className="bonus-lessons__amount">
        {max ? `До +${max}` : "Бонус"} <span>уроків у подарунок</span>
      </div>
      <div className="bonus-lessons__body">
        <h3>Більше уроків у пакеті — більше бонусних занять</h3>
        <p>
          Бонусні уроки додаються до придбаних, а їхня кількість залежить від розміру пакета
          та від того, скільки пакетів ви вже придбали в школі.
        </p>
        {rows.length > 0 ? (
          <ul className="bonus-lessons__table" aria-label="Бонус за розміром пакета">
            {rows.map((p) => (
              <li key={p.id}>{p.lessons_count} + <b>{p.bonus_lessons}</b></li>
            ))}
          </ul>
        ) : null}
        <p className="bonus-lessons__note">
          Наприклад, «16 + 2» — це 16 оплачених уроків і 2 у подарунок. Вказано для першого пакета.
        </p>
      </div>
    </aside>
  );
}
