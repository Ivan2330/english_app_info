import { useEffect, useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import { fetchPackageBySlug } from "../api/packages.js";
import { createOrder, payOrder } from "../api/orders.js";
import { money, lessonsWord } from "../lib/labels.js";
import { useReveal } from "../lib/motion.js";
import { ChastBadge, ChastLegal } from "../components/ChastBadge.jsx";

/**
 * Оформлення замовлення.
 *
 * Один екран, без багатокрокового майстра. На чеку 10–40 тисяч гривень
 * кожен зайвий крок — це місце, де людина зупиняється й іде подумати.
 * Тому все видно одразу: що купує, скільки коштує, куди писати контакти.
 *
 * Спосіб оплати обирається тут же, і Покупка Частинами показана як
 * рівноправний варіант, а не як «розстрочка» дрібним шрифтом: для
 * більшої частини чеків саме вона знімає заперечення про ціну.
 */
export default function Checkout() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const slug = params.get("package");

  const [pkg, setPkg] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [method, setMethod] = useState("card");
  const [parts, setParts] = useState(3);
  const [form, setForm] = useState({
    customer_name: "", customer_phone: "", customer_email: "",
    student_name: "", comment: "", promo_code: "",
  });
  const [familyClaim, setFamilyClaim] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useReveal([pkg]);

  useEffect(() => {
    if (!slug) { setNotFound(true); return; }
    fetchPackageBySlug(slug)
      .then((p) => {
        setPkg(p);
        // Якщо для пакета ПЧ недоступна — не показуємо її взагалі,
        // щоб людина не обрала варіант, який одразу відпаде.
        if (!p.chast_enabled) setMethod("card");
        else setParts(Math.min(3, p.chast_max_parts || 3));
      })
      .catch(() => setNotFound(true));
  }, [slug]);

  function onChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function submit(e) {
    e.preventDefault();
    setError(null);

    if (!form.customer_name.trim()) {
      setError("Вкажіть, будь ласка, імʼя");
      return;
    }
    if (!form.customer_phone.trim() && !form.customer_email.trim()) {
      setError("Потрібен телефон або email, щоб ми могли звʼязатися");
      return;
    }

    setBusy(true);
    try {
      const { order } = await createOrder({
        ...form,
        family_claim: familyClaim,
        package_slug: slug,
        source: "site/checkout",
      });

      /* Знижку рахує БЕКЕНД і повертає в `order.amount`. Фронт її не рахує
         принципово: інакше довелося б повторити правила перевірки коду
         в браузері, де їх можна подивитись і підібрати.

         Через це сума на кнопці до відправки — ціна пакета, а остаточну
         людина бачить уже на сторінці банку. Попереджаємо про це текстом
         під полем коду, щоб різниця не виглядала як помилка. */
      const pay = await payOrder(order.public_id, {
        method,
        ...(method === "chast" ? { parts_count: parts } : {}),
      });

      if (pay.checkout_url) {
        // Номер замовлення кладемо в адресу сторінки результату:
        // після повернення з банку стан треба буде опитати.
        sessionStorage.setItem("pa_last_order", order.public_id);
        window.location.href = pay.checkout_url;
      } else {
        navigate(`/payment/result?order=${order.public_id}`);
      }
    } catch (err) {
      const status = err?.response?.status;
      if (status === 503) {
        // Оплата вимкнена, поки не внесені реквізити ФОПа в оферту.
        setError(
          err?.response?.data?.detail ||
          "Оплата на сайті тимчасово недоступна. Напишіть нам — оформимо вручну."
        );
      } else {
        setError("Не вдалося створити замовлення. Спробуйте ще раз або напишіть нам.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (notFound) {
    return (
      <>
        <PageHero crumb="Оформлення" title="Пакет не знайдено" />
        <section className="sec sec--tight">
          <div className="container">
            <p className="co-msg">
              Схоже, посилання застаріло.{" "}
              <Link to="/packages">Оберіть пакет на сторінці цін</Link>.
            </p>
          </div>
        </section>
      </>
    );
  }

  if (!pkg) {
    return (
      <>
        <PageHero crumb="Оформлення" title="Оформлення замовлення" />
        <section className="sec sec--tight">
          <div className="container"><p className="co-msg">Завантажуємо…</p></div>
        </section>
      </>
    );
  }

  const partOptions = [];
  for (let i = 3; i <= (pkg.chast_max_parts || 3); i++) partOptions.push(i);

  return (
    <>
      <PageHero
        crumb="Оформлення"
        title="Оформлення замовлення"
        lead="Перевірте, що обрали, і залиште контакти. Після оплати з вами звʼяжеться координатор, щоб узгодити розклад і підібрати викладача."
      />

      <section className="sec sec--tight">
        <div className="container co">
          {/* ---------- що купуємо ---------- */}
          <aside className="co__summary" data-reveal>
            <p className="co__eyebrow">Ваш вибір</p>
            <h2 className="co__title">{pkg.name}</h2>

            <div className="co__price">{money(pkg.total_price, pkg.currency)}</div>
            {pkg.price_per_lesson ? (
              <p className="co__rate">
                {money(pkg.price_per_lesson, pkg.currency)} за урок
                {pkg.price_per_person ? " з людини" : ""}
              </p>
            ) : null}

            <ul className="co__facts">
              {pkg.lessons_count ? (
                <li>
                  <b>{pkg.lessons_count}</b> {lessonsWord(pkg.lessons_count)}
                  {pkg.lesson_duration_min ? ` по ${pkg.lesson_duration_min} хв` : ""}
                </li>
              ) : null}
              {pkg.group_size_max && pkg.format === "group" && (
                <li>Група до <b>{pkg.group_size_max}</b> людей</li>
              )}
              {/* Термін дії — те, чим ми кращі за ринок, і доти його ніде не було видно */}
              {pkg.validity_days ? (
                <li>Діє <b>{pkg.validity_days} днів</b> від першого заняття</li>
              ) : null}
              <li>Speaking Club — безкоштовно</li>
              <li>Матеріали й перевірка домашніх у ціні</li>
            </ul>

            <p className="co__fine">
              Оформлюючи замовлення, ви приймаєте{" "}
              <Link to="/offer">умови публічної оферти</Link>.
            </p>
          </aside>

          {/* ---------- контакти й оплата ---------- */}
          <form className="co__form" onSubmit={submit} data-reveal>
            <h3 className="co__h3">Контактні дані</h3>

            <label className="co__field">
              <span>Імʼя та прізвище *</span>
              <input name="customer_name" value={form.customer_name}
                     onChange={onChange} autoComplete="name" required />
            </label>

            <div className="co__row">
              <label className="co__field">
                <span>Телефон</span>
                <input name="customer_phone" value={form.customer_phone}
                       onChange={onChange} autoComplete="tel" placeholder="+380…" />
              </label>
              <label className="co__field">
                <span>Email</span>
                <input name="customer_email" type="email" value={form.customer_email}
                       onChange={onChange} autoComplete="email" />
              </label>
            </div>

            {/* Для дитячих і підліткових пакетів платник і учень — різні люди.
                Питаємо прямо, інакше координатор з'ясовує це телефоном. */}
            <label className="co__field">
              <span>Імʼя учня, якщо навчатиметесь не ви</span>
              <input name="student_name" value={form.student_name} onChange={onChange} />
            </label>

            <label className="co__field">
              <span>Побажання щодо розкладу чи цілей</span>
              <textarea name="comment" rows={3} value={form.comment} onChange={onChange} />
            </label>

            {/* Код і сімейна знижка стоять ПІСЛЯ контактів, а не перед ними.
                Поле промокоду вгорі форми — класичний спосіб втратити покупця:
                людина згадує, що код десь був, іде його шукати й не вертається. */}
            <label className="co__field">
              <span>Код того, хто вас порекомендував</span>
              <input
                name="promo_code"
                value={form.promo_code}
                onChange={onChange}
                placeholder="PA-XXXXXXXX"
                autoComplete="off"
                spellCheck="false"
              />
              <small className="co__hint">
                Номер замовлення людини, яка вже в нас навчається. Знижку
                перевіряє й застосовує сервер — остаточну суму побачите
                на сторінці оплати.
              </small>
            </label>

            <label className="co__check">
              <input
                type="checkbox"
                checked={familyClaim}
                onChange={(e) => setFamilyClaim(e.target.checked)}
              />
              <span>
                У нас уже навчається хтось із моєї родини
                <small>
                  Менеджер перевірить і застосує сімейну знижку до оплати.
                  Автоматично її не ставимо: підтвердити спорідненість
                  за даними замовлення неможливо.
                </small>
              </span>
            </label>

            <h3 className="co__h3">Спосіб оплати</h3>

            <label className={`co__pay${method === "card" ? " is-on" : ""}`}>
              <input type="radio" name="method" value="card"
                     checked={method === "card"} onChange={() => setMethod("card")} />
              <span>
                <b>Карткою онлайн</b>
                <small>Visa, Mastercard, Apple Pay, Google Pay</small>
              </span>
            </label>

            {pkg.chast_enabled && (
              <label className={`co__pay${method === "chast" ? " is-on" : ""}`}>
                <input type="radio" name="method" value="chast"
                       checked={method === "chast"} onChange={() => setMethod("chast")} />
                <span>
                  {/* Назву й значок бере ChastBadge: написання там одне з трьох
                      дозволених, і міняти його можна лише в одному місці.
                      Скорочувати до «кредиту» чи «розстрочки» не можна —
                      за це відключають від сервісу. */}
                  <b><ChastBadge naming="name" size="sm" /></b>
                  <small>
                    Ціна така сама, як при звичайній оплаті: комісію сплачує школа.
                    Працює для клієнтів monobank.
                  </small>
                </span>
              </label>
            )}

            {method === "chast" && partOptions.length > 1 && (
              <label className="co__field co__parts">
                <span>На скільки платежів</span>
                <select value={parts} onChange={(e) => setParts(Number(e.target.value))}>
                  {partOptions.map((n) => (
                    <option key={n} value={n}>
                      {n} платежі по {money(Math.round(pkg.total_price / n), pkg.currency)}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {error && <p className="co__err" role="alert">{error}</p>}

            <button type="submit" className="btn btn-cta co__submit" disabled={busy}>
              {busy ? "Готуємо оплату…" : `Оплатити ${money(pkg.total_price, pkg.currency)}`}
            </button>

            <p className="co__fine">
              Не впевнені у виборі? <Link to="/contacts">Запишіться на безкоштовний
              пробний урок</Link> — підберемо формат разом.
            </p>

            {/* Юридичні тексти monobank мають стояти біля КОЖНОЇ згадки сервісу,
                не лише на сторінці цін. Показуємо, тільки якщо ПЧ справді
                доступна для цього пакета: інакше це реклама того, чого на
                екрані немає. Без переліку характеристик — тут ПЧ це кнопка,
                а не опис продукту. */}
            {pkg.chast_enabled && <ChastLegal />}
          </form>
        </div>
      </section>
    </>
  );
}
