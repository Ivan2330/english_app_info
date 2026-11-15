import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/** Сторінки, де людина вже заповнює форму чи оплачує: липка панель там лише заважає
 *  (раніше вона перекривала кнопку відправки й поля чекаута). */
const HIDDEN_ON = ["/trial", "/thanks", "/contacts", "/checkout", "/payment/result", "/admin"];

/**
 * Липка панель унизу екрана — тільки на мобільному.
 * На довгих сторінках кнопка запису інакше залишається десь угорі,
 * і людині доводиться скролити назад.
 *
 * На головній, поки на екрані форма запису (перший екран), панель ховається:
 * вона дублювала б форму й накривала її кнопку.
 */
export default function StickyCta() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [heroFormVisible, setHeroFormVisible] = useState(pathname === "/");

  useEffect(() => {
    if (pathname !== "/") { setHeroFormVisible(false); return undefined; }
    const el = document.querySelector(".hero__form");
    if (!el || !("IntersectionObserver" in window)) { setHeroFormVisible(false); return undefined; }
    setHeroFormVisible(true);
    const io = new IntersectionObserver(([entry]) => setHeroFormVisible(entry.isIntersecting), { threshold: 0.2 });
    io.observe(el);
    return () => io.disconnect();
  }, [pathname]);

  if (HIDDEN_ON.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return null;
  if (heroFormVisible) return null;

  return (
    <div className="mcta">
      <button type="button" className="btn btn-ghost" onClick={() => navigate("/packages")}>
        Ціни
      </button>
      <button type="button" className="btn btn-cta" onClick={() => navigate("/trial")}>
        Пробний урок
      </button>
    </div>
  );
}
