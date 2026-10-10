import { useNavigate } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import TileCard from "../components/TileCard.jsx";
import LevelScale from "../components/LevelScale.jsx";
import { useReveal } from "../lib/motion.js";
import { FORMATS, PROGRAM_DETAILS } from "../lib/content.js";

/**
 * Сторінка «Програми».
 *
 * Напрямок визначає ЩО вивчаємо, формат — ЯК. Ці два вибори незалежні,
 * і сторінка побудована саме так, щоб це було видно з розкладки.
 */
export default function Programs() {
  const navigate = useNavigate();
  useReveal();

  return (
    <>
      <PageHero
        crumb="Програми"
        title="П'ять напрямків. Один із них точно ваш"
        lead={
          <>
            Напрямок визначає <b>що</b> ви вивчаєте: матеріали, лексику й критерії
            результату. Формат визначає <b>як</b>: індивідуально, у парі, в групі чи
            в розмовному клубі. Ці два вибори незалежні — комбінуєте як зручно.
          </>
        }
      >
        <button type="button" className="btn btn-cta" onClick={() => navigate("/packages")}>
          Порахувати вартість
        </button>
        <a href="#levels" className="btn btn-ghost">Подивитись рівні CEFR</a>
      </PageHero>

      {/* ---------- ФОРМАТИ ---------- */}
      <section className="sec sec--tight">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Формати</p>
            <h2 className="section-title">Чотири способи вчитись</h2>
          </div>
          <div className="tiles" data-reveal>
            {FORMATS.map((f) => <TileCard key={f.title} {...f} />)}
          </div>
        </div>
      </section>

      {/* ---------- НАПРЯМКИ ДЕТАЛЬНО ---------- */}
      <section className="sec">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Напрямки</p>
            <h2 className="section-title">Що саме вивчаємо</h2>
            <p className="section-subtitle">
              Кожен напрямок має власні матеріали й критерій «зараховано».
              Ви завжди знаєте, за що платите і як виміряти результат.
            </p>
          </div>

          <div className="pd-list">
            {PROGRAM_DETAILS.map((p, i) => (
              <article
                key={p.title}
                className={`pd${i % 2 ? " pd--flip" : ""}`}
                data-reveal
              >
                <div className={`pd__side pd__side--${p.tone}`}>
                  <span className="pd__icon" aria-hidden="true">{p.icon}</span>
                  <h3 className="pd__title">{p.title}</h3>
                  <p className="pd__lead">{p.lead}</p>
                  <div className="pd__meta">
                    {p.meta.map((m) => <span key={m} className="tag">{m}</span>)}
                  </div>
                </div>

                <div className="pd__main">
                  <h4 className="pd__h4">Що входить</h4>
                  <ul className="pd__list">
                    {p.includes.map((x) => <li key={x}>{x}</li>)}
                  </ul>
                  <div className="pd__for">
                    <b>Кому підійде</b>
                    {p.forWhom}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- РІВНІ CEFR ---------- */}
      <section className="sec" id="levels">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Рівні CEFR</p>
            <h2 className="section-title">Де ви зараз і що буде далі</h2>
            <p className="section-subtitle">
              Клікніть на рівень — покажемо, що ви вмієте на ньому, скільки часу
              до наступного і скільки це приблизно годин практики.
            </p>
          </div>
          <div data-reveal><LevelScale /></div>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section className="sec">
        <div className="container">
          <div className="dark dark--split" data-reveal>
            <div>
              <p className="kicker kicker--lime">Не знаєте, що обрати?</p>
              <h2 className="section-title section-title--light">
                Підберемо напрямок і формат на пробному уроці
              </h2>
              <p className="section-subtitle section-subtitle--light">
                Не треба вирішувати наперед. Приходьте на безкоштовну діагностику —
                визначимо рівень і запропонуємо конкретний варіант із цінами.
              </p>
              {/* Одна дія, не дві. Другою кнопкою тут було «Спершу подивитись
                  ціни» — і вона працювала проти самого блоку: людині, яка
                  дочитала до кінця сторінки про програми, пропонували вийти
                  замість записатись. Ціни й так є в меню та у блоці пакетів
                  вище, тож нічого не втрачено. */}
              <div className="dark__actions">
                <button type="button" className="btn btn-lime" onClick={() => navigate("/contacts")}>
                  Записатись на пробний
                </button>
              </div>
            </div>

            <div className="dark__panel">
              <div className="dark__big">40 хв</div>
              <p>триває безкоштовна діагностика</p>
              <ul className="dark__list">
                <li>Тест рівня + розмова</li>
                <li>Рекомендація напрямку</li>
                <li>Розрахунок вартості</li>
                <li>Жодних зобов'язань</li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
