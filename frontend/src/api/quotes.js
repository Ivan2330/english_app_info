// src/api/quotes.js
import apiPublic from "./apiClientPublic";

/**
 * Заявка на розрахунок (діти, корпоратив).
 * Відповідь містить лише { ok: true } — цін користувач не бачить.
 */
export async function createQuoteRequest(payload) {
  const res = await apiPublic.post("/api/quote-requests", payload);
  return res.data;
}
