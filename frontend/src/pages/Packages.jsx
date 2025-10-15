import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchPackages } from "../api/packages.js";
import PriceCard from "../components/PriceCard.jsx";

export default function Packages() {
  const navigate = useNavigate();
  const [tab] = useState("adults"); // зафіксовано дорослих
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  async function load(audience) {
    setLoading(true);
    try {
      const data = await fetchPackages({ audience, active: 1 });
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(tab); }, [tab]);

  const groups = useMemo(() => {
    const standard = items.filter((i) => i.type === "standard");
    const premium  = items.filter((i) => i.type === "premium");
    return { standard, premium };
  }, [items]);

  const goSelect = (p) => navigate("/contacts", { state: { selectedPackage: p.slug } });

  return (
    <section className="packages">
      <div className="container">
        {/* Заголовок + промо-нота */}
        <div className="packages__head">
          <h1 className="section-title">Пакети та ціни</h1>
          <div className="promo-note" role="note">
            Ми запустили оновлені тарифи — зараз вони з <strong>акційною знижкою</strong>.
            Стеж за <strong>постійними акціями</strong> в хайлайтах «Актуальне»
            на нашій новій сторінці в Instagram.
          </div>
        </div>

        {loading && <p>Завантаження...</p>}

        {!loading && (
          <>
            {/* Спільне для обох пакетів */}
            <section className="shared-included card">
              <h2 className="packages__group-title">У кожному пакеті</h2>
              <ul className="shared-included__list">
                <li>
                  Доступ до <strong>додаткових завдань</strong> для тренування всіх скілів
                  (Speaking / Listening / Reading / Writing) — <strong>база постійно поповнюється</strong>.
                </li>
                <li>Персональні цілі та <strong>трекинг прогресу</strong> у кабінеті.</li>
                <li>Матеріали уроків і <strong>домашні завдання</strong> онлайн.</li>
                <li>Підсумковий <strong>сертифікат</strong> після рівня/модуля.</li>
              </ul>
            </section>

            {/* STANDARD */}
            <div className="packages__group">
              <h2 className="packages__group-title">Стандарт</h2>

              {/* Підзаголовок (Варіант A) */}
              <p className="package-subtitle">
                Уроки <strong>по 50 хв</strong> з професійними сертифікованими викладачами.
                Чіткі цілі, живе спілкування й прокачка практичних навичок на кожному занятті.
              </p>

              <div className="package-columns">
                <div className="package-col card">
                  <h3 className="h3">Що входить</h3>
                  <ul className="features-list">
                    <li>Індивідуальні або малі групи на вибір</li>
                    <li><strong>Щотижневі практичні вправи</strong> + міні-квести на говоріння</li>
                    <li>Доступ до <strong>бази додаткових завдань</strong> (усі скіли), постійні оновлення</li>
                    <li><strong>Фідбек</strong> від викладача з конкретними порадами</li>
                  </ul>
                </div>

                <div className="package-col card">
                  <h3 className="h3">Умови</h3>
                  <ul className="features-list">
                    <li>
                      <strong>Перенесення/відміна:</strong> не пізніше ніж за <strong>6 годин</strong> до початку уроку — без згорання
                    </li>
                    <li>Якщо запізнюєшся — повідом, ми збережемо <strong>залишок часу</strong> у межах заняття</li>
                    {/* видалено за твоїм проханням: Графік узгоджується... */}
                  </ul>
                </div>
              </div>

              <div className="price-grid">
                {groups.standard.map((p) => (
                  <PriceCard
                    key={p.id}
                    type={p.type}
                    title={p.name}
                    oldPrice={p.not_true_price}
                    totalPrice={p.total_price ?? p.base_price}
                    pricePerLesson={p.price_per_lesson}
                    discountPercent={p.discount_percent}
                    discountMoney={p.discount_money}
                    lessonsCount={p.lessons_count}
                    lessonDuration={p.lesson_duration}
                    currency={p.currency}
                    onSelect={() => goSelect(p)}
                  />
                ))}
                {groups.standard.length === 0 && <p>Поки що немає стандартних пакетів для дорослих.</p>}
              </div>
            </div>

            {/* PREMIUM */}
            <div className="packages__group">
              <h2 className="packages__group-title">Premium</h2>

              {/* Підзаголовок (Варіант B) */}
              <p className="package-subtitle">
                Максимум уваги до твоїх цілей: <strong>індивідуальний план</strong>,
                пріоритетна підтримка та допомога з кар’єрними матеріалами.
              </p>

              <div className="package-columns">
                <div className="package-col card">
                  <h3 className="h3">Що входить</h3>
                  <ul className="features-list">
                    <li><strong>Усе зі “Стандарт”</strong> + розширений доступ до матеріалів і завдань</li>
                    <li><strong>Індивідуальний навчальний план</strong> з мікро-цілями на тиждень</li>
                    <li><strong>Пріоритетний фідбек</strong> (розбір говоріння/аудіо/писемних робіт)</li>
                    <li>
                      <strong>Допомога з працевлаштуванням:</strong> переклад і редагування резюме, профілів
                      (LinkedIn), мотиваційних/супровідних листів
                    </li>
                    <li><strong>Підготовка до співбесід:</strong> типові питання, мовні скрипти, рольові інтерв’ю</li>
                  </ul>
                </div>

                <div className="package-col card">
                  <h3 className="h3">Умови</h3>
                  <ul className="features-list">
                    <li>
                      <strong>Перенесення/відміна:</strong> не пізніше ніж за <strong>1 годину</strong> до початку — без згорання
                    </li>
                    {/* видалено за твоїм проханням: Пріоритетне бронювання... */}
                    {/* видалено за твоїм проханням: Можливість оперативного мікро-перенесення... */}
                  </ul>
                </div>
              </div>

              <div className="price-grid">
                {groups.premium.map((p) => (
                  <PriceCard
                    key={p.id}
                    type={p.type}
                    title={p.name}
                    oldPrice={p.not_true_price}
                    totalPrice={p.total_price ?? p.base_price}
                    pricePerLesson={p.price_per_lesson}
                    discountPercent={p.discount_percent}
                    discountMoney={p.discount_money}
                    lessonsCount={p.lessons_count}
                    lessonDuration={p.lesson_duration}
                    currency={p.currency}
                    onSelect={() => goSelect(p)}
                  />
                ))}
                {groups.premium.length === 0 && <p>Преміум-пакетів для дорослих поки немає.</p>}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
