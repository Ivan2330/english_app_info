export default function BonusLessons({ id }) {
  return (
    <aside id={id} className="bonus-lessons" aria-label="Бонусні уроки до пакета">
      <div className="bonus-lessons__amount">До +50% <span>уроків у подарунок</span></div>
      <div className="bonus-lessons__body">
        <h3>Більше уроків у пакеті — більше бонусних занять</h3>
        <p>
          Бонусні уроки додаються до придбаних. Їхня кількість залежить від розміру
          пакета та кількості придбаних пакетів: що більше уроків ви берете,
          то більше отримуєте зверху — до 50% від розміру пакета.
        </p>
        <p className="bonus-lessons__note">Точну кількість бонусних уроків для вашого вибору уточнимо на безкоштовному пробному уроці.</p>
      </div>
    </aside>
  );
}
