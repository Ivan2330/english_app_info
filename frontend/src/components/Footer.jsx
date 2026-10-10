import { NavLink } from "react-router-dom";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime_logo2.svg";
import { PLATFORM_URL, ADMIN_PATH } from "../config.js";

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__top">
        {/* Бренд */}
        <div className="footer__brand">
          <img src={logo} alt="Prime Academy" className="footer__logo" />
          <p className="footer__tagline">
            Онлайн школа англійської мови. Індивідуальні заняття, уроки в парі
            та міні-групи до 6 людей — для дітей, підлітків і дорослих.
          </p>
        </div>

        {/* Навігація */}
        <nav className="footer__nav" aria-label="Посилання у футері">
          <h4>Навігація</h4>
          <ul>
            <li><NavLink to="/programs">Програми</NavLink></li>
            <li><NavLink to="/packages">Ціни та пакети</NavLink></li>
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
            {/* Instagram замість особистого Telegram (30.09.2026).
                Основний трафік іде саме звідти, а зворотного посилання
                з сайту не було: людина, яка прийшла з reels подивитись
                сторіс чи відгуки, не мала куди повернутись.

                Особистий профіль власника прибрано свідомо — для школи
                потрібен загальний контакт, а не приватний акаунт. */}
            <li>
              <a href="https://instagram.com/___prime_academy__"
                 target="_blank" rel="noreferrer noopener">
                Instagram
              </a>
            </li>
          </ul>

          {/* Вхід на платформу — для тих, хто вже вчиться.
              Окремий продукт на іншому домені, тому звичайне посилання. */}
          <a
            className="footer__platform"
            href={PLATFORM_URL}
            target="_blank"
            rel="noreferrer"
          >
            <span aria-hidden="true">↗</span> Кабінет учня
          </a>

          <NavLink to="/contacts">
            <CTAButton size="sm" label="Записатись на пробний урок" />
          </NavLink>
        </div>
      </div>

      <div className="footer__bottom">
        <div className="container footer__bottom-row">
          <p>© {new Date().getFullYear()} Prime Academy. Всі права захищено.</p>

          {/* ОБОВ'ЯЗКОВИЙ рядок, не прибирати.
              Шрифт e-Ukraine поширюється за ліцензією CC BY 4.0: комерційне
              використання дозволене, але зазначення авторства — умова ліцензії.
              Без цього рядка ми користуємося шрифтом неправомірно. */}
          <p className="footer__font">
            Шрифт{" "}
            <a href="https://thedigital.gov.ua/fonts" target="_blank" rel="noreferrer noopener">
              e-Ukraine
            </a>{" "}
            — Міністерство цифрової трансформації України,{" "}
            <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer noopener">
              CC BY 4.0
            </a>
          </p>

          {/* Юридичні документи мають бути доступні з будь-якої сторінки —
              цього вимагають і платіжні сервіси, і здоровий глузд. */}
          {/* Окремі посилання на умови оплати, повернення й реквізити.
              Усе це є в оферті, але розділами 4, 11 і блоком «Реквізити» —
              перевіряльник еквайрингу не зобовʼязаний читати договір цілком,
              щоб переконатися, що вони на сайті є. Прямі якорі економлять
              йому хвилини, а нам — питання у відповіді. */}
          <nav className="footer__legal" aria-label="Юридичні документи">
            <NavLink to="/offer">Публічна оферта</NavLink>
            <NavLink to="/offer#p4">Умови оплати</NavLink>
            <NavLink to="/offer#p11">Повернення коштів</NavLink>
            <NavLink to="/offer#requisites">Реквізити</NavLink>
            <NavLink to="/privacy">Конфіденційність</NavLink>
          </nav>

          {/* Вхід для менеджера. Свідомо непомітний: це службове посилання,
              а не елемент навігації для відвідувача. У robots.txt /admin
              закритий від індексації. */}
          <a className="footer__staff" href={ADMIN_PATH}>
            Вхід для персоналу
          </a>
        </div>
      </div>
    </footer>
  );
}
