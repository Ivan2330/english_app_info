import { NavLink, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime_logo2.svg";

export default function Navbar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  // Закривати меню при зміні маршруту / ресайзі
  useEffect(() => {
    const closeOnResize = () => {
      if (window.innerWidth >= 880) setOpen(false);
    };
    window.addEventListener("resize", closeOnResize);
    return () => window.removeEventListener("resize", closeOnResize);
  }, []);

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

        {/* Десктопна навігація */}
        <nav className="navbar__nav" aria-label="Головна навігація">
          <NavLink to="/packages" className="navlink">Пакети</NavLink>
          <NavLink to="/about" className="navlink">Про нас</NavLink>
          <NavLink to="/verify-certificate" className="navlink">Сертифікат</NavLink>
          <NavLink to="/contacts" className="navlink">Контакти</NavLink>
        </nav>

        <div className="navbar__cta">
          <CTAButton size="sm" label="Пробний урок" onClick={() => go("/contacts")} />
          {/* Кнопка меню лише на мобільних */}
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

      {/* Мобільне меню (slide-down) */}
      <div id="mobile-nav" className="mobileNav" aria-hidden={!open}>
        <div className="mobileNav__inner">
          <button className="mobileNav__item" onClick={() => go("/packages")}>Пакети</button>
          <button className="mobileNav__item" onClick={() => go("/about")}>Про нас</button>
          <button className="mobileNav__item" onClick={() => go("/verify-certificate")}>Сертифікат</button>
          <button className="mobileNav__item" onClick={() => go("/contacts")}>Контакти</button>
          <div className="mobileNav__cta">
            <CTAButton label="Пробний урок" onClick={() => go("/contacts")} />
          </div>
        </div>
      </div>

      <div className="navbar__border" aria-hidden="true" />
    </header>
  );
}
