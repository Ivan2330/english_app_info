/**
 * Універсальний селектор опції для конструктора пакетів.
 *
 * Раніше тут були жорстко зашиті чотири вкладки adults/kids/business/it —
 * і це змішувало різні сутності: business та it не аудиторії, а напрями
 * навчання. Тепер компонент нічого не знає про конкретні значення й просто
 * малює список варіантів, які йому передали.
 */
export default function PackageTabs({
  options,          // [{ value, label, note, disabled }]
  value,
  onChange,
  ariaLabel = "Вибір",
}) {
  return (
    <div className="opt-group" role="tablist" aria-label={ariaLabel}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={o.disabled}
            className={`opt${active ? " is-active" : ""}${o.disabled ? " is-disabled" : ""}`}
            onClick={() => !o.disabled && onChange(o.value)}
          >
            <span className="opt__label">{o.label}</span>
            {o.note ? <span className="opt__note">{o.note}</span> : null}
            {active ? <span className="opt__check" aria-hidden="true">✓</span> : null}
          </button>
        );
      })}
    </div>
  );
}
