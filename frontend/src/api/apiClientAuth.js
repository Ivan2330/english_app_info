// src/api/apiClientAuth.js
import axios from "axios";
import { API_URL } from "../config";

const apiAuth = axios.create({
  baseURL: API_URL,
  withCredentials: true, // ✅ куки для /api/admin/**
});

apiAuth.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error("API auth error:", err?.response || err);
    return Promise.reject(err);
  }
);

export default apiAuth;
