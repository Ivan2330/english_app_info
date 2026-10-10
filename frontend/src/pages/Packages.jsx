import { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { fetchPackages, fetchPackageFilters } from "../api/packages.js";
import PackageBuilder from "../components/PackageBuilder.jsx";
import PriceCard from "../components/PriceCard.jsx";
import { TRACK, money } from "../lib/labels.js";
import { useReveal } from "../lib/motion.js";
import Faq from "../components/Faq.jsx";
import BookingForm from "../components/BookingForm.jsx";
import PageHero from "../components/PageHero.jsx";
import { FAQ_PAYMENT } from "../lib/content.js";
import { ChastBadge, ChastLegal } from "../components/ChastBadge.jsx";
import BonusLessons from "../components/BonusLessons.jsx";

/**
 * Сторінка цін.
 *
 * Три родини продуктів, які продаються по-різному:
 *   абонемент — пакет уроків, витрачається у своєму темпі (конструктор)
 *   курс      — фіксована програма з конкретним фінішем (картки)
 *   клуб      — помісячна підписка на розмовну практику
 */
export default function Packages() {
  const navigate = useNavigate();

  const [combos, setCombos] = useState([]);
  const [courses, setCourses] = useState([]);
  const [clubs, setClubs] = useState([]);
  const [corporate, setCorporate] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [courseTrack, setCourseTrack] = useState("all");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchPackageFilters(),
      fetchPackages({ family: "course" }),
      fetchPackages({ family: "club" }),
      fetchPackages({ family: "corporate" }),
    ])
      .then(([c, co, cl, corp]) => {
        if (cancelled) return;
        setCombos(c);
        setCourses(co);
        setClubs(cl);
        setCorporate(corp);
      })
      .catch(() => !cancelled && setError(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  // Картки приходять з API, тому reveal переспостерігає їх після завантаження.
  useReveal([loading, courses.length, clubs.length, corporate.length, courseTrack]);

  /**
   * Куди веде «Обрати».
   *
   * Корпоративні позиції — завжди в контакти: там ціна за групу за заняття,
   * постоплата за фактично проведені й рахунок на юрособу. Купити це
   * кнопкою неможливо в принципі.
   *
   * Решта — на оформлення замовлення. Якщо оплата вимкнена (реквізити ФОПа
   * ще не внесені в оферту), сторінка сама це скаже й запропонує написати нам:
   * краще показати чесне пояснення на кроці оплати, ніж вести в контакти
   * всіх підряд і втрачати тих, хто готовий платити зараз.
   */
  const goSelect = (p) => {
    if (p.family === "corporate") {
      navigate("/contacts", { state: { selectedPackage: p.slug } });
      return;
    }
    navigate(`/checkout?package=${encodeURIComponent(p.slug)}`);
  };

  const courseTracks = useMemo(() => {
    const set = [...new Set(courses.map((c) => c.track))];
    return ["all", ...set];
  }, [courses]);

  const visibleCourses = useMemo(
    () => (courseTrack === "all" ? courses : courses.filter((c) => c.track === courseTrack)),
    [courses, courseTrack]
  );

  if (loading) {
    return (
      <section className="packages">
        <div className="container"><p>Завантаження…</p></div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="packages">
        <div className="container">
          <h1 className="section-title">Пакети та ціни</h1>
          <p>Не вдалося завантажити каталог. Спробуйте оновити сторінку.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="packages packages--catalog">
      <PageHero
        crumb="Ціни та пакети"
        title="Три типи продуктів. Оберіть свій"
        lead={<>
          <b>Абонемент</b> — пакет уроків, які ви витрачаєте у своєму темпі.{" "}
          <b>Курс</b> — готова програма з фіксованою тривалістю під конкретну ціль.{" "}
          <b>Speaking Club</b> — помісячна підписка на розмовну практику.
        </>}
      />

      <div className="container">

        {/* ---------- АБОНЕМЕНТИ ---------- */}
        <div className="packages__group" id="subscriptions" data-reveal>
          <h2 className="packages__group-title">Абонемент для регулярного навчання</h2>
          {/* Конструктор — це регулярне навчання «на рівень». Людина, яка
              прийшла за IELTS чи співбесідою, інакше перебирає тут напрями,
              не знаходить свого й вирішує, що ми цього не робимо, — хоча
              курси під ціль лежать на тій самій сторінці нижче. Один рядок
              із посиланням дешевший за втраченого відвідувача. */}
          <p className="package-subtitle">
            Цей конструктор — для загальної англійської, розмовної практики
            та шкільної програми. Оберіть, для кого навчання, напрям, формат
            і кількість уроків — і одразу побачите вартість.
          </p>
          <p className="package-subtitle package-subtitle--aside">
            Є конкретна ціль — IELTS, співбесіда, НМТ, переїзд?{" "}
            <a href="#courses">Курси під ціль — нижче</a>: там фіксована програма
            й зрозумілий фініш, а не абонемент на уроки.
          </p>
          <PackageBuilder combos={combos} onSelect={goSelect} />
          <BonusLessons id="lesson-bonuses" />
        </div>

        <section className="pricing-benefits" id="benefits" aria-labelledby="benefits-title" data-reveal>
          <h2 className="packages__group-title" id="benefits-title">Навчатися можна ще вигідніше</h2>
          <p className="package-subtitle">Ціни на сторінці можуть бути нижчими завдяки рекомендаціям і вашим результатам.</p>
          <div className="pricing-benefits__grid">
            <article className="pricing-benefit pricing-benefit--friend">
              <span className="pricing-benefit__label">Запросіть друга</span>
              <div className="pricing-benefit__value">−20% <span>кожному</span></div>
              <h3>Разом починати приємніше</h3>
              <p>Приведіть друга — і кожен із вас отримає додаткові 20% знижки від ціни свого пакета на цій сторінці. Знижка за обсяг пакета вже врахована й зберігається.</p>
              <p className="pricing-benefit__note">Перед покупкою повідомте нам, що прийшли за рекомендацією, — допоможемо оформити знижку обом.</p>
              <Link className="pricing-benefit__link" to="/contacts">Уточнити знижку за друга →</Link>
            </article>
            <article className="pricing-benefit">
              <span className="pricing-benefit__label">Бали за успішність</span>
              <div className="pricing-benefit__value pricing-benefit__value--progress">Ваш прогрес</div>
              <h3>Результати відкривають більше можливостей</h3>
              <p>Під час навчання ви накопичуєте бали за успішність. Що кращі результати — то більше балів і шансів отримати додаткові знижки на навчання.</p>
              <p className="pricing-benefit__note">Бали не означають автоматичної знижки: доступні пропозиції та умови пояснить команда школи.</p>
            </article>
          </div>
        </section>

        {/* ---------- ЩО ВХОДИТЬ У БУДЬ-ЯКИЙ ПАКЕТ ---------- */}
        <section className="shared-included card" data-reveal>
          <h2 className="packages__group-title">У кожному пакеті</h2>
          <ul className="shared-included__list">
            <li>Матеріали уроків і <strong>домашні завдання</strong> в кабінеті.</li>
            <li><strong>Письмовий розбір</strong> письмових робіт, а не «в цілому нормально».</li>
            <li><strong>Speaking Club</strong> — безкоштовно для всіх активних учнів.</li>
            <li>Щомісячний <strong>звіт про прогрес</strong> у цифрах.</li>
            <li>Заміна викладача <strong>без пояснень</strong> і без втрати оплачених уроків.</li>
            <li>Підсумковий <strong>сертифікат</strong> після рівня.</li>
          </ul>
        </section>

        {/* ---------- ТЕМАТИЧНІ КУРСИ ---------- */}
        {courses.length > 0 && (
          <div className="packages__group" id="courses" data-reveal>
            <h2 className="packages__group-title">Курси під конкретну ціль</h2>
            <p className="package-subtitle">
              Окремі програми під вашу ціль: іспит, роботу, співбесіду чи подорож.
              Тут ви обираєте готовий курс із визначеною кількістю уроків.
              Для іспитів вартість залежить
              від стартового рівня: що вищий старт — то коротший і дешевший курс.
            </p>

            <p className="package-subtitle package-subtitle--aside">
              Ціни можуть бути нижчими завдяки <a href="#benefits">додатковим знижкам</a>,
              а до пакетів додаються <a href="#lesson-bonuses">бонусні уроки — до 50% зверху</a>.
            </p>
            {(clubs.length > 0 || corporate.length > 0) && (
              <nav className="package-section-links" aria-label="Інші пропозиції нижче">
                <span>Нижче — окремі пропозиції:</span>
                {clubs.length > 0 && <a href="#club">Speaking Club ↓</a>}
                {corporate.length > 0 && <a href="#corporate">Навчання для компаній ↓</a>}
              </nav>
            )}

            <div className="course-filter">
              {courseTracks.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`chip${courseTrack === t ? " is-active" : ""}`}
                  onClick={() => setCourseTrack(t)}
                >
                  {t === "all" ? "Усі" : TRACK[t]?.label ?? t}
                </button>
              ))}
            </div>

            <div className="price-grid">
              {visibleCourses.map((p) => (
                <PriceCard key={p.id} pkg={p} onSelect={() => goSelect(p)} />
              ))}
            </div>
          </div>
        )}

        {/* ---------- SPEAKING CLUB ---------- */}
        {clubs.length > 0 && (
          <div className="packages__group" id="club" data-reveal>
            <h2 className="packages__group-title">Speaking Club</h2>
            <p className="package-subtitle">
              Для учнів школи клуб <strong>безкоштовний</strong>. Ціни нижче — для тих,
              хто хоче тільки розмовну практику без основного курсу.
            </p>
            <div className="price-grid">
              {clubs.map((p) => (
                <PriceCard key={p.id} pkg={p} onSelect={() => goSelect(p)} />
              ))}
            </div>
          </div>
        )}

        {/* ---------- КОРПОРАТИВ ---------- */}
        {corporate.length > 0 && (
          <div className="packages__group" id="corporate" data-reveal>
            <h2 className="packages__group-title">Для компаній</h2>
            <p className="package-subtitle">
              Тут ціна вказана <strong>за групу за одне заняття</strong>, а не за людину.
              Рахунок виставляємо наприкінці місяця за фактично проведені заняття,
              з договором і закривними документами.
            </p>

            <div className="corp-table-wrap">
              <table className="corp-table">
                <thead>
                  <tr>
                    <th>Формат</th>
                    <th>Людей</th>
                    <th>Урок</th>
                    <th>Ціна</th>
                  </tr>
                </thead>
                <tbody>
                  {corporate.map((p) => (
                    <tr key={p.id} className={p.is_popular ? "is-popular" : undefined}>
                      <td>
                        <strong>{p.name}</strong>
                        {p.short_description ? <span className="corp-note">{p.short_description}</span> : null}
                      </td>
                      <td>{p.group_size_max === 1 ? "1" : `до ${p.group_size_max}`}</td>
                      <td>{p.lesson_duration_min} хв</td>
                      <td className="corp-price">{money(p.total_price, p.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="shared-included__list corp-terms">
              <li>Знижки за обсяг: 2 групи −5%, 3–4 −10%, 5–6 −15%, 7+ −20%</li>
              <li>Безкоштовне вступне тестування рівня співробітників від 2 груп</li>
              <li>Кабінет для HR: відвідуваність, результати тестів, сертифікати, фінансовий звіт</li>
              <li>Мінімальний контракт — 3 місяці, із заморозкою на час відпусток</li>
            </ul>

            {/* Ціни в таблиці вище — верхня межа, а не остаточна пропозиція.
                Корпоративні умови завжди рахуються під конкретну компанію:
                кількість груп, графік, тривалість контракту. Сказати про це
                прямо вигідніше, ніж мовчати: інакше HR порівнює нашу табличну
                ціну з чужою індивідуальною і йде. */}
            <div className="corp-offer">
              <div className="corp-offer__body">
                <p className="kicker kicker--lime">Індивідуальна пропозиція</p>
                <h3 className="corp-offer__title">
                  Напишіть нам — порахуємо вигідніше, ніж у таблиці
                </h3>
                <p className="corp-offer__text">
                  Ціни вище — базові. Під конкретну компанію умови рахуємо окремо
                  й майже завжди вони кращі за вказані: усе залежить від кількості
                  груп, графіка та тривалості контракту. Розкажіть, скільки у вас
                  людей і чого треба досягти — надішлемо прорахунок і програму.
                </p>
                <ul className="corp-offer__list">
                  <li>Додаткові знижки понад сітку за обсяг</li>
                  <li>Пілотний місяць, щоб перевірити нас без довгих зобовʼязань</li>
                  <li>Окремі умови для кількох відділів або філій</li>
                  <li>Гнучкий графік: ранкові, вечірні та обідні слоти</li>
                </ul>
                <div className="corp-offer__actions">
                  <button type="button" className="btn btn-lime" onClick={() => navigate("/contacts")}>
                    Отримати прорахунок
                  </button>
                  <a className="btn btn-outline" href="mailto:my.primeacademy19@gmail.com?subject=Корпоративне навчання">
                    Написати на пошту
                  </a>
                </div>
              </div>

              <aside className="corp-offer__side">
                <div className="corp-offer__big">24 год</div>
                <p>готуємо комерційну пропозицію</p>
                <ul>
                  <li>Тест рівня команди</li>
                  <li>Склад і кількість груп</li>
                  <li>Кошторис на весь контракт</li>
                  <li>Договір і закривні документи</li>
                </ul>
              </aside>
            </div>
          </div>
        )}

        {/* ---------- ОПЛАТА ---------- */}
        <section className="shared-included card" id="payment" data-reveal>
          <h2 className="packages__group-title">Оплата</h2>
          <ul className="shared-included__list">
            <li>Карткою онлайн: Visa, Mastercard, Apple Pay, Google Pay.</li>
            <li className="payment-installments">
              <ChastBadge naming="name" size="sm" />
              <p>Ціна частинами така сама, як при оплаті одразу. Комісію сплачує школа.</p>
            </li>
            <li>Для компаній — рахунок на юрособу й закривні документи.</li>
            <li>
              За невикористані уроки повертаємо кошти — умови в{" "}
              <Link to="/offer">публічній оферті</Link>.
            </li>
          </ul>

          {/* Обовʼязковий блок за вимогами monobank. Раніше він був набраний
              тут руками, і в ньому стояло «Покупка частинами» з малої — а це
              вже не одне з трьох дозволених написань. Тепер тексти й правило
              про кегль живуть у ChastBadge.jsx, одне місце на весь сайт. */}
          <ChastLegal full />
        </section>

        {/* ---------- FAQ ---------- */}
        <div className="packages__group" id="faq" data-reveal>
          <h2 className="packages__group-title">Питання про ціни, знижки й оплату</h2>
          <Faq items={FAQ_PAYMENT} />
        </div>

        {/* ---------- ЗАПИС ---------- */}
        <div className="packages__group" id="book" data-reveal>
          <BookingForm
            title="Пробний урок — безкоштовно і без картки"
            text="Порахуємо точну вартість під ваш графік і ціль, і скажемо, який пакет реально потрібен, а який — зайвий."
            bullets={["Без оплати", "Онлайн", "Розрахунок вартості"]}
            source="site/pricing"
          />
        </div>
      </div>
    </section>
  );
}
