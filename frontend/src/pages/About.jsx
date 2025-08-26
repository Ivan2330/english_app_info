export default function About() {
  return (
    <section className="about">
      <div className="container about__inner">
        {/* Hero/Intro */}
        <header className="about__hero">
          <p className="kicker">About Prime Academy</p>
          <h1 className="about__title">Місія — зробити англійську вашим щоденним інструментом</h1>
          <p className="about__lead">
            Ми навчаємо дітей і дорослих говорити впевнено: розмовний фокус, чіткі цілі та вимірюваний прогрес.
            Якщо результату немає — ми продовжуємо навчання <strong>безкоштовно</strong>.
          </p>
        </header>

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
              Наша команда — сертифіковані викладачі із реальним
              досвідом підготовки до <strong>IELTS/TOEFL</strong> і корпоративного навчання.
            </p>
            <div className="about__badges">
              <span className="badge">IELTS</span>
              <span className="badge">DELTA</span>
              <span className="badge">CERF</span>
            </div>
          </article>

        <article className="about__card">
            <h3>Сертифікати</h3>
            <p>
              Після успішного завершення курсу ви отримуєте офіційний сертифікат{" "}
              <strong>Prime Academy</strong> із унікальним кодом перевірки.
              Він підтверджує ваш рівень за міжнародною шкалою <strong>CEFR</strong>
              та може стати вагомою перевагою при вступі до університетів чи працевлаштуванні.
              Усі сертифікати зберігаються в нашій базі — їх легко перевірити онлайн на сторінці{" "}
              <em>“Перевірити сертифікат”</em>.
            </p>
            <p>
              Ми пишаємося тим, що документи Prime Academy визнають у багатьох міжнародних компаніях та освітніх програмах.
            </p>
          </article>

          <article className="about__card">
            <h3>Гарантія результату</h3>
            <p>
              Якщо ви дотримуєтесь плану, але не досягаєте цілей — ми продовжуємо навчання безкоштовно до потрібного рівня.
            </p>
            <ul className="about__list">
              <li>Прозорі метрики прогресу</li>
              <li>Регулярні фідбеки від викладача</li>
              <li>Доступ до матеріалів і записів</li>
            </ul>
          </article>
        </div>

        {/* Guarantee banner */}
        <aside className="about__guarantee">
          <div className="about__g-content">
            <h3>Гарантія результату</h3>
            <p>Не бачите прогресу? Продовжуємо навчання безкоштовно — доки не досягнемо мети разом.</p>
          </div>
          <div className="about__g-stats">
            <div><strong>1000+</strong><span>випускників</span></div>
            <div><strong>95%</strong><span>складають іспит з 1-го разу</span></div>
            <div><strong>4.7/5</strong><span>середня оцінка</span></div>
          </div>
        </aside>
      </div>
    </section>
  );
}
