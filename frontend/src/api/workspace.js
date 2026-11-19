// src/api/workspace.js — робочий простір кабінету: команда, завдання, нотатки, звіти,
// коментарі, оцінки, файли. Доступ перевіряє бекенд; тут лише виклики.
import apiAuth from "./apiClientAuth";

const get = (url, params) => apiAuth.get(url, { params }).then((r) => r.data);
const post = (url, data) => apiAuth.post(url, data).then((r) => r.data);
const patch = (url, data) => apiAuth.patch(url, data).then((r) => r.data);
const put = (url, data) => apiAuth.put(url, data).then((r) => r.data);
const del = (url, params) => apiAuth.delete(url, { params }).then((r) => r.data);

/* ---------- сесія ---------- */
export const changePassword = (current_password, new_password) =>
  post("/api/admin/change-password", { current_password, new_password });

/* ---------- головна ---------- */
export const getHome = () => get("/api/admin/home");
export const getCounters = () => get("/api/admin/counters");
export const getPeople = () => get("/api/admin/people");

/* ---------- команда (owner) ---------- */
export const getTeam = () => get("/api/admin/team");
export const createMember = (data) => post("/api/admin/team", data);
export const updateMember = (id, data) => patch(`/api/admin/team/${id}`, data);
export const resetMemberPassword = (id) => post(`/api/admin/team/${id}/reset-password`);
export const getAudit = (params) => get("/api/admin/audit", params);

/* ---------- завдання ---------- */
export const getTasks = (params) => get("/api/admin/tasks", params);
export const getTask = (id) => get(`/api/admin/tasks/${id}`);
export const createTask = (data) => post("/api/admin/tasks", data);
export const updateTask = (id, data) => patch(`/api/admin/tasks/${id}`, data);
export const deleteTask = (id) => del(`/api/admin/tasks/${id}`);

/* ---------- нотатки ---------- */
export const getNotes = (params) => get("/api/admin/notes", params);
export const createNote = (data) => post("/api/admin/notes", data);
export const updateNote = (id, data) => patch(`/api/admin/notes/${id}`, data);
export const deleteNote = (id) => del(`/api/admin/notes/${id}`);

/* ---------- звіти ---------- */
export const getReports = (params) => get("/api/admin/reports", params);
export const getReport = (id) => get(`/api/admin/reports/${id}`);
export const createReport = (data) => post("/api/admin/reports", data);
export const updateReport = (id, data) => patch(`/api/admin/reports/${id}`, data);
export const deleteReport = (id) => del(`/api/admin/reports/${id}`);
export function extractReportText(file) {
  const form = new FormData();
  form.append("file", file);
  return apiAuth.post("/api/admin/reports/extract", form).then((r) => r.data);
}

/* ---------- коментарі, оцінки, файли (будь-яка сутність) ---------- */
export const getComments = (entity_type, entity_id) => get("/api/admin/comments", { entity_type, entity_id });
export const addComment = (entity_type, entity_id, body) => post("/api/admin/comments", { entity_type, entity_id, body });
export const editComment = (id, body) => patch(`/api/admin/comments/${id}`, { body });
export const deleteComment = (id) => del(`/api/admin/comments/${id}`);

export const getReviews = (entity_type, entity_id) => get("/api/admin/reviews", { entity_type, entity_id });
export const saveReview = (entity_type, entity_id, score, body) =>
  put("/api/admin/reviews", { entity_type, entity_id, score, body });
export const deleteReview = (entity_type, entity_id) => del("/api/admin/reviews", { entity_type, entity_id });

export const getFiles = (entity_type, entity_id) => get("/api/admin/files", { entity_type, entity_id });
export function uploadFile(entity_type, entity_id, file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  return apiAuth.post("/api/admin/files", form, {
    params: { entity_type, entity_id },
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded / e.total) * 100) : 0),
  }).then((r) => r.data);
}
export const deleteFile = (id) => del(`/api/admin/files/${id}`);

/* ---------- звіт дня ---------- */
export const getDailyMine = () => get("/api/admin/daily-reports/mine");
export const getDailyAuthors = () => get("/api/admin/daily-reports/authors");
export const getDailyReports = (params) => get("/api/admin/daily-reports", params);
export const getDailyReport = (id) => get(`/api/admin/daily-reports/${id}`);
export const createDailyReport = (data) => post("/api/admin/daily-reports", data);
export const updateDailyReport = (id, data) => patch(`/api/admin/daily-reports/${id}`, data);
export const getDailySettings = () => get("/api/admin/daily-reports/settings");
export const setDailyVisibility = (visibility) => put("/api/admin/daily-reports/settings", { visibility });
export const getDailyWeek = (start) => get("/api/admin/daily-reports/week", start ? { start } : undefined);

/* ---------- банк ідей ---------- */
export const getIdeas = (params) => get("/api/admin/ideas", params);
export const createIdea = (data) => post("/api/admin/ideas", data);
export const updateIdea = (id, data) => put(`/api/admin/ideas/${id}`, data);

/* ---------- банк креативів ---------- */
const creative = (id = "") => `/api/admin/creatives${id === "" ? "" : `/${id}`}`;
export const getCreatives = (params) => get(creative(), params);
export const getCreative = (id) => get(creative(id));
export const createCreative = (data) => post(creative(), data);
export const updateCreative = (id, data) => put(creative(id), data);
export const setCreativeSchedule = (id, scheduled_at) => patch(`${creative(id)}/schedule`, { scheduled_at });
export const convertIdea = (id) => post(`${creative()}/from-idea/${id}`);
export const bulkCreatives = (data) => post(`${creative()}/bulk`, data);
export const duplicateCreative = (id) => post(`${creative(id)}/duplicate`);
export const getCreativeRankings = () => get(`${creative()}/rankings`);
export const getCreativeReviews = (id) => get(`${creative(id)}/reviews`);
export const saveCreativeReview = (id, data) => put(`${creative(id)}/reviews`, data);
export const getCreativeUploadSettings = () => get(`${creative()}/settings/upload`);
export const setCreativeUploadSettings = (data) => put(`${creative()}/settings/upload`, data);
export const orderCreativeMedia = (id, ids) => put(`${creative(id)}/media-order`, { ids });
export function saveCreativeMedia(id, mediaId, file, metadata, progress) {
  const form = new FormData();
  form.append("file", file);
  if (metadata.width && metadata.height) {
    form.append("width", metadata.width);
    form.append("height", metadata.height);
  }
  if (metadata.poster) form.append("poster", metadata.poster, "poster.jpg");
  return apiAuth.post(`${creative(id)}/media${mediaId ? `/${mediaId}` : ""}`, form, {
    onUploadProgress: (event) => progress?.(event.total ? Math.round(event.loaded * 100 / event.total) : 0),
  }).then((response) => response.data);
}
