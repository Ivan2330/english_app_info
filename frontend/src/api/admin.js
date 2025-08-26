// src/api/admin.js
import apiAuth from "./apiClientAuth";

export async function adminLogin(email, password) {
  const res = await apiAuth.post("/api/admin/login", { email, password });
  return res.data;
}
export async function adminLogout() {
  const res = await apiAuth.post("/api/admin/logout");
  return res.data;
}
export async function adminGetLeads(params = {}) {
  const res = await apiAuth.get("/api/admin/leads", { params });
  return res.data;
}
// ...інші /api/admin/**
