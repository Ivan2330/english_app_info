import { NavLink, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime_logo2.svg";
import "./navbar.css"; // якщо стилі в окремому файлі

export default function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  // Закривати меню при ресайзі на десктоп
  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 880) setOpen(false);
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
    <header className={`navbar ${open ? "navbar--open" : ""}`}>
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
          <NavLink to="/packages" className="navlink">Пакети</NavLink>
          <NavLink to="/about" className="navlink">Про нас</NavLink>
          <NavLink to="/verify-certificate" className="navlink">Сертифікат</NavLink>
          <NavLink to="/contacts" className="navlink">Контакти</NavLink>
        </nav>

        {/* Правий блок: CTA завжди видимий + бургер на мобайлі */}
        <div className="navbar__cta">
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
          <button className="mobileNav__item" onClick={() => go("/packages")}>Пакети</button>
          <button className="mobileNav__item" onClick={() => go("/about")}>Про нас</button>
          <button className="mobileNav__item" onClick={() => go("/verify-certificate")}>Сертифікат</button>
          <button className="mobileNav__item" onClick={() => go("/contacts")}>Контакти</button>
        </div>
      </div>

      <div className="navbar__border" aria-hidden="true" />
    </header>
  );
}
