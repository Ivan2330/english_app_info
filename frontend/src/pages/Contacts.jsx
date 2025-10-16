import { useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import { createLead } from "../api/leads.js";
import contactHero from "../assets/hero/contact-hero.webp";

/* ===== helpers ===== */
function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.matchMedia(`(max-width:${breakpoint}px)`).matches : false
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(`(max-width:${breakpoint}px)`);
    const onChange = (e) => setIsMobile(e.matches);
    mql.addEventListener?.("change", onChange);
    mql.addListener?.(onChange); // Safari fallback
    return () => {
      mql.removeEventListener?.("change", onChange);
      mql.removeListener?.(onChange);
    };
  }, [breakpoint]);
  return isMobile;
}

/* ===== icons ===== */
function IconPhone(){return(<svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.6 10.8c1.2 2.4 3.2 4.4 5.6 5.6l1.9-1.9a1 1 0 0 1 1.05-.24c1.15.38 2.39.59 3.65.59a1 1 0 0 1 1 1V19a2 2 0 0 1-2 2C10.28 21 3 13.72 3 4a2 2 0 0 1 2-2h2.15a1 1 0 0 1 1 1c0 1.26.21 2.5.59 3.65a1 1 0 0 1-.24 1.05L6.6 10.8Z" stroke="currentColor" strokeWidth="1.5"/></svg>);}
function IconMail(){return(<svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Zm0 0 8 6 8-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>);}
function IconUser(){return(<svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-4.418 0-8 2.239-8 5v1h16v-1c0-2.761-3.582-5-8-5Z" stroke="currentColor" strokeWidth="1.5"/></svg>);}
function IconTelegram(){return(<svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M21 3 3.5 10.2c-.6.24-.59 1.1.01 1.33l4.54 1.77 1.76 4.54c.23.6 1.09.61 1.33.01L18 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>);}
function IconClock(){return(<svg className="field__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 7v5l4 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>);}
function IconSelect(){return(<svg className="field__icon caret" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>);}

export default function Contacts() {
  const location = useLocation();
  const preselected = location?.state?.selectedPackage || "";
  const isMobile = useIsMobile(768); // <-- на телефонах не рендеримо фото

  const [form, setForm] = useState({
    name: "", phone: "", email: "", telegram: "",
    audience: "", preferred_time: "",
    comment: preselected ? `Цікавить пакет: ${preselected}` : "",
  });
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  function onChange(e){
    const { name, value } = e.target;
    setForm(s => ({ ...s, [name]: value }));
  }

  async function onSubmit(e){
    e.preventDefault();
    if(!form.name.trim()) { alert("Вкажіть, будь ласка, ім’я"); return; }
    const hasAnyContact = (form.phone?.trim() || form.telegram?.trim() || form.email?.trim());
    if(!hasAnyContact){ alert("Вкажіть хоча б один контакт: телефон, Telegram або email."); return; }

    setSending(true); setResult(null);
    try{
      const payload = {
        kind:"trial",
        name: form.name.trim(),
        phone: form.phone || undefined,
        telegram: form.telegram || undefined,
        email: form.email || undefined,
        audience: form.audience || undefined,
        preferred_time: form.preferred_time || undefined,
        comment: form.comment || undefined,
        source:"site",
      };
      const data = await createLead(payload);
      setResult({ ok:true, id:data?.id });
      setForm({ name:"", phone:"", email:"", telegram:"", audience:"", preferred_time:"", comment:"" });
    } catch(err){
      console.error(err);
      setResult({ ok:false, error: err?.response?.data?.detail || "Помилка відправки" });
    } finally { setSending(false); }
  }

  useEffect(()=>{
    if(preselected && !form.comment){
      setForm(s=>({ ...s, comment:`Цікавить пакет: ${preselected}` }));
    }
    // eslint-disable-next-line
  },[]);

  return (
    <section className="contact">
      <div className="container contact__inner">

        <header className="contact__head contact__head--span">
          <p className="kicker">Prime Academy</p>
          <h1 className="section-title">Запис на безкоштовний пробний урок</h1>
          <p className="section-subtitle">
            30–60 хвилин з викладачем по відеозв’язку: діагностика рівня та персональний план.
          </p>
          <p className="contact__hint">
            Вкажи <strong>хоча б один спосіб зв’язку</strong> (телефон / Telegram / email). Інші поля — за бажанням.
          </p>
        </header>

        <div className={`combo card ${isMobile ? "combo--formOnly" : ""}`}>
          {/* left: form */}
          <form className="form form--combo" onSubmit={onSubmit} noValidate>
            <div className="form__row">
              <label className="field">
                <span className="field__label">Ім’я *</span>
                <span className="input-wrap">
                  <IconUser />
                  <input className="field__input" name="name" value={form.name}
                    onChange={onChange} placeholder="Ваше ім’я" required autoComplete="name" />
                </span>
              </label>

              <label className="field">
                <span className="field__label">Телефон</span>
                <span className="input-wrap">
                  <IconPhone />
                  <input className="field__input" name="phone" value={form.phone}
                    onChange={onChange} placeholder="Ваш номер телефону" autoComplete="tel" inputMode="tel" />
                </span>
              </label>
            </div>

            <div className="form__row">
              <label className="field">
                <span className="field__label">Email</span>
                <span className="input-wrap">
                  <IconMail />
                  <input className="field__input" type="email" name="email" value={form.email}
                    onChange={onChange} placeholder="name@example.com" autoComplete="email" />
                </span>
              </label>

              <label className="field">
                <span className="field__label">Telegram</span>
                <span className="input-wrap">
                  <IconTelegram />
                  <input className="field__input" name="telegram" value={form.telegram}
                    onChange={onChange} placeholder="@username" />
                </span>
              </label>
            </div>

            <div className="form__row">
              <label className="field">
                <span className="field__label">Аудиторія</span>
                <span className="input-wrap">
                  <IconSelect />
                  <select className="field__select" name="audience" value={form.audience} onChange={onChange}>
                    <option value="">Обрати...</option>
                    <option value="kids">Діти</option>
                    <option value="adults">Дорослі</option>
                  </select>
                </span>
              </label>

              <label className="field">
                <span className="field__label">Зручний час</span>
                <span className="input-wrap">
                  <IconClock />
                  <input className="field__input" name="preferred_time" value={form.preferred_time}
                    onChange={onChange} placeholder="Будні 18:00–20:00" />
                </span>
              </label>
            </div>

            <label className="field">
              <span className="field__label">Коментар</span>
              <textarea className="field__textarea" name="comment" value={form.comment}
                onChange={onChange} rows={4}
                placeholder="Побажання щодо графіку, цілей або викладача" />
            </label>

            <div className="form__footer">
              <div className="form__note">Натискаючи «Записатись», ви погоджуєтесь із умовами обробки даних.</div>
              <button className="btn btn-cta" type="submit" disabled={sending}>
                {sending ? "Надсилаємо..." : "📅 Записатись на пробний урок"}
              </button>
            </div>

            <p className={result?.ok ? "form__success" : result ? "form__error" : "sr-only"} role="status" aria-live="polite">
              {result?.ok ? "Дякуємо! Заявку отримано — ми звʼяжемось найближчим часом."
                          : result ? `Помилка: ${result.error}` : ""}
            </p>
          </form>

          {/* right: photo — не рендеримо на мобайлі */}
          {!isMobile && (
            <aside className="visual">
              <div className="visual__media">
                <img
                  src={contactHero}
                  alt="Студентка на онлайн-уроці англійської"
                  className="visual__img"
                  loading="lazy"
                />
                <div className="visual__fadeLeft" aria-hidden="true"></div>
                <div className="visual__badges"></div>
              </div>
            </aside>
          )}
        </div>
      </div>
    </section>
  );
}
