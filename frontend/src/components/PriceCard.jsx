function formatCurrency(v, currency = "UAH") {
  if (v == null) return null;
  try {
    return new Intl.NumberFormat("uk-UA", { style: "currency", currency }).format(v);
  } catch {
    return `${v} ${currency}`;
  }
}

export default function PriceCard({
  title,
  type,               // "standard" | "premium"
  oldPrice,           // not_true_price
  totalPrice,         // total_price or base_price
  pricePerLesson,     // price_per_lesson
  discountPercent,    // discount_percent
  discountMoney,      // discount_money
  lessonsCount,
  lessonDuration,
  currency = "UAH",
  onSelect,
}) {
  const isPremium = type === "premium";
  const hasDiscount = Boolean(discountPercent || discountMoney || oldPrice);

  return (
    <article className={`price-card ${isPremium ? "is-premium" : ""}`}>
      {hasDiscount && (
        <div className="discount">
          {discountPercent ? `-${discountPercent}%` : discountMoney ? `-${formatCurrency(discountMoney, currency)}` : "Знижка"}
        </div>
      )}

      <div className="price-card__head">
        <h3 className="price-card__title">{title}</h3>
        <span className={`badge ${isPremium ? "badge--premium" : ""}`}>
          {isPremium ? "Premium" : "Standard"}
        </span>
      </div>

      <div className="price">
        {oldPrice ? <div className="price__old">{formatCurrency(oldPrice, currency)}</div> : null}
        <div className="price__current">{formatCurrency(totalPrice, currency)}</div>
        {pricePerLesson ? (
          <div className="price__perlesson">/ {formatCurrency(pricePerLesson, currency)} за урок</div>
        ) : null}
      </div>

      <ul className="features-list" aria-label="Що входить у пакет">
        {lessonsCount ? <li>Уроків у пакеті: <strong>{lessonsCount}</strong></li> : null}
        {lessonDuration ? <li>Тривалість одного уроку: <strong>{lessonDuration} хв</strong></li> : null}
        <li>Гарантія результату</li>
        <li>Індивідуальний план та домашні завдання</li>
      </ul>

      <div className="price-card__footer">
        <div className="guarantee">Не буде прогресу — навчаємо безкоштовно</div>
        <button className="btn btn-primary price-card__cta" onClick={onSelect}>Обрати пакет</button>
      </div>
    </article>
  );
}
