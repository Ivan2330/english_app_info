import React, { useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { TIDIO_KEY } from "./config.js";
// +++ add these 3 lines at the very top:
import "../styles/variables.css";
import "../styles/global.css";
import "../styles/home.css";
import "../styles/navbar.css";
import "../styles/footer.css";
import "../styles/tabs.css";
import "../styles/price-card.css";
import "../styles/packages.css";
import "../styles/about.css";
import "../styles/contacts.css";
import "../styles/certificates.css";

function Root() {
  useEffect(() => {
    if (TIDIO_KEY) {
      const s = document.createElement("script");
      s.src = `https://code.tidio.co/${TIDIO_KEY}.js`;
      s.async = true;
      document.body.appendChild(s);
    }
  }, []);

  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
