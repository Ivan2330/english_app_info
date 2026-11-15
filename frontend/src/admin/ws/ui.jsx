// Дрібні спільні шматки інтерфейсу робочого простору.
import { createContext, useEffect } from "react";
import { createPortal } from "react-dom";

/** Поточний адмін (/api/admin/me): імʼя, роль, розділи, ліміти. */
export const AdminContext = createContext(null);

export function fmtDate(iso, withTime = false) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleString("uk-UA", withTime
    ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }
    : { day: "numeric", month: "long", year: "numeric" });
}

export function fmtSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  return `${(bytes / 1024 ** 3).toFixed(1)} ГБ`;
}

/** Підказка під полем: що сюди писати і навіщо. */
export function Hint({ children }) {
  return <p className="ws-hint">{children}</p>;
}

export function Field({ label, hint, children }) {
  return (
    <label className="ws-field">
      <span className="ws-field__label">{label}</span>
      {children}
      {hint && <Hint>{hint}</Hint>}
    </label>
  );
}

export function ErrorBox({ text }) {
  if (!text) return null;
  return <p className="ws-error" role="alert">{text}</p>;
}

/** Вікно поверх сторінки. На телефоні — на весь екран. Esc закриває.
 *  Рендериться порталом у body: інакше липка верхня панель на телефоні
 *  опинялась над вікном і перекривала кнопку «Закрити». */
export function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.classList.add("ws-modal-open");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("ws-modal-open");
    };
  }, [onClose]);

  return createPortal(
    <div className="ws-modal" role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div className={`ws-modal__box${wide ? " is-wide" : ""}`}>
        <header className="ws-modal__head">
          <h2>{title}</h2>
          <button type="button" className="ws-btn ws-btn--ghost" onClick={onClose}>Закрити</button>
        </header>
        <div className="ws-modal__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

export function Empty({ title, children }) {
  return (
    <div className="ws-empty">
      <b>{title}</b>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Tags({ tags }) {
  if (!tags?.length) return null;
  return <span className="ws-tags">{tags.map((t) => <span key={t} className="ws-tag">#{t}</span>)}</span>;
}

/** Поле тегів: пишеш через кому, бачиш чіпи. */
export function TagsInput({ value, onChange }) {
  return (
    <input
      className="ws-input"
      value={value.join(", ")}
      placeholder="наприклад: reels, реклама"
      onChange={(e) => onChange(e.target.value.split(",").map((t) => t.trim()).filter(Boolean))}
    />
  );
}
