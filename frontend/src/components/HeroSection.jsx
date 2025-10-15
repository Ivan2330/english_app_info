import { useNavigate } from "react-router-dom";
import CTAButton from "./CTAButton";

export default function HeroSection() {
  const navigate = useNavigate();

  return (
    <section className="hero">
      <div className="container hero__inner">
        <div className="hero__content">
          <p className="kicker">Online English School</p>
          <h1 className="hero__title">Почни говорити англійською впевнено</h1>
          <p className="hero__subtitle">
            Індивідуальні та групові заняття для дітей і дорослих. Гарантія результату — або
            навчаємо безкоштовно.
          </p>

          <div className="hero__actions">
            {/* Приглушена за замовчуванням → яскрава при hover */}
            <CTAButton
              label="Записатись на пробний урок"
              onClick={() => navigate("/contacts")}
            />

            {/* Додаткова вторинна дія лишається ghost */}
            <button
              className="btn btn-ghost"
              onClick={() => navigate("/packages")}
            >
              Переглянути пакети
            </button>
          </div>
        </div>
      </div>

      {/* декоративна фіолетова лінія внизу героя */}
      <div className="accent-bar" aria-hidden="true" />
    </section>
  );
}
