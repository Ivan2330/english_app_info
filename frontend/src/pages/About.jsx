import main_logo from "../assets/icons/logo.svg";

export default function About() {
  return (
    <section className="about" aria-labelledby="about-title">
      <div className="container about__inner">
        {/* Hero/Intro */}
        <header className="about__hero">
          <p className="kicker">About Prime Academy</p>
          <h1 id="about-title" className="about__title">
            Місія — зробити англійську вашим щоденним інструментом
          </h1>
          <p className="about__lead">
            Ми навчаємо дітей і дорослих говорити впевнено: розмовний фокус,
            чіткі цілі та вимірюваний прогрес. Якщо результату немає — ми
            продовжуємо навчання <strong>безкоштовно</strong>.
          </p>
        </header>

        {/* Brand Medallion */}
        <section
          className="about__brand"
          aria-label="Філософія та цінності Prime Academy"
        >
          <div className="about__brand-logo" aria-hidden="true">
            <img src={main_logo} alt="Prime Academy" />
          </div>

          <h2 className="about__brand-title">
            Школа, де англійська звучить щодня
          </h2>

          <p className="about__brand-text">
            Успіх приходить із щоденної практики. Тому наші уроки — це живе
            спілкування, чітка структура й підтримка викладача, який бачить ваш
            прогрес і підлаштовує темп під вашу мету.
          </p>

          <div className="about__brand-tags" role="list" aria-label="Наші цінності">
            <span role="listitem">Speaking-first</span>
            <span role="listitem">CEFR roadmap</span>
            <span role="listitem">Measurable progress</span>
            <span role="listitem">Result guarantee</span>
          </div>
        </section>

        {/* Student Path (Timeline) */}
        <section className="about__steps" aria-label="Шлях студента в Prime Academy">
          <h2 className="about__steps-title">Шлях студента</h2>
          <p className="about__steps-lead">
            Від діагностики — до вимірюваного результату за CEFR. Чітко, прозоро, без хаосу.
          </p>

          <ol className="about__steps-list">
            <li className="about__step">
              <div className="about__step-icon">🧭</div>
              <h3>Діагностика</h3>
              <p>Тест + розмова, щоб визначити стартовий рівень і потреби.</p>
            </li>

            <li className="about__step">
              <div className="about__step-icon">🎯</div>
              <h3>Цілі</h3>
              <p>Фіксуємо конкретні результати: CEFR-рівень, іспит чи задачі роботи.</p>
            </li>

            <li className="about__step">
              <div className="about__step-icon">🗺️</div>
              <h3>План</h3>
              <p>Особистий маршрут: частота, матеріали, контрольні точки.</p>
            </li>

            <li className="about__step">
              <div className="about__step-icon">💬</div>
              <h3>Живі уроки</h3>
              <p>Speaking-first + «розумна» граматика, без зайвої теорії.</p>
            </li>

            <li className="about__step">
              <div className="about__step-icon">⏱️</div>
              <h3>Практика</h3>
              <p>Домашки, міні-челенджі, щотижневий фідбек і метрики прогресу.</p>
            </li>

            <li className="about__step">
              <div className="about__step-icon">🏆</div>
              <h3>Сертифікат / Результат</h3>
              <p>Підтвердження за CEFR і видимий апґрейд у реальних ситуаціях.</p>
            </li>
          </ol>
        </section>

        {/* 2-col content */}
        <div className="about__grid">
          <article className="about__card">
            <h3>Підхід</h3>
            <ul className="about__list">
              <li>Діагностика рівня та постановка персональних цілей</li>
              <li>Комунікативна методика + системна граматика</li>
              <li>Щотижневий прогрес-звіт і домашні завдання</li>
              <li>Гнучкий графік: індивідуально чи групи</li>
            </ul>
          </article>

          <article className="about__card">
            <h3>Викладачі</h3>
            <p>
              Наша команда — сертифіковані викладачі з реальним досвідом
              підготовки до <strong>IELTS/TOEFL</strong> та корпоративного
              навчання.
            </p>
            <div className="about__badges" aria-label="Сертифікації">
              <span className="badge">IELTS</span>
              <span className="badge">CEFR</span>
              <span className="badge">DELTA</span>
            </div>
          </article>

          <article className="about__card">
            <h3>Сертифікати</h3>
            <p>
              Після завершення курсу ви отримуєте офіційний сертифікат{" "}
              <strong>Prime Academy</strong> з унікальним кодом перевірки. Він
              підтверджує рівень за міжнародною шкалою <strong>CEFR</strong> і
              може стати перевагою при вступі або працевлаштуванні.
            </p>
            <p>
              Усі сертифікати зберігаються в нашій базі: їх легко перевірити
              онлайн на сторінці <em>«Перевірити сертифікат»</em>.
            </p>
          </article>

          <article className="about__card">
            <h3>Гарантія результату</h3>
            <p>
              Якщо ви дотримуєтесь плану, але не досягаєте цілей — ми
              продовжуємо навчання безкоштовно до потрібного рівня.
            </p>
            <ul className="about__list">
              <li>Прозорі метрики прогресу</li>
              <li>Регулярні фідбеки від викладача</li>
              <li>Доступ до матеріалів і записів</li>
            </ul>
          </article>
        </div>

        {/* Guarantee banner */}
        <aside className="about__guarantee" aria-label="Гарантія та показники">
          <div className="about__g-content">
            <h3>Гарантія результату</h3>
            <p>
              Не бачите прогресу? Продовжуємо навчання безкоштовно — доки не
              досягнемо мети разом.
            </p>
          </div>
          <div className="about__g-stats">
            <div>
              <strong>500+</strong>
              <span>випускників</span>
            </div>
            <div>
              <strong>95%</strong>
              <span>складають іспит з 1-го разу</span>
            </div>
            <div>
              <strong>4.7/5</strong>
              <span>середня оцінка</span>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
