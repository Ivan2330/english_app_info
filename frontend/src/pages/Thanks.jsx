import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { trackLead } from "../lib/analytics.js";
import { SELLER } from "../lib/legal/seller.js";

/**
 * Дякуємо за заявку. Тут спрацьовує подія Lead (Pixel + GA4) з тим самим event_id,
 * що вже пішов у Conversions API з сервера. Подія раз на заявку: якщо людина
 * оновить сторінку, дубля не буде (див. trackLead). Без event_id (пряме відкриття
 * сторінки) подія не шлеться взагалі.
 */
export default function Thanks() {
  const { state } = useLocation();
  const eventId = state?.eventId;

  useEffect(() => { trackLead(eventId); }, [eventId]);

  return (
    <section className="section thanks">
      <div className="container thanks__box card">
        <span className="thanks__icon" aria-hidden="true">✓</span>
        <h1 className="section-title">Заявку прийнято!</h1>
        <p className="thanks__lead"><b>Ми напишемо вам протягом 15 хвилин у робочий час</b> і домовимось про зручний час пробного уроку.</p>
        <ol className="thanks__steps">
          <li>Дочекайтесь повідомлення від нас у месенджері чи дзвінка.</li>
          <li>Оберемо час для 40-хвилинного пробного уроку.</li>
          <li>Підключитесь по відео з телефона чи комп'ютера, нічого встановлювати не треба.</li>
        </ol>
        <p className="thanks__alt">
          Хочете швидше? Напишіть нам: <a href={`tel:${SELLER.phone.replace(/[^\d+]/g, "")}`}>{SELLER.phone}</a>
          {" або "}<a href="https://instagram.com/___prime_academy__" target="_blank" rel="noopener noreferrer">в Instagram</a>.
        </p>
        <div className="thanks__actions">
          <Link to="/level-test" className="btn btn-ghost">Поки що перевірити рівень</Link>
          <Link to="/packages" className="btn btn-ghost">Подивитись ціни</Link>
        </div>
      </div>
    </section>
  );
}
