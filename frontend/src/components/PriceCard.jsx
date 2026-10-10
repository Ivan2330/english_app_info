import { money, lessonsWord, FORMAT } from "../lib/labels.js";

/**
 * Картка пакета. Використовується для тематичних курсів, Speaking Club
 * і корпоративних позицій — тобто скрізь, де показуємо готовий продукт,
 * а не результат роботи конструктора.
 *
 * Раніше картка малювала бейдж Standard/Premium. Тарифних рівнів більше немає:
 * тепер вона показує напрям, формат і — для курсів під іспит — стартовий рівень.
 */
export default function PriceCard({ pkg, onSelect }) {
  if (!pkg) return null;

  const {
    name,
    short_description,
    lessons_count,
    lesson_duration_min,
    group_size_max,
    level_from,
    level_target,
    duration_hint,
    validity_days,
    total_price,
    price_per_lesson,
    not_true_price,
    discount_percent,
    price_per_person,
    currency = "UAH",
    is_popular,
    format,
    chast_enabled,
    chast_max_parts,
  } = pkg;

  const hasDiscount = Boolean(discount_percent && not_true_price);

  return (
    <article className={`price-card${is_popular ? " is-popular" : ""}`}>
      {is_popular ? <div className="price-card__badge">Найчастіше обирають</div> : null}
      {hasDiscount ? <div className="discount">-{discount_percent}%</div> : null}

      {level_from ? (
        <div className="level-row">
          <span className="level-from">{level_from}</span>
          <span className="level-arrow" aria-hidden="true">→</span>
          <span className="level-to">{level_target}</span>
        </div>
      ) : null}

      <h3 className="price-card__title">{name}</h3>
      {short_description ? <p className="price-card__desc">{short_description}</p> : null}

      <div className="price">
        {hasDiscount ? (
          <div className="price__old">{money(not_true_price, currency)}</div>
        ) : null}
        <div className="price__current">{money(total_price, currency)}</div>
        {price_per_lesson ? (
          <div className="price__perlesson">
            {money(price_per_lesson, currency)} за урок
            {price_per_person ? " з людини" : ""}
          </div>
        ) : null}
      </div>

      {pkg.family === "course" && (
        <a className="price-card__benefits" href="#benefits">Ще −20% кожному за друга</a>
      )}

      <ul className="features-list" aria-label="Деталі пакета">
        {lessons_count ? (
          <li>
            <strong>{lessons_count}</strong> {lessonsWord(lessons_count)}
            {lesson_duration_min ? ` по ${lesson_duration_min} хв` : ""}
          </li>
        ) : null}
        {group_size_max && format === "group" ? (
          <li>Група до <strong>{group_size_max}</strong> людей</li>
        ) : null}
        {format && FORMAT[format] ? <li>{FORMAT[format].label}</li> : null}
        {duration_hint ? <li>Триває {duration_hint}</li> : null}
        {/* Термін дії — те, чим ми кращі за ринок на кожній сходинці */}
        {validity_days ? <li>Діє <strong>{validity_days} днів</strong> від першого заняття</li> : null}
      </ul>

      {chast_enabled ? (
        <div className="chast-note">
          Можна частинами — до {chast_max_parts} платежів без переплати
        </div>
      ) : null}

      <button type="button" className="btn btn-cta price-card__cta" onClick={onSelect}>
        Обрати
      </button>
    </article>
  );
}
