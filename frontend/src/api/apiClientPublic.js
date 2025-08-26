// src/api/apiClientPublic.js
import axios from "axios";
import { API_URL } from "../config";

const apiPublic = axios.create({
  baseURL: API_URL,
  withCredentials: false, // ✅ жодних куків
});

apiPublic.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error("API public error:", err?.response || err);
    return Promise.reject(err);
  }
);

export default apiPublic;
