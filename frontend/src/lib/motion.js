/**
 * Анімаційна система з макета, перенесена в React.
 *
 * Три ефекти, усі на чистому JS без залежностей:
 *   useReveal   — поява блоків при скролі
 *   useTilt     — 3D-нахил картки за курсором
 *   useMagnetic — кнопка тягнеться до курсора
 *
 * Усі вимикаються, якщо система просить менше руху (prefers-reduced-motion)
 * або пристрій сенсорний — на тачі hover-ефекти лише заважають.
 */

import { useEffect, useRef } from "react";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const hasFinePointer = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(hover: hover) and (pointer: fine)").matches;

/**
 * Показує елементи з атрибутом data-reveal, коли вони входять у в'юпорт.
 * Викликати один раз на сторінці; deps — те, після зміни чого з'являється
 * новий контент (наприклад, завантажені з API картки).
 */
export function useReveal(deps = []) {
  useEffect(() => {
    const nodes = document.querySelectorAll("[data-reveal]:not(.is-in)");
    if (!nodes.length) return;

    const revealAll = () => nodes.forEach((n) => n.classList.add("is-in"));

    if (prefersReducedMotion()) {
      revealAll();
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        });
      },
      // threshold 0.01, а не 0.12: секція з 32 картками вища за екран,
      // і вимагати від неї 12% видимості — означає, що вона зʼявиться
      // лише коли людина прокрутить глибоко всередину. На практиці
      // це читалося як «блок порожній».
      { threshold: 0.01, rootMargin: "0px 0px -40px" }
    );

    nodes.forEach((n) => io.observe(n));

    // ЗАПОБІЖНИК. Анімація появи не має права СХОВАТИ контент назавжди.
    //
    // `[data-reveal]` має opacity: 0 доти, доки не зʼявиться `.is-in`.
    // Якщо спостерігач з будь-якої причини не спрацював — вузол змонтувався
    // після проходу, браузер не підтримує IntersectionObserver, вкладка була
    // у фоні — секція лишається невидимою, займаючи місце. Виглядає це
    // як діра в сторінці, а не як помилка, і шукати причину можна довго.
    //
    // Тому через 1.2 с показуємо все безумовно. Для того, хто вже дивиться
    // сторінку, нічого не зміниться: IO спрацьовує за мілісекунди.
    const failsafe = setTimeout(revealAll, 1200);

    return () => {
      clearTimeout(failsafe);
      io.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** 3D-нахил елемента за положенням курсора. */
export function useTilt({ max = 8, scale = 1.02 } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || !hasFinePointer()) return;

    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      el.style.transform =
        `perspective(900px) rotateX(${-py * max}deg) rotateY(${px * max * 1.2}deg)` +
        ` translateY(-6px) scale(${scale})`;
    };
    const onLeave = () => { el.style.transform = ""; };

    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [max, scale]);

  return ref;
}

/** Кнопка трохи тягнеться за курсором — «магнітний» ефект. */
export function useMagnetic({ strength = 0.22 } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || !hasFinePointer()) return;

    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - r.left - r.width / 2) * strength;
      const dy = (e.clientY - r.top - r.height / 2) * strength * 1.4;
      el.style.transform = `translate(${dx}px, ${dy}px) translateY(-3px)`;
    };
    const onLeave = () => { el.style.transform = ""; };

    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [strength]);

  return ref;
}

/**
 * Плавний лічильник від 0 до значення, коли елемент з'явився на екрані.
 * Використовується у блоці статистики.
 */
export function useCountUp(target, { duration = 1500 } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const value = Number(target);
    if (!Number.isFinite(value)) {
      el.textContent = target ?? "";
      return;
    }

    const decimals = value % 1 !== 0 ? 1 : 0;
    const render = (n) =>
      decimals ? n.toFixed(1) : Math.round(n).toLocaleString("uk-UA");

    if (prefersReducedMotion()) {
      el.textContent = render(value);
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        io.disconnect();
        const t0 = performance.now();
        const step = (t) => {
          const p = Math.min((t - t0) / duration, 1);
          el.textContent = render(value * (1 - Math.pow(1 - p, 3)));
          if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      },
      { threshold: 0.5 }
    );

    io.observe(el);
    return () => io.disconnect();
  }, [target, duration]);

  return ref;
}
