import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalyticsConsent, setAnalyticsConsent } from "../lib/consent.js";

/** Подія, якою футер знову відкриває банер («Налаштування cookie»). */
export const OPEN_COOKIE_SETTINGS = "pa:cookie-settings";

/**
 * Банер cookie з чесним вибором: дві кнопки однакової ваги.
 * Google Analytics і Meta Pixel стартують лише після «Прийняти все».
 * «Лише необхідні» нічого стороннього не вмикає.
 */
export default function CookieBanner() {
  const [open, setOpen] = useState(() => getAnalyticsConsent() === null);

  useEffect(() => {
    const reopen = () => setOpen(true);
    window.addEventListener(OPEN_COOKIE_SETTINGS, reopen);
    return () => window.removeEventListener(OPEN_COOKIE_SETTINGS, reopen);
  }, []);

  if (!open) return null;

  function choose(allow) {
    setAnalyticsConsent(allow);
    setOpen(false);
  }

  return (
    <div className="cookie" role="dialog" aria-label="Налаштування cookie" data-testid="cookie-banner">
      <p className="cookie__text">
        Ми використовуємо cookie, щоб сайт працював, і, якщо ви дозволите, аналітичні та рекламні
        cookie (Google Analytics, Meta Pixel), щоб розуміти, що корисне, і показувати нашу рекламу тим,
        кому вона може бути цікава.{" "}
        <Link to="/privacy#p6">Детальніше в Політиці конфіденційності</Link>
      </p>
      <div className="cookie__actions">
        <button type="button" className="btn btn-ghost" onClick={() => choose(false)}>Лише необхідні</button>
        <button type="button" className="btn btn-cta" onClick={() => choose(true)}>Прийняти все</button>
      </div>
    </div>
  );
}
