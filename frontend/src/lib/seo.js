import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { OG_IMAGE, canonicalFor, metaFor } from "./seoData.js";

function setMeta(selector, attr, key, value) {
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", value);
}

/**
 * Теги title / description / canonical / og / robots для поточного маршруту.
 * Викликається один раз у App: усі сторінки отримують свої теги без окремого коду.
 * Для краулерів без JS ті самі теги вже лежать у HTML (scripts/prerender.mjs).
 */
export function useRouteSeo() {
  const { pathname } = useLocation();
  useEffect(() => {
    const m = metaFor(pathname);
    document.title = m.title;
    setMeta('meta[name="description"]', "name", "description", m.description);
    setMeta('meta[property="og:title"]', "property", "og:title", m.title);
    setMeta('meta[property="og:description"]', "property", "og:description", m.description);
    setMeta('meta[property="og:url"]', "property", "og:url", canonicalFor(m.path));
    setMeta('meta[property="og:image"]', "property", "og:image", OG_IMAGE);

    let link = document.head.querySelector('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("rel", "canonical");
      document.head.appendChild(link);
    }
    link.setAttribute("href", canonicalFor(m.path));

    const robots = document.head.querySelector('meta[name="robots"]');
    if (m.noindex) setMeta('meta[name="robots"]', "name", "robots", "noindex, nofollow");
    else if (robots) robots.remove();
  }, [pathname]);
}
