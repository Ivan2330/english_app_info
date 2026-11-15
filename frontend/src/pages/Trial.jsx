import PageHero from "../components/PageHero.jsx";
import TrialForm from "../components/TrialForm.jsx";

/**
 * Посадкова сторінка для реклами: один оффер, одна форма, нічого зайвого.
 * Лише перевірені факти: пробний 40 хвилин, без картки, групи до 6 людей.
 */
export default function Trial() {
  return (
    <>
      <PageHero crumb={<span>Пробний урок</span>} title="Безкоштовний пробний урок англійської"
                lead="40 хвилин із викладачем по відеозв'язку: визначимо рівень, поговоримо англійською і складемо план під вашу ціль." />
      <section className="section">
        <div className="container trial">
          <div className="trial__form card">
            <TrialForm source="site/trial" id="trial-form" />
          </div>
          <aside className="trial__facts" aria-label="Що вас чекає">
            <h2>Як це працює</h2>
            <ol>
              <li><b>Залишаєте заявку</b> імʼя й контакт, це займає хвилину.</li>
              <li><b>Ми напишемо вам</b> протягом 15 хвилин у робочий час і домовимось про зручний час.</li>
              <li><b>Пробний урок, 40 хвилин:</b> діагностика рівня й персональний план. Без оплати й без картки.</li>
            </ol>
            <ul className="trial__list">
              <li>Індивідуально, у парі або в групі до 6 людей</li>
              <li>Група: урок 90 хвилин</li>
              <li>Дорослі, підлітки й діти від 5 років</li>
              <li>Не сподобається, просто не продовжуєте</li>
            </ul>
          </aside>
        </div>
      </section>
    </>
  );
}
