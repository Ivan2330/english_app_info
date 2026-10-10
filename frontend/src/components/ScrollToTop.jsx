import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * React Router зберігає позицію скролу при переході між сторінками.
 * Через це, натиснувши «Обрати» внизу сторінки цін, людина потрапляла
 * на Контакти вже прокрученими до середини форми.
 *
 * ЯКОРІ
 * =====
 *
 * Router не прокручує до `#hash` сам — це робота браузера, і вона
 * виконується лише при першому завантаженні сторінки, а не при
 * клієнтському переході. Тому посилання на кшталт `/offer#p11`
 * (умови повернення) без цієї обробки відкривали б оферту згори,
 * і людина мусила б шукати потрібний розділ очима.
 *
 * Для еквайрингу це не дрібниця: перевіряльник переходить за прямим
 * посиланням на умови оплати й має одразу побачити саме їх.
 *
 * `requestAnimationFrame` потрібен, бо на момент спрацювання ефекту
 * нова сторінка ще не змонтована — `getElementById` повернув би null.
 */
export default function ScrollToTop() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      const id = hash.slice(1);
      const jump = () => {
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
          return true;
        }
        return false;
      };

      // Два кадри: перший — монтування сторінки, другий — поява секцій,
      // які ховаються до спрацювання useReveal.
      requestAnimationFrame(() => {
        if (!jump()) requestAnimationFrame(jump);
      });
      return;
    }

    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }, [pathname, hash]);

  return null;
}
