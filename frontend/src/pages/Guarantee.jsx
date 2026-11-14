import LegalPage from "./LegalPage.jsx";
import { GUARANTEE_SECTIONS } from "../lib/legal/guarantee.js";

export default function Guarantee() {
  return (
    <LegalPage
      crumb="Гарантія результату"
      title="Умови гарантії результату"
      lead="Гарантія діє на курсах підготовки до НМТ та IELTS."
      sections={GUARANTEE_SECTIONS}
      showSeller={false}
    />
  );
}
