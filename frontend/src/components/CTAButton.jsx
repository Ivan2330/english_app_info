import React from "react";

/**
 * Універсальна кнопка CTA з приглушеним дефолт-станом і яскравим hover.
 * Використання:
 * <CTAButton onClick={...} />        // розмір md (за замовчуванням)
 * <CTAButton size="sm" />            // компактний розмір (для хедера/футера)
 * <CTAButton className="my-extra" /> // додаткові класи за потреби
 */
export default function CTAButton({
  label = "Пробний урок",
  onClick,
  className = "",
  size = "md", // "sm" | "md"
  type = "button",
}) {
  const sizeClass = size === "sm" ? "btn--sm" : "";

  return (
    <button
      type={type}
      onClick={onClick}
      className={`btn btn-cta ${sizeClass} ${className}`.trim()}
    >
      {label}
    </button>
  );
}
