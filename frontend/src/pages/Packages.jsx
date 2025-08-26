import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchPackages } from "../api/packages.js";
import PackageTabs from "../components/PackageTabs.jsx";
import PriceCard from "../components/PriceCard.jsx";

// export default function Packages() {
//   const navigate = useNavigate();
//   const [tab, setTab] = useState("adults"); // adults | kids | business | it
//   const [items, setItems] = useState([]);
//   const [loading, setLoading] = useState(false);

//   async function load(audience) {
//     setLoading(true);
//     try {
//       const data = await fetchPackages({ audience, active: 1 });
//       setItems(Array.isArray(data) ? data : []);
//     } catch (e) {
//       console.error(e);
//       setItems([]);
//     } finally {
//       setLoading(false);
//     }
//   }

//   useEffect(() => { load(tab); }, [tab]);

//   const groups = useMemo(() => {
//     const standard = items.filter((i) => i.type === "standard");
//     const premium = items.filter((i) => i.type === "premium");
//     return { standard, premium };
//   }, [items]);

//   return (
//     <section className="packages">
//       <div className="container">
//         <div className="packages__head">
//           <h1 className="section-title">Пакети та ціни</h1>
//           <PackageTabs active={tab} onChange={setTab} />
//         </div>

//         {loading && <p>Завантаження...</p>}

//         {!loading && (
//           <>
//             <div className="packages__group">
//               <h2 className="packages__group-title">Стандартні пакети</h2>
//               <div className="price-grid">
//                 {groups.standard.map((p) => (
//                   <PriceCard
//                     key={p.id}
//                     type={p.type}
//                     title={p.name}
//                     oldPrice={p.not_true_price}
//                     totalPrice={p.total_price ?? p.base_price}
//                     pricePerLesson={p.price_per_lesson}
//                     discountPercent={p.discount_percent}
//                     discountMoney={p.discount_money}
//                     lessonsCount={p.lessons_count}
//                     lessonDuration={p.lesson_duration}
//                     currency={p.currency}
//                     onSelect={() => navigate("/contacts", { state: { selectedPackage: p.slug } })}
//                   />
//                 ))}
//                 {groups.standard.length === 0 && <p>Поки що немає стандартних пакетів для цієї аудиторії.</p>}
//               </div>
//             </div>

//             <div className="packages__group">
//               <h2 className="packages__group-title">Premium</h2>
//               <div className="price-grid">
//                 {groups.premium.map((p) => (
//                   <PriceCard
//                     key={p.id}
//                     type={p.type}
//                     title={p.name}
//                     oldPrice={p.not_true_price}
//                     totalPrice={p.total_price ?? p.base_price}
//                     pricePerLesson={p.price_per_lesson}
//                     discountPercent={p.discount_percent}
//                     discountMoney={p.discount_money}
//                     lessonsCount={p.lessons_count}
//                     lessonDuration={p.lesson_duration}
//                     currency={p.currency}
//                     onSelect={() => navigate("/contacts", { state: { selectedPackage: p.slug } })}
//                   />
//                 ))}
//                 {groups.premium.length === 0 && <p>Преміум-пакетів цієї аудиторії поки немає.</p>}
//               </div>
//             </div>
//           </>
//         )}
//       </div>
//     </section>
//   );
// }

export default function Packages() {
  const navigate = useNavigate();
  // ❗️Залишаємо тільки adults
  const [tab, setTab] = useState("adults"); // було: adults | kids | business | it
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
    const premium = items.filter((i) => i.type === "premium");
    return { standard, premium };
  }, [items]);

  return (
    <section className="packages">
      <div className="container">
        <div className="packages__head">
          <h1 className="section-title">Пакети та ціни</h1>

          {/* ❌ Прибрав вкладки для kids/business/it */}
          {/* <PackageTabs active={tab} onChange={setTab} /> */}
        </div>

        {loading && <p>Завантаження...</p>}

        {!loading && (
          <>
            <div className="packages__group">
              <h2 className="packages__group-title">Стандартні пакети</h2>
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
                    onSelect={() => navigate("/contacts", { state: { selectedPackage: p.slug } })}
                  />
                ))}
                {groups.standard.length === 0 && <p>Поки що немає стандартних пакетів для дорослих.</p>}
              </div>
            </div>

            <div className="packages__group">
              <h2 className="packages__group-title">Premium</h2>
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
                    onSelect={() => navigate("/contacts", { state: { selectedPackage: p.slug } })}
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
