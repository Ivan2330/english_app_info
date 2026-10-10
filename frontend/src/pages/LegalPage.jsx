import { Link } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import { useReveal } from "../lib/motion.js";
import { SELLER, sellerIsConfigured, OFFER_REVISION } from "../lib/legal/seller.js";

/**
 * Спільний макет для юридичних сторінок: оферта й політика конфіденційності.
 *
 * Обидві — довгі нумеровані документи, і головне тут не краса, а читабельність:
 * широкі поля, великий міжрядковий інтервал, якір на кожен розділ.
 * Людина відкриває таку сторінку, щоб знайти один конкретний пункт,
 * а не щоб прочитати все.
 */
export default function LegalPage({ crumb, title, lead, sections, showSeller = true }) {
  useReveal([sections]);

  return (
    <>
      <PageHero crumb={crumb} title={title} lead={lead} />

      <section className="sec sec--tight">
        <div className="container legal">
          {/* Зміст: на документі з п'ятнадцяти розділів без нього не обійтись */}
          <nav className="legal__toc" aria-label="Зміст документа" data-reveal>
            <h2 className="legal__toc-title">Зміст</h2>
            <ol>
              {sections.map((s, i) => (
                <li key={s.title}>
                  <a href={`#p${i + 1}`}>{s.title}</a>
                </li>
              ))}
            </ol>
          </nav>

          <div className="legal__body">
            {sections.map((s, i) => (
              <section key={s.title} className="legal__section" id={`p${i + 1}`} data-reveal>
                <h2 className="legal__h2">{s.title}</h2>
                {s.items.map((text) => (
                  <p key={text} className="legal__p">{text}</p>
                ))}
              </section>
            ))}

            {showSeller && (
              <section className="legal__section" id="requisites" data-reveal>
                <h2 className="legal__h2">Реквізити Виконавця</h2>

                {sellerIsConfigured() ? (
                  <dl className="legal__req">
                    <dt>Найменування</dt><dd>{SELLER.name}</dd>
                    <dt>Податковий номер</dt><dd>{SELLER.taxId}</dd>
                    {SELLER.registryRecord ? (
                      <>
                        <dt>Запис в ЄДР</dt><dd>{SELLER.registryRecord}</dd>
                      </>
                    ) : null}
                    <dt>Адреса для листування</dt><dd>{SELLER.address}</dd>
                    {SELLER.taxGroup ? (
                      <>
                        <dt>Система оподаткування</dt>
                        <dd>
                          Єдиний податок, {SELLER.taxGroup} група
                          {SELLER.taxGroup === "3" ? " · не платник ПДВ" : ""}
                        </dd>
                      </>
                    ) : null}
                    <dt>Електронна пошта</dt>
                    <dd><a href={`mailto:${SELLER.email}`}>{SELLER.email}</a></dd>
                    <dt>Телефон</dt><dd>{SELLER.phone}</dd>
                  </dl>
                ) : (
                  /* Поки реквізити не заповнені — чесно про це кажемо.
                     Мовчазна порожнеча в цьому місці гірша за попередження. */
                  <p className="legal__warn">
                    Реквізити Виконавця на стадії оформлення. До їх публікації оплата
                    на сайті не приймається — зв'яжіться з нами будь-яким зручним
                    способом, і ми узгодимо умови особисто.
                  </p>
                )}
              </section>
            )}

            <p className="legal__revision" data-reveal>
              Редакція від {OFFER_REVISION}.{" "}
              <Link to="/contacts">Є питання за умовами — напишіть нам</Link>.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
