import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createLead } from "../api/leads.js";
import { newEventId } from "../lib/attribution.js";

const AUDIENCES = [
  { value: "adults", label: "Дорослий" },
  { value: "teens", label: "Підліток" },
  { value: "kids", label: "Дитина 5–12" },
];
const LEVELS = [
  { value: "unknown", label: "Не знаю" },
  { value: "A1-A2", label: "Початковий (A1–A2)" },
  { value: "B1-B2", label: "Середній (B1–B2)" },
  { value: "C1+", label: "Просунутий (C1 і вище)" },
];
const TIMES = [
  { value: "", label: "Будь-який" },
  { value: "Ранок", label: "Ранок" },
  { value: "День", label: "День" },
  { value: "Вечір", label: "Вечір" },
];

/** Телефон чи Telegram: один рядок, а що саме, визначаємо за змістом. */
export function parseContact(raw) {
  const v = (raw || "").trim();
  const digits = v.replace(/\D/g, "");
  if (digits.length >= 9 && /^[+\d\s()\-.]+$/.test(v)) return { phone: v };
  const handle = v.replace(/^https?:\/\/t\.me\//i, "").replace(/^@/, "");
  if (/^[A-Za-z0-9_]{5,32}$/.test(handle)) return { telegram: `@${handle}` };
  return null;
}

/**
 * Коротка форма запису на пробний. Використовується на /trial (повна)
 * і на першому екрані головної (compact: імʼя, контакт, для кого).
 *
 * event_id створюється тут, ще до відправки: заявка стає ідемпотентною
 * (повторне натискання не дає дубль), а подія Lead у Pixel і в серверному
 * Conversions API підписана одним і тим самим id.
 */
export default function TrialForm({ compact = false, source = "site/trial", id }) {
  const navigate = useNavigate();
  const [f, setF] = useState({ name: "", contact: "", audience: "adults", level: "unknown", time: "", website: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const eventId = useRef(null);
  const set = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    setError("");
    if (!f.name.trim()) return setError("Вкажіть, будь ласка, імʼя");
    const contact = parseContact(f.contact);
    if (!contact) return setError("Вкажіть телефон (наприклад, 050 123 45 67) або Telegram (@нік)");

    setBusy(true);
    eventId.current = eventId.current || newEventId();
    try {
      const res = await createLead({
        kind: "trial",
        name: f.name.trim(),
        ...contact,
        audience: f.audience,
        level: f.level,
        preferred_time: f.time || undefined,
        source,
        website: f.website,          // honeypot: людина його не бачить
        event_id: eventId.current,
      });
      navigate("/thanks", { state: { eventId: res.event_id } });
    } catch (err) {
      const status = err?.response?.status;
      setError(
        status === 429 ? err.response.data.detail
          : !err?.response ? "Немає звʼязку із сервером. Перевірте інтернет і спробуйте ще раз."
          : "Не вдалося надіслати заявку. Спробуйте ще раз або напишіть нам у Telegram чи Instagram."
      );
      setBusy(false);
    }
  }

  return (
    <form className={`tform${compact ? " tform--compact" : ""}`} onSubmit={submit} noValidate id={id}>
      <label className="tform__field">
        <span>Ваше імʼя</span>
        <input name="name" value={f.name} onChange={set("name")} autoComplete="given-name" placeholder="Як до вас звертатись?" />
      </label>

      <label className="tform__field">
        <span>Телефон або Telegram</span>
        <input name="contact" value={f.contact} onChange={set("contact")} inputMode="tel" autoComplete="tel"
               placeholder="050 123 45 67 або @нік" />
      </label>

      <fieldset className="tform__field tform__chips">
        <legend>Для кого</legend>
        <div>
          {AUDIENCES.map((a) => (
            <label key={a.value} className={f.audience === a.value ? "is-on" : ""}>
              <input type="radio" name="audience" value={a.value} checked={f.audience === a.value} onChange={set("audience")} />
              {a.label}
            </label>
          ))}
        </div>
      </fieldset>

      {!compact && (
        <div className="tform__row">
          <label className="tform__field">
            <span>Рівень англійської</span>
            <select value={f.level} onChange={set("level")}>
              {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </label>
          <label className="tform__field">
            <span>Зручний час</span>
            <select value={f.time} onChange={set("time")}>
              {TIMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
        </div>
      )}

      {/* Honeypot: поза екраном, без фокусу. Заповнює його лише бот. */}
      <div className="tform__hp" aria-hidden="true">
        <label>Сайт<input name="website" tabIndex={-1} autoComplete="off" value={f.website} onChange={set("website")} /></label>
      </div>

      {error && <p className="tform__error" role="alert">{error}</p>}

      <button type="submit" className="btn btn-cta tform__submit" disabled={busy}>
        {busy ? "Надсилаємо…" : "Записатись на пробний урок"}
      </button>
      <p className="tform__fine">
        Безкоштовно, 40 хвилин, без картки. Натискаючи кнопку, ви погоджуєтесь на обробку персональних
        даних відповідно до <Link to="/privacy" target="_blank" rel="noopener noreferrer">Політики конфіденційності</Link>.
      </p>
    </form>
  );
}
