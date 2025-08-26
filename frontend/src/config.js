// src/config.js
export const API_URL =
  import.meta.env.PROD
    ? "https://my-prime-academy.com"   // прод (краще проксити /api цим же доменом)
    : "http://localhost:8000";         // дев

export const TIDIO_KEY = import.meta.env.VITE_TIDIO_PUBLIC_KEY || "";
