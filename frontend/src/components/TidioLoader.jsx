import { useEffect } from "react";

const TIDIO_ID = import.meta.env.VITE_TIDIO_PUBLIC_KEY;

export default function TidioLoader() {
  useEffect(() => {
    if (!TIDIO_ID) {
      // eslint-disable-next-line no-console
      console.warn("VITE_TIDIO_PUBLIC_KEY is not set. Tidio won't load.");
      return;
    }

    // не дублювати, якщо вже додано
    if (document.getElementById("tidio-script")) return;

    const s = document.createElement("script");
    s.id = "tidio-script";
    s.src = `https://code.tidio.co/${TIDIO_ID}.js`;
    s.async = true;

    // Якщо хочеш вантажити чат тільки за згоди cookies — зроби перевірку тут
    // if (!userConsentedTo('marketing')) return;

    document.body.appendChild(s);

    return () => {
      // Видаляти скрипт зазвичай НЕ потрібно (чат глобальний).
      // Якщо робиш SPA unmount/mount — можеш сховати віджет через API.
    };
  }, []);

  return null;
}
