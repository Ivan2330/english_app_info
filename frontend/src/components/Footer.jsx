import { NavLink } from "react-router-dom";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime_logo2.svg";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__top">
        {/* Бренд */}
        <div className="footer__brand">
          <img src={logo} alt="Prime Academy" className="footer__logo" />
          <p className="footer__tagline">
            Онлайн школа англійської з гарантією результату.
            Індивідуальні та групові заняття для дітей і дорослих.
          </p>
        </div>

        {/* Навігація */}
        <nav className="footer__nav" aria-label="Посилання у футері">
          <h4>Навігація</h4>
          <ul>
            <li><NavLink to="/packages">Пакети</NavLink></li>
            <li><NavLink to="/about">Про нас</NavLink></li>
            <li><NavLink to="/verify-certificate">Перевірити сертифікат</NavLink></li>
            <li><NavLink to="/contacts">Контакти</NavLink></li>
          </ul>
        </nav>

        {/* Контакти */}
        <div className="footer__contacts">
          <h4>Звʼязок</h4>
          <ul>
            <li><a href="tel:+380991797047">+38 (099) 179-70-47</a></li>
            <li><a href="mailto:my.primeacademy19@gmail.com">my.primeacademy19@gmail.com</a></li>
            <li>
              <a
                href="https://t.me/IvanKozhevnyk"
                target="_blank"
                rel="noreferrer"
              >
                Telegram
              </a>
            </li>
          </ul>

          {/* Кнопка: приглушена за замовчуванням */}
          <NavLink to="/contacts">
            <CTAButton size="sm" label="Записатись на пробний урок" />
          </NavLink>
        </div>
      </div>

      <div className="footer__bottom">
        <div className="container">
          <p>© {new Date().getFullYear()} Prime Academy. Всі права захищено.</p>
        </div>
      </div>
    </footer>
  );
}
