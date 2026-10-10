// src/api/admin.js
//
// Усі виклики кабінету менеджера. Авторизація — HttpOnly-кука,
// тому токен ніде в JS не зберігається й не може витекти через XSS.
import apiAuth from "./apiClientAuth";

/* ---------- сесія ---------- */
export async function adminLogin(email, password) {
  const res = await apiAuth.post("/api/admin/login", { email, password });
  return res.data;
}

export async function adminLogout() {
  const res = await apiAuth.post("/api/admin/logout");
  return res.data;
}

export async function adminMe() {
  const res = await apiAuth.get("/api/admin/me");
  return res.data;
}

/* ---------- дашборд ---------- */
export async function adminStats(days = 30) {
  const res = await apiAuth.get("/api/admin/stats", { params: { days } });
  return res.data;
}

/* ---------- заявки ---------- */
export async function adminGetLeads(params = {}) {
  const res = await apiAuth.get("/api/admin/leads", { params });
  return res.data;
}

export async function adminUpdateLead(id, data) {
  const res = await apiAuth.patch(`/api/admin/leads/${id}`, data);
  return res.data;
}

/* ---------- замовлення ---------- */
export async function adminGetOrders(params = {}) {
  const res = await apiAuth.get("/api/admin/orders", { params });
  return res.data;
}

export async function adminGetOrder(publicId) {
  const res = await apiAuth.get(`/api/admin/orders/${publicId}`);
  return res.data;
}

export async function adminUpdateOrder(publicId, data) {
  const res = await apiAuth.patch(`/api/admin/orders/${publicId}`, data);
  return res.data;
}

export async function adminManualPayment(publicId, data) {
  const res = await apiAuth.post(`/api/admin/orders/${publicId}/manual-payment`, data);
  return res.data;
}

export async function adminSetDiscount(publicId, kinds) {
  const res = await apiAuth.post(`/api/admin/orders/${publicId}/discount`, { kinds });
  return res.data;
}

/* ---------- сертифікати ---------- */
export async function adminGetCertificates(params = {}) {
  const res = await apiAuth.get("/api/admin/certificates", { params });
  return res.data;
}

export async function adminCertStats() {
  const res = await apiAuth.get("/api/admin/certificates/stats");
  return res.data;
}

export async function adminCreateCertificate(data) {
  const res = await apiAuth.post("/api/admin/certificates", data);
  return res.data;
}

export async function adminUpdateCertificate(id, data) {
  const res = await apiAuth.patch(`/api/admin/certificates/${id}`, data);
  return res.data;
}

export async function adminRevokeCertificate(id, reason) {
  const res = await apiAuth.post(`/api/admin/certificates/${id}/revoke`, { reason });
  return res.data;
}

export async function adminRestoreCertificate(id) {
  const res = await apiAuth.post(`/api/admin/certificates/${id}/restore`);
  return res.data;
}

export async function adminDeleteCertificate(id) {
  const res = await apiAuth.delete(`/api/admin/certificates/${id}`);
  return res.data;
}

export async function adminGenerateCertPdf(id) {
  const res = await apiAuth.post(`/api/admin/certificates/${id}/pdf`);
  return res.data;
}
