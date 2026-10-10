import LegalPage from "./LegalPage.jsx";
import { OFFER_SECTIONS } from "../lib/legal/offer.js";

export default function Offer() {
  return (
    <LegalPage
      crumb="Публічна оферта"
      title="Договір публічної оферти"
      lead="Умови, на яких ми надаємо послуги. Оплачуючи пакет, ви приймаєте цей договір — тому варто прочитати хоча б розділи про перенесення занять, строк дії пакета та повернення коштів."
      sections={OFFER_SECTIONS}
    />
  );
}
