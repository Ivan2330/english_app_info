export default function PackageTabs({ active, onChange }) {
  return (
    <div className="tabs" role="tablist" aria-label="Категорії пакетів">
      <button className={`tab ${active === "adults" ? "is-active" : ""}`} role="tab" onClick={() => onChange("adults")}>Дорослі</button>
      <button className={`tab ${active === "kids" ? "is-active" : ""}`} role="tab" onClick={() => onChange("kids")}>Діти</button>
      <button className={`tab ${active === "business" ? "is-active" : ""}`} role="tab" onClick={() => onChange("business")}>Бізнес</button>
      <button className={`tab ${active === "it" ? "is-active" : ""}`} role="tab" onClick={() => onChange("it")}>IT</button>
    </div>
  );
}
