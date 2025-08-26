// src/api/leads.js
import apiPublic from "./apiClientPublic";

export async function createLead(payload) {
  const res = await apiPublic.post("/api/leads", payload);
  return res.data;
}
