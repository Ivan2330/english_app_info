import { useTilt } from "../lib/motion.js";

/**
 * Кольорова картка з градієнтом і 3D-нахилом за курсором.
 * Один компонент на три місця: напрямки, формати навчання, принципи.
 *
 * tone задає градієнт: violet | coral | cyan | ink | lime
 */
export default function TileCard({ tone = "violet", icon, title, text, points, meta, onClick }) {
  const ref = useTilt();
  const Tag = onClick ? "button" : "article";

  return (
    <Tag
      ref={ref}
      className={`tile tile--${tone}${onClick ? " tile--clickable" : ""}`}
      onClick={onClick}
      type={onClick ? "button" : undefined}
    >
      {icon ? <span className="tile__icon" aria-hidden="true">{icon}</span> : null}

      <h3 className="tile__title">
        {String(title).split("\n").map((line, i) => (
          <span key={i}>{line}</span>
        ))}
      </h3>

      {text ? <p className="tile__text">{text}</p> : null}

      {points?.length ? (
        <ul className="tile__points">
          {points.map((p) => <li key={p}>{p}</li>)}
        </ul>
      ) : null}

      {meta ? (
        <div className="tile__foot">
          <span>{meta}</span>
          {onClick ? <span className="tile__arrow" aria-hidden="true">↗</span> : null}
        </div>
      ) : null}
    </Tag>
  );
}
