import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Footer from "./components/Footer.jsx";
import TidioIdentify from "./components/TidioIdentify.jsx";

import Home from "./pages/Home.jsx";
import Packages from "./pages/Packages.jsx";
import About from "./pages/About.jsx";
import Contacts from "./pages/Contacts.jsx";
import VerifyCertificate from "./pages/VerifyCertificate.jsx";
import NotFound from "./pages/NotFound.jsx";

export default function App() {
  // TODO: заміни на реальні дані з твого Auth/Context/Redux
  const visitor = {
    distinct_id: "user_123",                 // наприклад, user.id
    name: "Ivan Kozhevnyk",
    email: "ivan@prime-academy.info",
    // phone: "+380XXXXXXXXX",
  };

  return (
    <>
      <Navbar />

      {/* Ідентифікація користувача у Tidio */}
      <TidioIdentify visitor={visitor} />

      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/packages" element={<Packages />} />
          <Route path="/about" element={<About />} />
          <Route path="/contacts" element={<Contacts />} />
          <Route path="/verify-certificate" element={<VerifyCertificate />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>

      <Footer />
    </>
  );
}
