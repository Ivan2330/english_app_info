import { NavLink, useNavigate } from "react-router-dom";
import CTAButton from "./CTAButton";
import logo from "../assets/icons/prime_logo2.svg";

export default function Navbar() {
  const navigate = useNavigate();

  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <button
          className="navbar__brand"
          onClick={() => navigate("/")}
          aria-label="Prime Academy — на головну"
        >
          <img src={logo} alt="" className="navbar__logo" />
          <span className="navbar__title">Prime Academy</span>
        </button>

        <nav className="navbar__nav" aria-label="Головна навігація">
          <NavLink to="/packages" className="navlink">Пакети</NavLink>
          <NavLink to="/about" className="navlink">Про нас</NavLink>
          <NavLink to="/verify-certificate" className="navlink">Сертифікат</NavLink>
          <NavLink to="/contacts" className="navlink">Контакти</NavLink>
        </nav>

        <div className="navbar__cta">
          {/* Компактна приглушена кнопка */}
          <CTAButton
            size="sm"
            label="Пробний урок"
            onClick={() => navigate("/contacts")}
          />
        </div>
      </div>

      <div className="navbar__border" aria-hidden="true" />
    </header>
  );
}
