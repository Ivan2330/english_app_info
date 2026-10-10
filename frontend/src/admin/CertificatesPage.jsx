import { useCallback, useEffect, useState } from "react";
import {
  adminGetCertificates, adminCertStats, adminCreateCertificate,
  adminUpdateCertificate, adminRevokeCertificate, adminRestoreCertificate,
  adminDeleteCertificate, adminGenerateCertPdf,
} from "../api/admin.js";

const KINDS = [
  { value: "level", label: "Підвищення рівня" },
  { value: "course", label: "Завершення курсу" },
  { value: "club", label: "Speaking Club" },
  { value: "corporate", label: "Корпоративна програма" },
  { value: "intensive", label: "Інтенсив" },
];
const KIND_LABEL = Object.fromEntries(KINDS.map((k) => [k.value, k.label]));
const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const EMPTY = {
  kind: "course", student_full_name: "", organization: "", course_title: "",
  level_from: "", level_to: "", lessons_count: "", hours: "",
  started_at: "", finished_at: "", valid_until: "",
  teacher_name: "", pdf_url: "",
};

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("uk-UA", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

export default function CertificatesPage() {
  const [items, setItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");     // "" | "active" | "revoked"
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(null);       // null | EMPTY | обʼєкт для правки
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q.trim()) params.q = q.trim();
      if (filter === "revoked") params.revoked = true;
      if (filter === "active") params.revoked = false;
      const [list, s] = await Promise.all([adminGetCertificates(params), adminCertStats()]);
      setItems(list.items || []);
      setStats(s);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [q, filter]);

  useEffect(() => { load(); }, [filter]);   // пошук — по Enter

  async function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);

    // Порожні рядки не шлемо: бекенд відрізняє «не передали» від «очистили»
    const payload = Object.fromEntries(
      Object.entries(form).filter(([, v]) => v !== "" && v != null)
    );

    try {
      if (form.id) {
        await adminUpdateCertificate(form.id, payload);
      } else {
        await adminCreateCertificate(payload);
      }
      setForm(null);
      load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Не вдалося зберегти");
    } finally {
      setBusy(false);
    }
  }

  async function makePdf(cert) {
    try {
      await adminGenerateCertPdf(cert.id);
      load();
    } catch (err) {
      window.alert(err?.response?.data?.detail || "Не вдалося згенерувати PDF");
    }
  }

  async function revoke(cert) {
    const reason = window.prompt(
      `Анулювати сертифікат ${cert.serial_number}?\n` +
      "Вкажіть причину — вона зберігається для внутрішнього розбору\n" +
      "і назовні не показується."
    );
    if (reason === null) return;
    await adminRevokeCertificate(cert.id, reason);
    load();
  }

  async function remove(cert) {
    if (!window.confirm(
      `Видалити запис ${cert.serial_number} назавжди?\n\n` +
      "Видаляти можна тільки те, що ще не пішло людині. Якщо документ уже " +
      "виданий — анулюйте його: у власника лишається PDF, і перевірка має " +
      "показувати «анульовано», а не «не існує»."
    )) return;
    try {
      await adminDeleteCertificate(cert.id);
      load();
    } catch (err) {
      window.alert(err?.response?.data?.detail || "Не вдалося видалити");
    }
  }

  function edit(cert) {
    setForm({
      ...EMPTY,
      ...Object.fromEntries(
        Object.entries(cert).filter(([k]) => k in EMPTY || k === "id")
      ),
      id: cert.id,
      started_at: cert.started_at?.slice(0, 10) || "",
      finished_at: cert.finished_at?.slice(0, 10) || "",
      valid_until: cert.valid_until?.slice(0, 10) || "",
    });
    setError(null);
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <header className="adm-head">
        <h1>Сертифікати</h1>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <form className="adm-search" onSubmit={(e) => { e.preventDefault(); load(); }}>
            <input placeholder="Прізвище або номер" value={q}
                   onChange={(e) => setQ(e.target.value)} />
            <button type="submit">Знайти</button>
          </form>
          <button type="button" className="adm-btn" style={{ marginTop: 0 }}
                  onClick={() => { setForm({ ...EMPTY }); setError(null); }}>
            + Видати сертифікат
          </button>
        </div>
      </header>

      {stats && (
        <div className="adm-cards" style={{ marginBottom: 20 }}>
          <article className="adm-card">
            <p className="adm-card__label">Усього видано</p>
            <div className="adm-card__value">{stats.total}</div>
          </article>
          <article className="adm-card">
            <p className="adm-card__label">Чинних</p>
            <div className="adm-card__value">{stats.active}</div>
          </article>
          <article className="adm-card">
            <p className="adm-card__label">Анульованих</p>
            <div className="adm-card__value">{stats.revoked}</div>
          </article>
          <article className="adm-card">
            <p className="adm-card__label">За останній місяць</p>
            <div className="adm-card__value">
              {stats.by_month?.at(-1)?.count ?? 0}
            </div>
          </article>
        </div>
      )}

      <div className="adm-tabs adm-tabs--wide">
        <button type="button" className={!filter ? "is-on" : ""} onClick={() => setFilter("")}>Усі</button>
        <button type="button" className={filter === "active" ? "is-on" : ""} onClick={() => setFilter("active")}>Чинні</button>
        <button type="button" className={filter === "revoked" ? "is-on" : ""} onClick={() => setFilter("revoked")}>Анульовані</button>
      </div>

      {/* ---------- форма видачі / правки ---------- */}
      {form && (
        <section className="adm-panel">
          <h2>{form.id ? `Правка ${form.serial_number || ""}` : "Новий сертифікат"}</h2>

          {/* Номер не редагується: він надрукований на документі й зашитий
              у QR-код. Помилка в даних — правимо дані; помилка в документі —
              анулюємо й видаємо новий. */}
          {!form.id && (
            <p className="adm-note">
              Номер буде згенеровано автоматично, з контрольним символом.
              Вводити його руками не можна — саморобні номери не проходять
              перевірку на сайті.
            </p>
          )}

          <form className="adm-form" onSubmit={submit}>
            <label>
              <span>Тип</span>
              <select value={form.kind} onChange={set("kind")}>
                {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </label>

            <label>
              <span>Імʼя учня *</span>
              <input value={form.student_full_name} onChange={set("student_full_name")} required />
            </label>

            <label>
              <span>Назва курсу *</span>
              <input value={form.course_title} onChange={set("course_title")} required />
            </label>

            <label>
              <span>Організація (для корпоративних)</span>
              <input value={form.organization} onChange={set("organization")} />
            </label>

            <label>
              <span>Рівень на старті</span>
              <select value={form.level_from} onChange={set("level_from")}>
                <option value="">—</option>
                {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>

            <label>
              <span>Рівень на фініші</span>
              <select value={form.level_to} onChange={set("level_to")}>
                <option value="">—</option>
                {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </label>

            <label>
              <span>Занять</span>
              <input type="number" min="0" value={form.lessons_count} onChange={set("lessons_count")} />
            </label>

            <label>
              <span>Годин</span>
              <input type="number" min="0" value={form.hours} onChange={set("hours")} />
            </label>

            <label>
              <span>Навчання з</span>
              <input type="date" value={form.started_at} onChange={set("started_at")} />
            </label>

            <label>
              <span>Навчання до</span>
              <input type="date" value={form.finished_at} onChange={set("finished_at")} />
            </label>

            <label>
              <span>Викладач</span>
              <input value={form.teacher_name} onChange={set("teacher_name")} />
            </label>

            <label>
              <span>Посилання на PDF</span>
              <input value={form.pdf_url} onChange={set("pdf_url")} placeholder="/static/certificates/…" />
            </label>

            {error && <p className="adm-form__err">{error}</p>}

            <div className="adm-form__actions">
              <button type="submit" className="adm-btn adm-btn--primary" disabled={busy}>
                {busy ? "Зберігаємо…" : form.id ? "Зберегти" : "Видати"}
              </button>
              <button type="button" className="adm-btn" onClick={() => setForm(null)}>
                Скасувати
              </button>
            </div>
          </form>
        </section>
      )}

      {loading && <p className="adm-empty">Завантажуємо…</p>}
      {!loading && items.length === 0 && <p className="adm-empty">Сертифікатів немає</p>}

      <div className="adm-rows">
        {items.map((c) => (
          <article key={c.id} className={`adm-row ${c.is_revoked ? "st-refunded" : "st-paid"}`}>
            <div className="adm-row__main" style={{ cursor: "default" }}>
              <div className="adm-row__who">
                <b>{c.student_full_name}</b>
                <span className="adm-mono">{c.serial_number}</span>
              </div>

              <div className="adm-row__meta">
                <span className="adm-tag">{KIND_LABEL[c.kind] || c.kind}</span>
                {c.level_from && c.level_to && (
                  <span className="adm-tag">{c.level_from} → {c.level_to}</span>
                )}
                <span className="adm-date">{fmt(c.issued_at)}</span>
                {c.is_revoked && <span className="adm-fail">анульовано</span>}
              </div>

              <div className="adm-cert-actions">
                {/* Посилання для QR — щоб менеджер міг перевірити очима,
                    що сертифікат справді знаходиться */}
                <a href={c.verify_url} target="_blank" rel="noreferrer" title="Перевірити">↗</a>
                <button type="button" onClick={() => edit(c)}>Правити</button>

                {/* Перегенерація дозволена: якщо виправили ім'я чи рівень,
                    документ треба перемалювати. Номер не змінюється, файл
                    перезаписується — раніше надіслані посилання лишаються
                    робочими. */}
                <button type="button" onClick={() => makePdf(c)}>
                  {c.pdf_url ? "Перегенерувати PDF" : "Зробити PDF"}
                </button>

                {c.pdf_url && (
                  <a href={c.pdf_url} target="_blank" rel="noreferrer">PDF</a>
                )}
                {c.is_revoked ? (
                  <button type="button"
                          onClick={() => adminRestoreCertificate(c.id).then(load)}>
                    Відновити
                  </button>
                ) : (
                  <button type="button" onClick={() => revoke(c)}>Анулювати</button>
                )}
                {!c.pdf_url && !c.is_revoked && (
                  <button type="button" className="is-danger" onClick={() => remove(c)}>
                    Видалити
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
