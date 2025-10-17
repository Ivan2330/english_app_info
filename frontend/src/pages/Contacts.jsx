import { useLocation } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { createLead } from "../api/leads.js";


/* ===== Icons ===== */
function IconUser(){
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-4.418 0-8 2.239-8 5v1h16v-1c0-2.761-3.582-5-8-5Z" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  );
}
function IconPhone(){
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M6.6 10.8c1.2 2.4 3.2 4.4 5.6 5.6l1.9-1.9a1 1 0 0 1 1.05-.24c1.15.38 2.39.59 3.65.59a1 1 0 0 1 1 1V19a2 2 0 0 1-2 2C10.28 21 3 13.72 3 4a2 2 0 0 1 2-2h2.15a1 1 0 0 1 1 1c0 1.26.21 2.5.59 3.65a1 1 0 0 1-.24 1.05L6.6 10.8Z" stroke="currentColor" strokeWidth="1.5"/>
    </svg>
  );
}
function IconAt(){
  return (
    <svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 20a8 8 0 1 1 6.32-3.1M15 13.5a3 3 0 1 1-3-3h.5a2.5 2.5 0 0 1 2.5 2.5v2a1.5 1.5 0 0 0 3 0V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ===== Helpers ===== */
function parseContact(raw){
  const v = (raw||"").trim();
  if(!v) return { email: undefined, telegram: undefined };
  // Дуже проста евристика:
  if(v.includes("@") && v.includes(".")) return { email: v, telegram: undefined };
  if(v.startsWith("@")) return { email: undefined, telegram: v };
  return { email: undefined, telegram: v }; // якщо не схоже на email — трактуємо як Telegram
}

export default function Contacts(){
  const location = useLocation();
  const preselected = location?.state?.selectedPackage || "";
  const formRef = useRef(null);

  const [form, setForm] = useState({
    name: "",
    phone: "",
    contact: "", // універсальне поле: Telegram або email
  });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(()=>{ setResult(null); }, [form.name, form.phone, form.contact]);

  function onChange(e){
    const { name, value } = e.target;
    setForm(s => ({ ...s, [name]: value }));
  }

  function scrollToForm(e){
    e?.preventDefault?.();
    const el = formRef.current;
    if(!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function onSubmit(e){
    e.preventDefault();
    if(!form.name.trim()){
      alert("Вкажіть, будь ласка, ім’я");
      return;
    }
    if(!(form.phone?.trim() || form.contact?.trim())){
      alert("Вкажіть хоча б один контакт: телефон або Telegram/email.");
      return;
    }

    const { email, telegram } = parseContact(form.contact);

    setSending(true); setResult(null);
    try{
      const payload = {
        kind: "trial",
        name: form.name.trim(),
        phone: form.phone?.trim() || undefined,
        email,
        telegram,
        comment: preselected ? `Цікавить пакет: ${preselected}` : undefined,
        source: "site",
      };
      const data = await createLead(payload);
      setResult({ ok:true, id:data?.id });
      setForm({ name:"", phone:"", contact:"" });
    } catch(err){
      console.error(err);
      setResult({ ok:false, error: err?.response?.data?.detail || "Помилка відправки" });
    } finally { setSending(false); }
  }

  return (
    <section className="contact">
      <div className="container contact__inner">

        <header className="contact__head contact__head--span">
          <p className="kicker">Prime Academy</p>
          <h1 className="section-title">Запис на безкоштовний пробний урок</h1>
          <p className="section-subtitle">
            30–60 хвилин із викладачем по відеозв’язку: діагностика рівня та персональний план.
          </p>
          <p className="contact__hint">
            Заповнення займає ~10 секунд. <strong>Потрібно лише ім’я та один контакт.</strong>
          </p>

          {/* Mobile ribbon */}
          <div className="promo-ribbon" aria-live="polite">
            <strong>До 20.10</strong> — зафіксуйте акційну ціну: <b>400/375/340/320 грн</b>
            <span className="promo-ribbon__sub">додатково до поточних знижок у пакетах</span>
          </div>
        </header>

        <div className="combo">
          {/* ===== PROMO (замість фото) ===== */}
          <aside className="promo card">
            <div className="promo__head">
              <span className="badge-deadline">🔔 Акція діє до 20 жовтня</span>
              <h3 className="promo__title">Зафіксуйте акційні ціни на жовтневий набір</h3>
              <p className="promo__subtitle">
                Додаткові знижки <strong>понад поточні</strong> знижки у пакетах.
              </p>
            </div>

            <div className="promo__list">
              <div className="tier">
                <div className="tier__name">16 уроків</div>
                <div className="tier__save">Економія 1600 грн</div>
                <div className="tier__price"><s>500 грн</s><span>400 грн</span></div>
              </div>
              <div className="tier">
                <div className="tier__name">24 уроки</div>
                <div className="tier__save">Економія 3000 грн</div>
                <div className="tier__price"><s>500 грн</s><span>375 грн</span></div>
              </div>
              <div className="tier">
                <div className="tier__name">48 уроків</div>
                <div className="tier__save">Економія 7 680 грн</div>
                <div className="tier__price"><s>500 грн</s><span>340 грн</span></div>
              </div>
              <div className="tier">
                <div className="tier__name">72 уроки</div>
                <div className="tier__save">Економія 12 960 грн</div>
                <div className="tier__price"><s>500 грн</s><span>320 грн</span></div>
              </div>
            </div>

            <div className="promo__foot">
              <div className="promo__note">
                Щоб зафіксувати ціну, достатньо залишити заявку на пробний до <strong>20.10</strong> — менеджер підкаже деталі.
              </div>
              <a href="#contact-form" className="btn btn-cta promo__cta" onClick={scrollToForm}>
                Хочу ціну по акції
              </a>
            </div>
          </aside>

          {/* ===== FORM (коротка) ===== */}
          <form id="contact-form" ref={formRef} className="form card" onSubmit={onSubmit} noValidate>
            <div className="form__row">
              <label className="field">
                <span className="field__label">Ім’я *</span>
                <span className="input-wrap">
                  <IconUser />
                  <input
                    className="field__input"
                    name="name"
                    value={form.name}
                    onChange={onChange}
                    placeholder="Ваше ім’я"
                    autoComplete="name"
                    required
                  />
                </span>
              </label>

              <label className="field">
                <span className="field__label">Телефон</span>
                <span className="input-wrap">
                  <IconPhone />
                  <input
                    className="field__input"
                    name="phone"
                    value={form.phone}
                    onChange={onChange}
                    placeholder="+380 00 000 00 00"
                    autoComplete="tel"
                    inputMode="tel"
                  />
                </span>
              </label>
            </div>

            <label className="field">
              <span className="field__label">Контакт (Telegram або email)</span>
              <span className="input-wrap">
                <IconAt />
                <input
                  className="field__input"
                  name="contact"
                  value={form.contact}
                  onChange={onChange}
                  placeholder="@username або name@example.com"
                  autoComplete="off"
                />
              </span>
            </label>

            <div className="form__footer">
              <div className="form__note">Натискаючи «Записатись», ви погоджуєтесь із умовами обробки даних.</div>
              <button className="btn btn-cta" type="submit" disabled={sending}>
                {sending ? "Надсилаємо..." : "📅 Записатись на пробний урок"}
              </button>
            </div>

            <p
              className={result?.ok ? "form__success" : result ? "form__error" : "sr-only"}
              role="status" aria-live="polite"
            >
              {result?.ok ? "Дякуємо! Заявку отримано — ми звʼяжемось найближчим часом."
                          : result ? `Помилка: ${result.error}` : ""}
            </p>
          </form>
        </div>
      </div>
    </section>
  );
}
