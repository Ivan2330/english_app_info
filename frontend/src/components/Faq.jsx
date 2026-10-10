import { useRef, useState } from "react";

/**
 * Акордеон питань. items — масив пар [питання, відповідь].
 * Відкритий лише один пункт: так людина читає, а не сканує стіну тексту.
 */
export default function Faq({ items }) {
  const [open, setOpen] = useState(null);
  const bodies = useRef({});

  return (
    <div className="faq">
      {items.map(([q, a], i) => {
        const isOpen = open === i;
        return (
          <div key={q} className={`faq__item${isOpen ? " is-open" : ""}`}>
            <button
              type="button"
              className="faq__q"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : i)}
            >
              {q}
              <span className="faq__icon" aria-hidden="true">+</span>
            </button>
            <div
              className="faq__a"
              ref={(el) => (bodies.current[i] = el)}
              style={{ maxHeight: isOpen ? `${bodies.current[i]?.scrollHeight ?? 400}px` : 0 }}
            >
              <p>{a}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
