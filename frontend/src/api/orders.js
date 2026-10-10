// src/api/orders.js
import apiPublic from "./apiClientPublic";

export async function createOrder(data) {
  const res = await apiPublic.post("/api/orders", data);
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
