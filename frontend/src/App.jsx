import { useEffect } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import ScrollToTop from "./components/ScrollToTop.jsx";
import AuroraBackground from "./components/AuroraBackground.jsx";
import StickyCta from "./components/StickyCta.jsx";

import Home from "./pages/Home.jsx";
import Packages from "./pages/Packages.jsx";
import Programs from "./pages/Programs.jsx";
import About from "./pages/About.jsx";
import Contacts from "./pages/Contacts.jsx";
import VerifyCertificate from "./pages/VerifyCertificate.jsx";
import LevelTest from "./pages/LevelTest.jsx";
import Offer from "./pages/Offer.jsx";
import Privacy from "./pages/Privacy.jsx";
import NotFound from "./pages/NotFound.jsx";
import Checkout from "./pages/Checkout.jsx";
import PaymentResult from "./pages/PaymentResult.jsx";
import AdminApp from "./admin/AdminApp.jsx";
import { trackVisit } from "./lib/track.js";

/** Ім'я сторінки для CSS: body[data-page="contacts"] тощо.
 *  Потрібне, щоб приховувати чат Tidio там, де він заважає формі. */
const PAGE_NAMES = {
  "/": "home",
  "/programs": "programs",
  "/packages": "packages",
  "/about": "about",
  "/contacts": "contacts",
  "/verify-certificate": "certificate",
  "/offer": "legal",
  "/privacy": "legal",
  "/checkout": "checkout",
  "/payment/result": "checkout",
};

function usePageName() {
  const { pathname } = useLocation();
  useEffect(() => {
    document.body.dataset.page = PAGE_NAMES[pathname] ?? "other";
  }, [pathname]);
}

/** Власний лічильник візитів. Кабінет менеджера не рахуємо:
 *  інакше робота команди потрапила б у статистику відвідувань. */
function useVisitTracking() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pathname.startsWith("/admin")) return;
    trackVisit(pathname);
  }, [pathname]);
}

export default function App() {
  usePageName();
  useVisitTracking();

  return (
    <>
      <AuroraBackground />
      <ScrollToTop />
      <Navbar />

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/programs" element={<Programs />} />
          <Route path="/packages" element={<Packages />} />
          <Route path="/about" element={<About />} />
          <Route path="/contacts" element={<Contacts />} />
          <Route path="/verify-certificate" element={<VerifyCertificate />} />
          <Route path="/level-test" element={<LevelTest />} />
          <Route path="/offer" element={<Offer />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route path="/payment/result" element={<PaymentResult />} />
          {/* Кабінет менеджера. Вкладені маршрути — усередині AdminApp. */}
          <Route path="/admin/*" element={<AdminApp />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <Footer />
      <StickyCta />
    </>
  );
}
