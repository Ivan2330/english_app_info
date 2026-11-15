// src/api/apiClientAuth.js
//
// Клієнт кабінету. Сесія — httpOnly-кука, JS її не бачить.
// CSRF: бекенд кладе випадковий рядок в окрему куку admin_csrf (її JS
// прочитати може) і вимагає той самий рядок у заголовку X-CSRF-Token на кожну
// зміну. Чужий сайт цієї куки не прочитає, тож і запит від нашого імені не зробить.
import axios from "axios";
import { API_URL } from "../config";

const CSRF_COOKIE = "admin_csrf";

function readCookie(name) {
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return hit ? decodeURIComponent(hit.slice(name.length + 1)) : "";
}

const apiAuth = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

apiAuth.interceptors.request.use((config) => {
  const method = (config.method || "get").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = readCookie(CSRF_COOKIE);
    if (token) config.headers["X-CSRF-Token"] = token;
  }
  return config;
});

// Сесія закінчилась (12 годин без активності, пароль змінили, акаунт вимкнули) —
// кабінет слухає цю подію й показує форму входу замість купи помилок.
apiAuth.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    const url = err?.config?.url || "";
    if (status === 401 && !url.endsWith("/login") && !url.endsWith("/me")) {
      window.dispatchEvent(new Event("admin:session-expired"));
    }
    if (status === 403 && err?.response?.data?.detail === "must_change_password") {
      window.dispatchEvent(new Event("admin:must-change-password"));
    }
    return Promise.reject(err);
  }
);

/** Текст помилки з відповіді бекенда — вже українською. */
export function errorText(err, fallback = "Не вдалося виконати дію. Спробуйте ще раз.") {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d !== "csrf") return d;
  if (Array.isArray(d)) return "Перевірте заповнені поля.";
  if (err?.response?.status === 413) return "Файл завеликий.";
  if (!err?.response) return "Немає звʼязку із сервером. Перевірте інтернет.";
  return fallback;
}

export default apiAuth;
