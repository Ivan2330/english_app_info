// src/api/leads.js
import apiPublic from "./apiClientPublic";
import { attributionPayload, newEventId } from "../lib/attribution.js";

/**
 * Заявка. До кожної автоматично додається джерело трафіку (UTM, fbclid) і, якщо
 * людина погодилась на cookie, дані для Meta. event_id створюється тут (або
 * приходить із форми): за ним заявка ідемпотентна, ним же підписана подія Lead
 * у Pixel і в Conversions API. Повертається разом із відповіддю.
 */
export async function createLead(payload) {
  const event_id = payload.event_id || newEventId();
  const res = await apiPublic.post("/api/leads", { ...attributionPayload(), ...payload, event_id });
  return { ...res.data, event_id };
}
