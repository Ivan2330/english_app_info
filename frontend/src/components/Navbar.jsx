import { NavLink, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime-academy-logo.png";
import { PLATFORM_URL } from "../config.js";


export default function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [stuck, setStuck] = useState(false);

  // Скляна «пігулка» стає щільнішою, коли сторінку прокрутили —
  // інакше на світлому фоні текст меню зливається з контентом під ним.
  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Закривати меню при ресайзі на десктоп
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth > 1080) setOpen(false);
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Блокувати скрол сторінки, коли меню відкрите
  useEffect(() => {
    document.documentElement.classList.toggle("body--lock", open);
    return () => document.documentElement.classList.remove("body--lock");
  }, [open]);

  const go = (path) => {
    navigate(path);
    setOpen(false);
  };

  return (
    <header className={`navbar ${open ? "navbar--open" : ""} ${stuck ? "is-stuck" : ""}`.trim()}>
      <div className="container navbar__inner">
        <button
          className="navbar__brand"
          onClick={() => go("/")}
          aria-label="Prime Academy — на головну"
        >
          <img src={logo} alt="" className="navbar__logo" />
          <span className="navbar__title">Prime Academy</span>
        </button>

        {/* Десктоп-меню */}
        <nav className="navbar__nav" aria-label="Головна навігація">
          <NavLink to="/programs" className="navlink">Програми</NavLink>
          <NavLink to="/packages" className="navlink">Ціни</NavLink>
          {/* Тест — джерело заявок, але з меню на нього не було входу:
              знайти сторінку можна було лише випадково, з фіналу
              експрес-тесту або зі шкали рівнів. */}
          <NavLink to="/level-test" className="navlink">Тест рівня</NavLink>
          <NavLink to="/about" className="navlink">Про нас</NavLink>
          <NavLink to="/verify-certificate" className="navlink">Сертифікат</NavLink>
          <NavLink to="/contacts" className="navlink">Контакти</NavLink>
        </nav>

        {/* Правий блок: CTA завжди видимий + бургер на мобайлі */}
        <div className="navbar__cta">
          {/* Вхід у кабінет для тих, хто вже вчиться. Окремий домен,
              тому звичайне посилання, а не роут. */}
          <a
            className="navbar__platform"
            href={PLATFORM_URL}
            target="_blank"
            rel="noreferrer"
          >
            Кабінет учня
          </a>

          <div className="navbar__ctaBtn">
            <CTAButton size="sm" label="Пробний урок" onClick={() => go("/contacts")} />
          </div>

          <button
            className="navbar__menuBtn"
            aria-label={open ? "Закрити меню" : "Відкрити меню"}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((s) => !s)}
          >
            <span className="navbar__menuIcon" />
          </button>
        </div>
      </div>

      {/* Бекдроп поверх контенту */}
      <div className="mobileNav__backdrop" onClick={() => setOpen(false)} />

      {/* Мобільне меню без CTA (щоб не дублювався) */}
      <div id="mobile-nav" className="mobileNav" aria-hidden={!open}>
        <div className="mobileNav__inner">
          <button className="mobileNav__item" onClick={() => go("/programs")}>Програми</button>
          <button className="mobileNav__item" onClick={() => go("/packages")}>Ціни</button>
          <button className="mobileNav__item" onClick={() => go("/level-test")}>Тест рівня</button>
          <button className="mobileNav__item" onClick={() => go("/about")}>Про нас</button>
          <button className="mobileNav__item" onClick={() => go("/verify-certificate")}>Сертифікат</button>
          <button className="mobileNav__item" onClick={() => go("/contacts")}>Контакти</button>
          <a
            className="mobileNav__item mobileNav__item--platform"
            href={PLATFORM_URL}
            target="_blank"
            rel="noreferrer"
            onClick={() => setOpen(false)}
          >
            Кабінет учня ↗
          </a>
        </div>
      </div>

      <div className="navbar__border" aria-hidden="true" />
    </header>
  );
}
