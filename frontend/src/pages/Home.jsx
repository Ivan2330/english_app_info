import { useNavigate, Link } from "react-router-dom";
import HeroSection from "../components/HeroSection.jsx";
import TileCard from "../components/TileCard.jsx";
import Timeline from "../components/Timeline.jsx";
import LevelQuiz from "../components/LevelQuiz.jsx";
import BookingForm from "../components/BookingForm.jsx";
import { useReveal, useCountUp } from "../lib/motion.js";
import { STATS, PROGRAM_CARDS, HOME_STEPS } from "../lib/content.js";

function Stat({ item }) {
  // Хук має викликатись завжди, навіть для текстової картки:
  // умовний виклик зламав би порядок хуків у React.
  const ref = useCountUp(item.value ?? 0);

  return (
    <div className="stat">
      <div className={`stat__number${item.text ? " stat__number--text" : ""}`}>
        {item.text ? item.text : (
          <>{item.prefix}<span ref={ref}>0</span>{item.suffix}</>
        )}
      </div>
      <div className="stat__label">{item.label}</div>
      {item.note ? <div className="stat__note">{item.note}</div> : null}
    </div>
  );
}

export default function Home() {
  const navigate = useNavigate();
  useReveal();

  return (
    <>
      <HeroSection />

      {/* ---------- СТАТИСТИКА ---------- */}
      <section className="stats">
        <div className="container">
          <div className="stats__inner" data-reveal>
            {STATS.map((s) => <Stat key={s.label} item={s} />)}
          </div>
        </div>
      </section>

      {/* ---------- НАПРЯМКИ ---------- */}
      <section className="sec" id="programs">
        <div className="container">
          <div className="sec__head" data-reveal>
            <div>
              <p className="kicker">Напрямки</p>
              <h2 className="section-title">Оберіть ціль — програму зберемо ми</h2>
              <p className="section-subtitle">
                Чотири треки з різними матеріалами, темпом і критеріями результату.
                Кожен доступний у будь-якому форматі: індивідуально, у парі чи в групі.
              </p>
            </div>
            <button type="button" className="btn btn-dark" onClick={() => navigate("/programs")}>
              Всі програми →
            </button>
          </div>

          <div className="tiles" data-reveal>
            {PROGRAM_CARDS.map((c) => (
              <TileCard key={c.title} {...c} onClick={() => navigate("/programs")} />
            ))}
          </div>
        </div>
      </section>

      {/* ---------- ЯК ЦЕ ПРАЦЮЄ ---------- */}
      <section className="sec">
        <div className="container">
          <div className="dark" data-reveal>
            <p className="kicker kicker--lime">Як це працює</p>
            <h2 className="section-title section-title--light">Три кроки до старту</h2>
            <p className="section-subtitle section-subtitle--light">
              Повну методику й систему контрольних точок описали на сторінці «Про школу».
            </p>

            <Timeline steps={HOME_STEPS} />

            <button type="button" className="btn btn-lime" onClick={() => navigate("/about")}>
              Детально про методику →
            </button>
          </div>
        </div>
      </section>

      {/* ---------- ЦІНИ (тизер) ---------- */}
      <section className="sec">
        <div className="container">
          <div className="sec__head" data-reveal>
            <div>
              <p className="kicker">Формати та ціни</p>
              <h2 className="section-title">Платите тільки за те, що обрали</h2>
              <p className="section-subtitle">
                Ціна залежить від формату, цілі та розміру пакета. На сторінці цін є
                конструктор — зберете свій варіант і одразу побачите суму.
              </p>
            </div>
            <button type="button" className="btn btn-dark" onClick={() => navigate("/packages")}>
              Відкрити конструктор →
            </button>
          </div>

          <div className="teaser" data-reveal>
            <article className="teaser__card">
              <h3>Група до 6</h3>
              <p>Оптимально за ціною. Однорівнева група, урок 90 хвилин.</p>
              <ul>
                <li>Матеріали включені</li>
                <li>Speaking Club безкоштовно</li>
              </ul>
            </article>
            <article className="teaser__card teaser__card--hot">
              <span className="teaser__badge">Найчастіше обирають</span>
              <h3>Індивідуально</h3>
              <p>Максимальна швидкість. Графік і програма — під вас.</p>
              <ul>
                <li>Персональна програма</li>
                <li>Перевірка письмових робіт</li>
                <li>Заміна викладача в 1 клік</li>
              </ul>
            </article>
            {/* Пара — єдиний формат, який доводиться пояснювати: люди
                думають, що потрібен свій партнер, і проходять повз.
                Тому прямо кажемо, що пару можна підібрати. */}
            <article className="teaser__card">
              <h3>У парі</h3>
              <p>Як індивідуально, але дешевше: увага викладача ділиться на двох, а не на групу.</p>
              <ul>
                <li>Друг, партнер, колега — або підберемо пару</li>
                <li>Підбираємо за рівнем і темпом</li>
                <li>Удвічі більше розмовної практики</li>
              </ul>
            </article>
            <article className="teaser__card">
              <h3>Speaking Club</h3>
              <p>Окремий формат для практики. Можна без основного курсу.</p>
              <ul>
                <li>Групи за рівнем</li>
                <li>Без домашніх завдань</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      {/* ---------- ЕКСПРЕС-ТЕСТ ---------- */}
      <section className="sec" id="quiz">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Експрес-тест</p>
            <h2 className="section-title">Перевіримо ваш рівень</h2>
            <p className="section-subtitle">
              Три питання, без реєстрації. Відповіді побачить викладач і розбере їх
              на безкоштовному пробному уроці — там і назве ваш рівень за CEFR.
            </p>

            {/* Три речі, які знімають напругу перед тестом і які люди
                інакше додумують самі, зазвичай не на нашу користь:
                що це не іспит, що «нуль» — нормальна відповідь,
                і що є довший варіант, якщо хочеться точніше. */}
            {/* Дві окремі картки, а не один широкий блок у дві колонки:
                це різні думки — «можна не проходити» і «можна детальніше».
                В одній рамці вони читалися як один довгий абзац. */}
            <div className="quiz-note" data-reveal>
              <article className="quiz-note__card">
                <h3>Тест не обовʼязковий</h3>
                <p>
                  Якщо англійської немає взагалі — це не проблема й не привід
                  соромитись: саме з нуля ми вчимо найчастіше. Рівень усе одно
                  перевіримо на пробному уроці й там же складемо програму під вас.
                </p>
              </article>

              <article className="quiz-note__card">
                <h3>Хочете точніше?</h3>
                <p>
                  Є <Link to="/level-test">повний тест на 25 питань</Link> — два
                  набори складності на вибір: окремо для тих, хто починає,
                  і для тих, хто вже непогано знає.
                </p>
              </article>
            </div>
          </div>
          <div data-reveal><LevelQuiz /></div>
        </div>
      </section>

      {/* Блок «Відгуки» прибрано до появи реальних. Вісім порожніх карток
          «Відгук #1 · Ім'я · напрямок» не викликають довіри, а повідомляють,
          що відгуків немає. Компонент Testimonials лишений — повернути секцію,
          коли зберемо 5–8 справжніх. Вигаданих не додаємо: це заборонена
          оманлива практика й порушення правил Google Ads і Meta. */}

      {/* ---------- CTA ---------- */}
      <section className="sec" id="book">
        <div className="container" data-reveal>
          <BookingForm source="site/home" />
        </div>
      </section>
    </>
  );
}
