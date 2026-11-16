// src/api/orders.js
import apiPublic from "./apiClientPublic";
import { attributionPayload } from "../lib/attribution.js";

export async function createOrder(data) {
  // Джерело трафіку додається автоматично: потрібне для звіту «з якої реклами оплата»
  const res = await apiPublic.post("/api/orders", { ...attributionPayload(), ...data });
  return res.data;
}

export async function payOrder(publicId, data) {
  const res = await apiPublic.post(`/api/orders/${publicId}/pay`, data);
  return res.data;
}

export async function getOrderState(publicId) {
  const res = await apiPublic.get(`/api/orders/${publicId}/state`);
  return res.data;
}
