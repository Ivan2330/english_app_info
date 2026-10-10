import { useEffect, useRef, useState } from "react";

/**
 * Таймлайн у темному блоці: вертикальна лінія заповнюється при скролі,
 * а номери кроків підсвічуються, коли доходять до середини екрана.
 *
 * Використовується двічі: коротка версія на головній (3 кроки)
 * і повна методика на сторінці «Про школу» (5 кроків).
 */
export default function Timeline({ steps }) {
  const ref = useRef(null);
  const [fill, setFill] = useState(0);
  const [hit, setHit] = useState(new Set());

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setFill(100);
      setHit(new Set(steps.map((_, i) => i)));
      return;
    }

    const update = () => {
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      const p = Math.max(0, Math.min(1, (vh * 0.65 - r.top) / (r.height * 0.85)));
      setFill(p * 100);

      const next = new Set();
      el.querySelectorAll("[data-step]").forEach((node, i) => {
        if (node.getBoundingClientRect().top < vh * 0.68) next.add(i);
      });
      setHit(next);
    };

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [steps]);

  return (
    <div className="tl" ref={ref}>
      <span className="tl__line" aria-hidden="true" />
      <span className="tl__fill" style={{ height: `${fill}%` }} aria-hidden="true" />

      {steps.map((s, i) => (
        <div key={s.title} className={`tl__item${hit.has(i) ? " is-hit" : ""}`} data-step>
          <span className="tl__num">{String(i + 1).padStart(2, "0")}</span>
          <div className="tl__body">
            <h3 className="tl__title">{s.title}</h3>
            <p className="tl__text">{s.text}</p>
            {s.tags?.length ? (
              <div className="tl__tags">
                {s.tags.map((t) => (
                  <span key={t} className="tag">{t}</span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
