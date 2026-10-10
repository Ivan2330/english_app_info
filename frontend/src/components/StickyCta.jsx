import { useNavigate } from "react-router-dom";

/**
 * Липка панель унизу екрана — тільки на мобільному.
 * На довгих сторінках кнопка запису інакше залишається десь угорі,
 * і людині доводиться скролити назад.
 */
export default function StickyCta() {
  const navigate = useNavigate();

  return (
    <div className="mcta">
      <button type="button" className="btn btn-ghost" onClick={() => navigate("/packages")}>
        Ціни
      </button>
      <button type="button" className="btn btn-cta" onClick={() => navigate("/contacts")}>
        Пробний урок
      </button>
    </div>
  );
}
