import { useCallback, useEffect, useState } from "react";
import { Routes, Route, NavLink, Navigate, useLocation, useNavigate } from "react-router-dom";
import { adminMe, adminLogout } from "../api/admin.js";
import { getCounters } from "../api/workspace.js";
import AdminLogin from "./AdminLogin.jsx";
import ChangePassword from "./ChangePassword.jsx";
import Dashboard from "./Dashboard.jsx";
import LeadsPage from "./LeadsPage.jsx";
import OrdersPage from "./OrdersPage.jsx";
import QuotesPage from "./QuotesPage.jsx";
import CertificatesPage from "./CertificatesPage.jsx";
import HomePage from "./HomePage.jsx";
import TasksPage from "./TasksPage.jsx";
import NotesPage from "./NotesPage.jsx";
import ReportsPage from "./ReportsPage.jsx";
import TeamPage from "./TeamPage.jsx";
import DailyPage from "./DailyPage.jsx";
import IdeasPage from "./IdeasPage.jsx";
import CreativesPage from "./CreativesPage.jsx";
import AppsPage from "./AppsPage.jsx";
import { AdminContext } from "./ws/ui.jsx";
import Appearance, { useAppearance } from "./ws/Appearance";
import "../../styles/admin-tokens.css";

/**
 * Робочий простір школи.
 *
 * Живе під /admin у тому самому застосунку, що й сайт. Візуально навмисно
 * не схожий на сайт: темний і спокійний, бо тут працюють годинами.
 *
 * Меню будується з `sections`, які віддає бекенд. Але це лише зручність:
 * доступ до кожного розділу перевіряє бекенд, і набрана руками адреса
 * закритого розділу дасть 403, а не дані.
 */

// Порядок і групи меню. section: null — відкрито завжди.
const MENU = [
  { group: "Робота", items: [
    { to: "/admin", label: "Головна", end: true, section: null },
    { to: "/admin/tasks", label: "Завдання", section: "tasks", counter: "tasks" },
    { to: "/admin/reports", label: "Звіти", section: "reports", counter: "reports" },
    { to: "/admin/daily", label: "Звіт дня", section: "daily", counter: "daily" },
    { to: "/admin/ideas", label: "Ідеї", section: "ideas" },
    { to: "/admin/creatives", label: "Креативи", section: "creatives" },
    { to: "/admin/apps", label: "Апки", section: "apps" },
    { to: "/admin/notes", label: "Нотатки", section: null },
  ] },
  { group: "Сайт", items: [
    { to: "/admin/stats", label: "Статистика сайту", section: "dashboard" },
    { to: "/admin/leads", label: "Заявки", section: "leads", counter: "leads" },
    { to: "/admin/quotes", label: "Розрахунки", section: "quotes" },
    { to: "/admin/orders", label: "Замовлення", section: "orders" },
    { to: "/admin/certificates", label: "Сертифікати", section: "certificates" },
  ] },
];

const PAGES = {
  tasks: TasksPage, reports: ReportsPage, daily: DailyPage, ideas: IdeasPage, creatives: CreativesPage, apps: AppsPage, dashboard: Dashboard, leads: LeadsPage,
  quotes: QuotesPage, orders: OrdersPage, certificates: CertificatesPage,
};
const PATHS = { tasks: "tasks", reports: "reports", daily: "daily", ideas: "ideas", creatives: "creatives", apps: "apps", dashboard: "stats", leads: "leads", quotes: "quotes",
                orders: "orders", certificates: "certificates" };
const NAV_ICONS = { home: "⌂", tasks: "☑", reports: "▤", daily: "▦", notes: "✎", ideas: "✧",
  creatives: "▧", apps: "▥", dashboard: "▥", leads: "✉", quotes: "₴", orders: "▣", certificates: "☆", team: "♙" };

export default function AdminApp() {
  const [admin, setAdmin] = useState(null);
  const [checking, setChecking] = useState(true);
  const [counters, setCounters] = useState({});
  const [menuOpen, setMenuOpen] = useState(false);
  const appearance = useAppearance(admin?.id);
  const navigate = useNavigate();
  const location = useLocation();

  const refreshMe = useCallback(() => adminMe().then(setAdmin).catch(() => setAdmin(null)), []);

  useEffect(() => { refreshMe().finally(() => setChecking(false)); }, [refreshMe]);

  useEffect(() => {
    document.body.classList.add("admin-mode");
    return () => document.body.classList.remove("admin-mode");
  }, []);

  // Сесія завершилась (або пароль треба змінити) — бекенд каже це будь-якому запиту.
  useEffect(() => {
    const expired = () => setAdmin(null);
    const mustChange = () => setAdmin((a) => (a ? { ...a, must_change_password: true } : a));
    window.addEventListener("admin:session-expired", expired);
    window.addEventListener("admin:must-change-password", mustChange);
    return () => {
      window.removeEventListener("admin:session-expired", expired);
      window.removeEventListener("admin:must-change-password", mustChange);
    };
  }, []);

  // Лічильники непрочитаного: при зміні сторінки і раз на хвилину.
  const refreshCounters = useCallback(() => {
    if (!admin || admin.must_change_password) return;
    getCounters().then(setCounters).catch(() => {});
  }, [admin]);
  useEffect(() => { refreshCounters(); }, [refreshCounters, location.pathname]);
  useEffect(() => {
    const t = setInterval(refreshCounters, 60_000);
    return () => clearInterval(t);
  }, [refreshCounters]);

  useEffect(() => { setMenuOpen(false); }, [location.pathname]);

  async function onLogout() {
    try { await adminLogout(); } catch { /* вийти маємо в будь-якому разі */ }
    setAdmin(null);
    navigate("/admin", { replace: true });
  }

  if (checking) return <div className="adm-boot">Перевіряємо вхід…</div>;
  if (!admin) return <AdminLogin onSuccess={setAdmin} />;
  if (admin.must_change_password) {
    return <ChangePassword forced admin={admin} onDone={setAdmin} onLogout={onLogout} />;
  }

  const open = new Set(admin.sections);
  const isOwner = admin.role === "owner";
  const ctx = { ...admin, refreshCounters, refreshMe };

  return (
    <AdminContext.Provider value={ctx}>
      <div className={`adm ws${menuOpen ? " is-menu-open" : ""}`}>
        <header className="ws-topbar">
          <span className="ws-topbar__brand">Prime Academy</span>
          <button type="button" className="ws-btn" aria-expanded={menuOpen} onClick={() => setMenuOpen((v) => !v)}>
            {menuOpen ? "Закрити меню" : "Меню"}
            {!menuOpen && (counters.tasks || 0) + (counters.reports || 0) + (counters.daily || 0) + (counters.leads || 0) > 0 && <i className="ws-dot" />}
          </button>
        </header>

        <aside className="adm__side ws-side">
          <div className="adm__brand">
            Prime Academy
            <span>робочий простір</span>
          </div>

          <nav className="ws-nav" aria-label="Розділи кабінету">
            {MENU.map((g) => {
              const items = g.items.filter((i) => i.section === null || open.has(i.section));
              if (!items.length) return null;
              return (
                <div key={g.group} className="ws-nav__group">
                  <span className="ws-nav__title">{g.group}</span>
                  {items.map((i) => (
                    <NavLink key={i.to} to={i.to} end={i.end} className="adm__link ws-nav__link">
                      <span className="ws-nav__caption"><span className="ws-nav__icon" aria-hidden="true">
                        {NAV_ICONS[i.section || (i.end ? "home" : "notes")]}
                      </span>{i.label}</span>
                      {i.counter && counters[i.counter] > 0 && (
                        <span className="ws-badge" aria-label={`нових: ${counters[i.counter]}`}>{counters[i.counter]}</span>
                      )}
                    </NavLink>
                  ))}
                </div>
              );
            })}
            {isOwner && (
              <div className="ws-nav__group">
                <span className="ws-nav__title">Керування</span>
                <NavLink to="/admin/team" className="adm__link ws-nav__link"><span className="ws-nav__caption">
                  <span className="ws-nav__icon" aria-hidden="true">{NAV_ICONS.team}</span>Команда
                </span></NavLink>
              </div>
            )}
          </nav>

          <div className="ws-user">
            <b>{admin.name}</b>
            <span>{isOwner ? "Власник" : "Адміністратор"}</span>
            <Appearance {...appearance} />
            <NavLink to="/admin/password" className="ws-user__link">Змінити пароль</NavLink>
            <button type="button" className="ws-btn" onClick={onLogout}>Вийти</button>
          </div>
        </aside>

        <main className="adm__main ws-main">
          <Routes>
            <Route index element={<HomePage />} />
            <Route path="notes" element={<NotesPage />} />
            <Route path="password" element={<ChangePassword admin={admin} onDone={setAdmin} />} />
            {Object.entries(PAGES).map(([section, Page]) => (
              <Route key={section} path={`${PATHS[section]}/*`}
                     element={open.has(section) ? <Page /> : <Closed />} />
            ))}
            <Route path="team" element={isOwner ? <TeamPage /> : <Closed />} />
            <Route path="*" element={<Navigate to="/admin" replace />} />
          </Routes>
        </main>
      </div>
    </AdminContext.Provider>
  );
}

function Closed() {
  return (
    <div className="ws-empty">
      <b>Цей розділ для вас вимкнено</b>
      <p>Доступ до розділів вмикає власник у меню «Команда». Якщо він вам потрібен, напишіть власнику.</p>
    </div>
  );
}
