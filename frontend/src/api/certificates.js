// src/api/certificates.js
import apiPublic from "./apiClientPublic";

export async function verifyCertificate(code) {
  const res = await apiPublic.get("/api/certificates/verify", { params: { code } });
  return res.data;
}
