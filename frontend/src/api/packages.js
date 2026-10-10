// src/api/packages.js
import apiPublic from "./apiClientPublic";

/**
 * Каталог пакетів.
 * @param {object} params - family | audience | format | track | chast | active
 */
export async function fetchPackages(params = {}) {
  const res = await apiPublic.get("/api/packages", { params: { active: 1, ...params } });
  return Array.isArray(res.data) ? res.data : [];
}

export async function fetchPackageBySlug(slug) {
  const res = await apiPublic.get(`/api/packages/${slug}`);
  return res.data;
}

/**
 * Які комбінації осей реально існують у каталозі.
 * Потрібно, щоб конструктор блокував недоступні варіанти,
 * а не показував порожній результат після вибору.
 */
export async function fetchPackageFilters() {
  const res = await apiPublic.get("/api/packages/filters");
  return res.data?.combinations ?? [];
}
