import LegalPage from "./LegalPage.jsx";
import { PRIVACY_SECTIONS } from "../lib/legal/privacy.js";

export default function Privacy() {
  return (
    <LegalPage
      crumb="Конфіденційність"
      title="Політика конфіденційності"
      lead="Які дані ми збираємо, навіщо, кому передаємо і як довго зберігаємо. Написано звичайною мовою — юридичні формулювання тут нічого не додали б."
      sections={PRIVACY_SECTIONS}
    />
  );
}
