// src/api/packages.js
import apiPublic from "./apiClientPublic";

export async function fetchPackages(params = {}) {
  const res = await apiPublic.get("/api/packages", { params });
  return res.data;
}

export async function fetchPackageBySlug(slug) {
  const res = await apiPublic.get(`/api/packages/${slug}`);
  return res.data;
}
