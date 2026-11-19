import { Link, Route, Routes } from "react-router-dom";
import { Empty } from "./ws/ui";
import PublicationCalendar from "./apps/PublicationCalendar";
import Economy from "./apps/Economy";
import { ContentTemplates, PhraseBank, UtmBuilder } from "./apps/Entries";
import "../../styles/admin-apps.css";

const APPS = [
  { path: "calendar", title: "Календар публікацій", icon: "▦", tone: "purple", detail: "Розклад креативів на тиждень або місяць.", Component: PublicationCalendar },
  { path: "templates", title: "Хештеги й підписи", icon: "#", tone: "pink", detail: "Набори за темами й шаблони із закликом до дії.", Component: ContentTemplates },
  { path: "utm", title: "UTM-генератор", icon: "↗", tone: "blue", detail: "Посилання для реклами й дописів. Історія зберігається.", Component: UtmBuilder },
  { path: "economy", title: "Калькулятор юніт-економіки", icon: "₴", tone: "green", detail: "CAC, маржа, LTV й окупність пакета.", Component: Economy },
  { path: "phrases", title: "Банк фраз", icon: "Aa", tone: "gold", detail: "Приклади англійською для майбутніх креативів.", Component: PhraseBank },
];

export default function AppsPage() {
  return <Routes>
    <Route index element={<div className="ws-stack ws-gap-l"><header className="ws-pagehead"><h1 className="ws-h1">Апки</h1></header>
      <div className="apps-launch">{APPS.map(({ path, title, icon, tone, detail }) => <Link to={path} className="ws-card apps-tile" key={path}>
        <span className={`apps-icon apps-icon--${tone}`} aria-hidden="true">{icon}</span>
        <strong>{title}</strong><span className="ws-muted">{detail}</span>
      </Link>)}</div></div>} />
    {APPS.map(({ path, title, Component }) => <Route key={path} path={path} element={<div className="ws-stack ws-gap-l">
      <header className="ws-pagehead"><Link to="/admin/apps" className="ws-back">← Усі апки</Link><h1 className="ws-h1">{title}</h1></header>
      <Component />
    </div>} />)}
    <Route path="*" element={<Empty title="Апку не знайдено"><Link to="/admin/apps">Відкрити список апок</Link></Empty>} />
  </Routes>;
}
