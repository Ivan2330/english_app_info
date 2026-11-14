import LegalPage from "./LegalPage.jsx";
import { OFFER_SECTIONS, OFFER_REQUISITES, OFFER_TITLE, OFFER_SITE } from "../lib/legal/offer.js";
import { OFFER_REVISION } from "../lib/legal/seller.js";

export default function Offer() {
  return (
    <LegalPage
      crumb="Публічна оферта"
      title={OFFER_TITLE}
      lead={`Редакція від ${OFFER_REVISION}. Сайт: ${OFFER_SITE}.`}
      sections={OFFER_SECTIONS}
      requisites={OFFER_REQUISITES}
      // Реквізити — розділ 15 самої оферти, окремий блок їх лише дублював би.
      showSeller={false}
    />
  );
}
