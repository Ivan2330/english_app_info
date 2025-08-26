import { useNavigate } from "react-router-dom";
import HeroSection from "../components/HeroSection.jsx";
import StatsBlock from "../components/StatsBlock.jsx";

export default function Home() {
  const navigate = useNavigate();

  return (
    <>
      <HeroSection />
      <StatsBlock />

      <section className="features">
        <div className="container">
          <h2 className="section-title">Чому Prime Academy</h2>

          <ul className="features__grid">
            <li className="feature-card">
              <div className="feature-card__icon" aria-hidden>🗣️</div>
              <h3 className="feature-card__title">Розмовний фокус</h3>
              <p className="feature-card__text">Практика з першого уроку. Мовні патерни та живі діалоги.</p>
            </li>
            <li className="feature-card">
              <div className="feature-card__icon" aria-hidden>🎓</div>
              <h3 className="feature-card__title">Сертифіковані викладачі</h3>
              <p className="feature-card__text">CELTA/DELTA/TEFL, реальний досвід роботи з дітьми й дорослими.</p>
            </li>
            <li className="feature-card">
              <div className="feature-card__icon" aria-hidden>💻</div>
              <h3 className="feature-card__title">Гнучке навчання</h3>
              <p className="feature-card__text">Заняття онлайн у зручний час. Персональний план під цілі.</p>
            </li>
            <li className="feature-card">
              <div className="feature-card__icon" aria-hidden>🏆</div>
              <h3 className="feature-card__title">Гарантія результату</h3>
              <p className="feature-card__text">Не отримуєш прогрес — продовжуємо навчання безкоштовно.</p>
            </li>
          </ul>
        </div>
      </section>

      <section className="cta">
        <div className="container cta__inner">
          <div className="cta__content">
            <h2>Готові стартувати?</h2>
            <p>Залиш заявку на безкоштовний пробний урок — ми підберемо програму та викладача.</p>
          </div>
          <div className="cta__actions">
            <button className="btn btn-primary" onClick={() => navigate("/contacts")}>
              Записатись на пробний урок
            </button>
            <button className="btn btn-ghost" onClick={() => navigate("/packages")}>
              Пакети та ціни
            </button>
          </div>
        </div>
      </section>
    </>
  );
}
