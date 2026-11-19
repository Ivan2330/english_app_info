import { useLayoutEffect, useState } from "react";

const themes = { classic: "Поточна", nord: "Nord", school: "Prime Academy" };
const defaultAppearance = { theme: "classic", mode: "light" };
const storageKey = (id) => `prime-admin-appearance:${id}`;

function readAppearance(id) {
  if (!id) return defaultAppearance;
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey(id)));
    if (Object.hasOwn(themes, saved?.theme) && ["light", "dark"].includes(saved.mode)) return saved;
  } catch { /* Браузер може заборонити локальне сховище. */ }
  return defaultAppearance;
}

export function useAppearance(id) {
  const [appearance, setAppearance] = useState(defaultAppearance);
  useLayoutEffect(() => { setAppearance(readAppearance(id)); }, [id]);
  useLayoutEffect(() => {
    if (id && appearance.theme !== "classic") document.body.dataset.adminTheme = `${appearance.theme}-${appearance.mode}`;
    else delete document.body.dataset.adminTheme;
    return () => { delete document.body.dataset.adminTheme; };
  }, [id, appearance]);

  function change(patch) {
    const value = { ...appearance, ...patch };
    setAppearance(value);
    try { localStorage.setItem(storageKey(id), JSON.stringify(value)); }
    catch { /* Тема діє до закриття сторінки. */ }
  }
  return { appearance, change };
}

export default function Appearance({ appearance, change }) {
  return <details className="ws-appearance">
    <summary>Оформлення</summary>
    <label className="ws-field"><span className="ws-field__label">Тема кабінету</span>
      <select aria-label="Тема кабінету" className="ws-input" value={appearance.theme} onChange={(e) => change({ theme: e.target.value })}>
        {Object.entries(themes).map(([key, label]) => <option value={key} key={key}>{label}</option>)}
      </select>
    </label>
    {appearance.theme !== "classic" && <div className="ws-seg" aria-label="Кольоровий режим" role="group">
      {Object.entries({ light: "Світла", dark: "Темна" }).map(([mode, label]) => <button type="button" key={mode}
        onClick={() => change({ mode })} aria-pressed={appearance.mode === mode} className={appearance.mode === mode ? "is-on" : ""}>{label}</button>)}
    </div>}
  </details>;
}
