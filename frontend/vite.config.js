import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Адреса бекенду для dev-проксі. Якщо порт 8000 зайнятий і ти підняв
// контейнер на іншому (BACKEND_PORT=8001), пропиши той самий у
// frontend/.env.local:  VITE_API_URL=http://localhost:8001
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // 127.0.0.1, а НЕ localhost. Node 18+ резолвить "localhost" за порядком,
  // який повертає система, і на Windows це зазвичай спершу IPv6 (::1).
  // Docker Desktop публікує порт на IPv4, тож проксі не достукується
  // й Vite віддає браузеру 500 — при цьому в логах бекенда ПОРОЖНЬО,
  // бо запит до нього не дійшов. Явна адреса знімає питання.
  const apiTarget = env.VITE_API_URL || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          // Без цього Vite мовчки віддає 500, і причину видно лише
          // в мережі браузера. Друкуємо її в термінал, де запущено dev.
          configure: (proxy) => {
            proxy.on("error", (err) => {
              console.error(`[proxy] не вдалося звернутись до ${apiTarget}:`, err.message);
            });
          },
        },
        // PDF сертифікатів лежать на бекенді. Без цього правила посилання
        // «Завантажити сертифікат» у dev вело б на Vite, який про них не знає.
        "/static": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
