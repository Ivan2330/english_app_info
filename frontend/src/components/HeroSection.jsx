import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import CTAButton from "./CTAButton";
import { useMagnetic } from "../lib/motion.js";

/** Слова, що змінюються в заголовку. Кожне — окрема ціль навчання. */
const GOALS = ["кар'єри", "подорожей", "іспиту", "співбесіди", "НМТ", "життя за кордоном"];

/** Рядок, що біжить під героєм. */
const MARQUEE = [
  "CEFR A1–C2", "IELTS", "TOEFL iBT", "Business English", "НМТ",
  "Speaking Club", "Індивідуально", "Групи до 6", "Власна платформа",
];

export default function HeroSection() {
  const navigate = useNavigate();
  const ghostRef = useMagnetic();
  const [goal, setGoal] = useState(0);

  // Ротація слова в заголовку. Якщо система просить менше руху —
  // лишаємо перше слово статичним.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setGoal((i) => (i + 1) % GOALS.length), 2600);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="hero">
      <div className="container hero__inner">
        <div className="hero__grid">
          <div className="hero__content">
            <span className="hero__pill">
              <b>НАБІР</b> Стартуємо щопонеділка
            </span>

            <h1 className="hero__title">
              Англійська для
              <span className="hero__rotator" aria-live="polite">
                {GOALS.map((word, i) => (
                  <span key={word} className={i === goal ? "is-on" : ""}>
                    {word}
                  </span>
                ))}
              </span>
            </h1>

            <p className="hero__subtitle">
              Не «курси для всіх». Ви обираєте формат і ціль — ми збираємо під них
              програму, темп і викладача. Перший урок безкоштовний, без картки.
            </p>

            <div className="hero__actions">
              <CTAButton
                label="Записатись на пробний урок"
                onClick={() => navigate("/contacts")}
              />
              <button
                ref={ghostRef}
                className="btn btn-ghost"
                onClick={() => navigate("/packages")}
              >
                Переглянути пакети
              </button>
            </div>
          </div>

          {/* Картка прогресу учня — показує результат, а не процес */}
          <aside className="hero__visual" aria-label="Приклад прогресу учня">
            <div className="pcard">
              <div className="pcard__head">
                {/* Знеособлено свідомо: вигадане імʼя з віком читається як
                    відгук, а відгуків у нас поки немає. Це схема прогресу,
                    а не історія конкретної людини.

                    У значку — рівень ПОТОЧНИЙ (B1), а не стартовий. Усі три
                    місця на картці мають казати одне й те саме: значок,
                    підпис під смужкою і сама смужка. Доти тут стояло «A2»
                    при смужці, що доповзала до B2, — і картка сперечалася
                    сама з собою. */}
                <span className="pcard__avatar" aria-hidden="true">B1</span>
                <div>
                  <div className="pcard__name">Приклад прогресу</div>
                  <div className="pcard__goal">Ціль: співбесіда англійською</div>
                </div>
                <span className="pcard__since">4 міс</span>
              </div>

              <div className="pcard__scale">
                {/* «ПОТОЧНИЙ РІВЕНЬ: A2 → B1» — суперечність у самому рядку:
                    поточний рівень не буває діапазоном. Тут показано рух,
                    тому підпис про рух. */}
                <div className="pcard__scale-top">
                  <span>БУЛО → СТАЛО</span>
                  <b>A2 → B1</b>
                </div>
                <div className="pcard__track">
                  <i />
                </div>
                <div className="pcard__ticks">
                  <span>A1</span><span>A2</span><b>B1</b>
                  <span>B2</span><span>C1</span><span>C2</span>
                </div>
              </div>

              <div className="pcard__mini">
                <div className="pcard__cell">
                  <span>СЛІВ У АКТИВІ</span>
                  <b>1 240</b>
                  <div className="pcard__spark">
                    {[28, 42, 36, 58, 51, 70, 64, 88].map((h, i) => (
                      <i key={i} style={{ height: `${h}%`, animationDelay: `${0.5 + i * 0.07}s` }} />
                    ))}
                  </div>
                </div>
                <div className="pcard__cell">
                  <span>УРОКІВ ПРОЙДЕНО</span>
                  <b>32</b>
                  <p className="pcard__meta">Відвідуваність 96%<br />Домашніх зроблено 28/32</p>
                </div>
              </div>

              <ul className="pcard__steps">
                <li><b>✓</b>Пройдено: базові часи й побутові теми</li>
                <li><b>✓</b>Пройдено: телефонна розмова та емейли</li>
                <li className="is-next"><b>3</b>Далі: mock-інтерв'ю та лексика галузі</li>
              </ul>
            </div>

            <div className="pcard__float pcard__float--goal">
              <span className="pcard__emoji">🎯</span>
              <div>Ціль тижня<small>40 нових слів · 92%</small></div>
            </div>
            <div className="pcard__float pcard__float--growth">
              <span className="pcard__emoji pcard__emoji--cyan">📈</span>
              <div>A2 → B1<small>за 4 місяці</small></div>
            </div>
          </aside>
        </div>

        <div className="hero__marquee" aria-hidden="true">
          <div className="hero__marquee-track">
            {[...MARQUEE, ...MARQUEE].map((item, i) => (
              <span key={i}>{item}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
