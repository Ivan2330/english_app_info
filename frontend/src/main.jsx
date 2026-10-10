import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";

// Глобальні стилі
import "../styles/variables.css";
import "../styles/global.css";
import "../styles/sections.css";
import "../styles/home.css";
import "../styles/navbar.css";
import "../styles/footer.css";
import "../styles/tabs.css";
import "../styles/price-card.css";
import "../styles/packages.css";
import "../styles/builder.css";
import "../styles/about.css";
import "../styles/contacts.css";
import "../styles/certificates.css";
import "../styles/leveltest.css";
import "../styles/legal.css";
import "../styles/admin.css";

function Root() {
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
