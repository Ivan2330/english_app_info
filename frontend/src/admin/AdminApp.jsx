import { useEffect, useState } from "react";
import { Routes, Route, NavLink, Navigate, useNavigate } from "react-router-dom";
import { adminMe, adminLogout } from "../api/admin.js";
import AdminLogin from "./AdminLogin.jsx";
import Dashboard from "./Dashboard.jsx";
import LeadsPage from "./LeadsPage.jsx";
import OrdersPage from "./OrdersPage.jsx";
import CertificatesPage from "./CertificatesPage.jsx";

/**
 * Кабінет менеджера.
 *
 * Живе під /admin у тому самому застосунку, що й сайт — окремої збірки
 * не заводимо: код спільний, компонентів мало, а два деплої на один
 * невеликий проєкт коштують дорожче, ніж дають.
 *
 * Візуально навмисно НЕ схожий на сайт: темний, щільний, без анімацій.
 * Це робоче середовище, в якому людина проводить години, а не вітрина.
 * Aurora Glass тут заважав би читати таблиці.
 */
export default function AdminApp() {
  const [admin, setAdmin] = useState(null);
  const [checking, setChecking] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    adminMe()
      .then(setAdmin)
      .catch(() => setAdmin(null))
      .finally(() => setChecking(false));
  }, []);

  // Тема вмикається на body, щоб перекрити глобальні стилі сайту
  useEffect(() => {
    document.body.classList.add("admin-mode");
    return () => document.body.classList.remove("admin-mode");
  }, []);

  async function onLogout() {
    try { await adminLogout(); } catch { /* вийти маємо в будь-якому разі */ }
    setAdmin(null);
    navigate("/admin", { replace: true });
  }

  if (checking) {
    return <div className="adm-boot">Перевіряємо сесію…</div>;
  }

  if (!admin) {
    return <AdminLogin onSuccess={setAdmin} />;
  }

  return (
    <div className="adm">
      <aside className="adm__side">
        <div className="adm__brand">
          Prime Academy
          <span>кабінет менеджера</span>
        </div>

        <nav className="adm__nav">
          <NavLink to="/admin" end className="adm__link">Дашборд</NavLink>
          <NavLink to="/admin/leads" className="adm__link">Заявки</NavLink>
          <NavLink to="/admin/orders" className="adm__link">Замовлення</NavLink>
          <NavLink to="/admin/certificates" className="adm__link">Сертифікати</NavLink>
        </nav>

        <div className="adm__user">
          <span title={admin.email}>{admin.email}</span>
          <button type="button" onClick={onLogout}>Вийти</button>
        </div>
      </aside>

      <main className="adm__main">
        <Routes>
          <Route index element={<Dashboard />} />
          <Route path="leads" element={<LeadsPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="certificates" element={<CertificatesPage />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </main>
    </div>
  );
}
