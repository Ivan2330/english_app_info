import PageHero from "../components/PageHero.jsx";
import TileCard from "../components/TileCard.jsx";
import Timeline from "../components/Timeline.jsx";
import Faq from "../components/Faq.jsx";
import BookingForm from "../components/BookingForm.jsx";
import { useReveal } from "../lib/motion.js";
import { useNavigate, Link } from "react-router-dom";
import {
  PRINCIPLES, METHOD_STEPS, DIFFERENCE,
  LEVEL_GUARANTEE, GUARANTEES, FAQ_LEARNING,
  LEVELS, CERTIFICATE_BLOCK,
} from "../lib/content.js";

export default function About() {
  const navigate = useNavigate();
  useReveal();

  return (
    <>
      <PageHero
        crumb="Про школу"
        title="Ми міряємо результат, а не кількість уроків"
        lead="Більшість шкіл продає години. Ми будуємо навчання навколо однієї речі: чи змінився ваш рівень і чи можете ви робити те, чого не могли на старті."
      >
        <button type="button" className="btn btn-cta" onClick={() => navigate("/contacts")}>
          Записатись на пробний урок
        </button>
        <a href="#method" className="btn btn-ghost">Як влаштоване навчання</a>
      </PageHero>

      {/* ---------- ПРИНЦИПИ ---------- */}
      <section className="sec sec--tight">
        <div className="container">
          <div className="tiles tiles--3" data-reveal>
            {PRINCIPLES.map((p) => <TileCard key={p.title} {...p} />)}
          </div>
        </div>
      </section>

      {/* ---------- МЕТОДИКА ---------- */}
      <section className="sec" id="method">
        <div className="container">
          <div className="dark" data-reveal>
            <p className="kicker kicker--lime">Методика</p>
            <h2 className="section-title section-title--light">
              П'ять кроків від «розумію через слово» до вільної мови
            </h2>
            <p className="section-subtitle section-subtitle--light">
              Ніякої магії — послідовна система з контрольними точками,
              однакова для всіх напрямків.
            </p>
            <Timeline steps={METHOD_STEPS} />
          </div>
        </div>
      </section>

      {/* ---------- ЧИМ ВІДРІЗНЯЄМОСЬ ----------
          Стоїть на місці колишнього блоку «Викладачі». Той прибрано:
          після тимчасової паузи бази викладачів недостатньо, а картки
          «Ім'я викладача · Прапор» повідомляли, що команди немає.
          Стилі .teachers / .teacher__* у sections.css лишені —
          повернути секцію, коли буде 4+ реальних профілі. */}
      <section className="sec" id="difference">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Різниця</p>
            <h2 className="section-title">Чотири числа замість обіцянок</h2>
            <p className="section-subtitle">
              «Індивідуальний підхід» і «досвідчені викладачі» пише кожен.
              Нижче те, що можна перевірити на сторінці цін ще до розмови з нами.
            </p>
          </div>

          <div className="diff" data-reveal>
            {DIFFERENCE.map((d) => (
              <article key={d.title} className="diff__card">
                <div className="diff__num">
                  {d.value}<span>{d.unit}</span>
                </div>
                <h3 className="diff__title">{d.title}</h3>
                <p className="diff__text">{d.text}</p>
              </article>
            ))}
          </div>

        </div>
      </section>

      {/* ---------- ШКАЛА CEFR ----------
          Стоїть одразу після методики: там ми пояснили, ЯК вчимо,
          тут показуємо, ДО ЧОГО. Людина шукає себе в переліку
          («так, це про мене») ще до розмови з нами. */}
      <section className="sec" id="cefr">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Шкала</p>
            <h2 className="section-title">Де ви зараз і що буде далі</h2>
            <p className="section-subtitle">
              Описано через дії, а не через назви часів. «Present Perfect»
              нічого не каже тому, хто прийшов із нуля — «можу пройти
              співбесіду англійською» каже все.
            </p>
          </div>

          {/* Джерело — той самий LEVELS, що й в інтерактивній шкалі
              на «Програмах». Другий масив із тими самими рівнями означав би
              два джерела правди: підправив в одному місці — на сусідній
              сторінці лишилося старе. Тут подача статична: усі рівні видно
              одразу, бо людина шукає себе в переліку, а не вивчає кожен. */}
          <ol className="cefr" data-reveal>
            {LEVELS.map((l, i) => (
              <li key={l.code} className="cefr__step" style={{ "--i": i }}>
                <div className="cefr__mark">
                  <span className="cefr__lvl">{l.code}</span>
                  <span className="cefr__name">{l.sub}</span>
                </div>

                {/* Один рядок на рівень читався надто сухо — як перелік
                    обмежень, а не як опис того, що людина вже вміє.
                    Тому спершу тепліше речення про сам рівень, а потім
                    конкретні вміння. */}
                <p className="cefr__lead">{l.text}</p>

                <ul className="cefr__can">
                  {l.can.map((c) => <li key={c}>{c}</li>)}
                </ul>

                {/* C2 останній — «до наступного рівня» для нього
                    безглузде, тому в нього окреме формулювання. */}
                <p className="cefr__next">
                  {l.hours ? (
                    <>до наступного рівня — <b>{l.hours}</b>, це <b>{l.time}</b></>
                  ) : (
                    <>далі — <b>підтримка рівня</b></>
                  )}
                </p>
              </li>
            ))}
          </ol>

          <p className="cefr__foot" data-reveal>
            Рівень визначаємо на безкоштовній діагностиці тим самим
            інструментом, яким потім міряємо прогрес.{" "}
            <Link to="/level-test">Або пройдіть тест самостійно</Link> —
            відповіді розбере викладач.{" "}
            <Link to="/programs#levels">Детальніше про кожен рівень</Link>.
          </p>
        </div>
      </section>

      {/* ---------- СЕРТИФІКАТ ----------
          Єдина річ на сторінці, яку відвідувач може перевірити ПРЯМО ЗАРАЗ,
          не лишаючи контакт. Тому головна дія тут — перевірка, а не заявка. */}
      <section className="sec" id="certificate">
        <div className="container">
          <div className="cert-blk" data-reveal>
            <div className="cert-blk__text">
              <p className="kicker kicker--lime">{CERTIFICATE_BLOCK.eyebrow}</p>
              <h2 className="cert-blk__title">{CERTIFICATE_BLOCK.title}</h2>
              <p className="cert-blk__lead">{CERTIFICATE_BLOCK.lead}</p>

              <div className="cert-blk__points">
                {CERTIFICATE_BLOCK.points.map((p) => (
                  <div key={p.title} className="cert-blk__point">
                    <h3>{p.title}</h3>
                    <p>{p.text}</p>
                  </div>
                ))}
              </div>

              <Link className="btn btn-cta" to="/verify-certificate">
                Перевірити сертифікат
              </Link>
            </div>

          </div>
        </div>
      </section>

      {/* ---------- ГАРАНТІЯ РІВНЯ ---------- */}
      <section className="sec" id="guarantee">
        <div className="container">
          <div className="lg" data-reveal>
            <div className="lg__head">
              <p className="kicker kicker--lime">{LEVEL_GUARANTEE.eyebrow}</p>
              <h2 className="lg__title">{LEVEL_GUARANTEE.title}</h2>
              <p className="lg__lead">{LEVEL_GUARANTEE.lead}</p>
            </div>

            <div className="lg__grid">
              {LEVEL_GUARANTEE.conditions.map((c) => (
                <div key={c.text} className="lg__cond">
                  <div className="lg__num">
                    {c.value}<span>{c.unit}</span>
                  </div>
                  <p>{c.text}</p>
                </div>
              ))}
            </div>

            <ol className="lg__steps">
              {LEVEL_GUARANTEE.steps.map((s, i) => (
                <li key={s}><b>{i + 1}</b>{s}</li>
              ))}
            </ol>

            <p className="lg__fine">
              {LEVEL_GUARANTEE.excluded}{" "}
              <Link to="/offer#p10">Повні умови — в оферті</Link>.
            </p>
          </div>
        </div>
      </section>

      {/* ---------- ГАРАНТІЇ ---------- */}
      <section className="sec">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Гарантії</p>
            <h2 className="section-title">За що ми відповідаємо</h2>
            <p className="section-subtitle">
              Обіцянки, які можна перевірити. Все, що не можна виміряти,
              ми сюди не пишемо.
            </p>
          </div>

          <div className="guarantees" data-reveal>
            {GUARANTEES.map((g) => (
              <article key={g.title} className="guarantee card">
                <span className="guarantee__icon" aria-hidden="true">{g.icon}</span>
                <h3>{g.title}</h3>
                <p>{g.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- FAQ ---------- */}
      <section className="sec" id="faq">
        <div className="container">
          <div data-reveal>
            <p className="kicker">Часті питання</p>
            <h2 className="section-title">Про навчання</h2>
          </div>
          <div data-reveal><Faq items={FAQ_LEARNING} /></div>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section className="sec">
        <div className="container" data-reveal>
          <BookingForm
            eyebrow="Перший крок"
            title="Перевірте нас на безкоштовному уроці"
            source="site/about"
          />
        </div>
      </section>
    </>
  );
}
