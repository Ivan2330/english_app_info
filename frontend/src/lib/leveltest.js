/**
 * ПОВНИЙ ТЕСТ РІВНЯ
 *
 * Два окремі набори питань замість одного довгого.
 *
 * ЧОМУ ДВА, А НЕ ОДИН АДАПТИВНИЙ
 * ==============================
 *
 * Один спільний тест на 40 питань погано працює з обох боків. Початківець
 * упирається в питання, яких не розуміє, на десятому — і закриває вкладку.
 * Людина з B2 нудьгує на перших двадцяти й теж іде.
 *
 * Справжній адаптивний тест (складність підлаштовується після кожної
 * відповіді) вимагає відкаліброваного банку питань на кілька сотень
 * позицій — це окремий проєкт. Розвилка на вході дає 80% користі
 * за 10% роботи: людина сама каже, звідки починати.
 *
 * ФОРМУЛЮВАННЯ РОЗВИЛКИ
 * =====================
 *
 * Не «початковий / просунутий» — таке змушує оцінювати себе, і люди
 * систематично занижують. Питаємо про поведінку: чи розумієте серіали,
 * чи можете підтримати розмову. Це простіше й точніше.
 *
 * РЕЗУЛЬТАТ
 * =========
 *
 * За замовчуванням користувачу НЕ показується — див. SHOW_RESULT нижче.
 * Бали з розбивкою їдуть у заявку, викладач розбирає їх на пробному.
 */

/** Чи показувати результат після тесту.
 *
 *  false — поточна політика: рівень називає викладач на пробному уроці.
 *  Тест перестає бути іграшкою «дізнався бал і пішов» і стає джерелом заявок.
 *
 *  Компроміс, якщо конверсія в контакти виявиться низькою: показувати
 *  діапазон («схоже на B1–B2»), але точний рівень лишати на пробний.
 *  Для цього достатньо перемкнути прапорець — решта коду готова.
 */
export const SHOW_RESULT = false;

/** Скільки питань показуємо. Менше за весь банк — щоб тест не тягнувся. */
export const QUESTIONS_PER_RUN = 25;

export const TRACKS = {
  starter: {
    id: "starter",
    title: "Починаю або давно не практикував",
    hint: "Окремі слова знаю, але речення даються важко. Серіали без субтитрів не розумію.",
    range: "A1 – B1",
    minutes: 8,
  },
  confident: {
    id: "confident",
    title: "Читаю й розумію, хочу перевірити точніше",
    hint: "Можу підтримати розмову й дивитися серіали з субтитрами. Цікавить, де саме прогалини.",
    range: "B1 – C1",
    minutes: 12,
  },
};

/* =========================================================================
   НАБІР ДЛЯ ПОЧАТКІВЦІВ · A1 → B1
   Складність зростає: перші питання має закрити будь-хто, останні
   відділяють A2 від B1.
   ========================================================================= */

export const STARTER_QUESTIONS = [
  { level: "A1", q: "___ from Ukraine.",
    options: ["I'm", "I are", "I be", "My is"], correct: 0 },

  { level: "A1", q: "She ___ coffee every morning.",
    options: ["drink", "drinks", "drinking", "is drink"], correct: 1 },

  { level: "A1", q: "There ___ two books on the table.",
    options: ["is", "are", "be", "am"], correct: 1 },

  { level: "A1", q: "___ you like pizza?",
    options: ["Do", "Does", "Are", "Is"], correct: 0 },

  { level: "A1", q: "This is ___ interesting film.",
    options: ["a", "an", "the", "— (нічого)"], correct: 1 },

  { level: "A1", q: "___ is your birthday?",
    options: ["When", "Where", "Who", "Which"], correct: 0 },

  { level: "A2", q: "He is taller ___ his brother.",
    options: ["then", "than", "that", "as"], correct: 1 },

  { level: "A2", q: "I ___ to the cinema yesterday.",
    options: ["go", "went", "gone", "was go"], correct: 1 },

  { level: "A2", q: "I'd like ___ water, please.",
    options: ["some", "any", "a", "many"], correct: 0 },

  { level: "A2", q: "She can't come ___ she is ill.",
    options: ["so", "but", "because", "although"], correct: 2 },

  { level: "A2", q: "There isn't ___ milk left.",
    options: ["many", "much", "a lot", "few"], correct: 1 },

  { level: "A2", q: "___ I open the window?",
    options: ["May", "Do", "Am", "Will"], correct: 0 },

  { level: "A2", q: "It's the ___ film I've ever seen.",
    options: ["better", "goodest", "best", "most good"], correct: 2 },

  { level: "A2", q: "The train ___ at six every morning.",
    options: ["leave", "leaves", "is leaving", "left"], correct: 1 },

  { level: "A2", q: "We didn't go out ___ the rain.",
    options: ["because", "because of", "so", "for"], correct: 1 },

  { level: "B1", q: "If it rains tomorrow, we ___ at home.",
    options: ["stay", "will stay", "stayed", "would stay"], correct: 1 },

  { level: "B1", q: "He's been working here ___ five years.",
    options: ["since", "for", "during", "from"], correct: 1 },

  { level: "B1", q: "We ___ here since 2020.",
    options: ["are living", "have been living", "live", "was living"], correct: 1 },

  { level: "B1", q: "I'm looking forward ___ you again.",
    options: ["to see", "to seeing", "seeing", "see"], correct: 1 },

  { level: "B1", q: "The book ___ I read last week was excellent.",
    options: ["what", "that", "who", "whose"], correct: 1 },

  { level: "B1", q: "She said she ___ tired.",
    options: ["is", "was", "were", "be"], correct: 1 },

  { level: "B1", q: "I used ___ in London when I was a child.",
    options: ["to live", "live", "living", "lived"], correct: 0 },

  { level: "B1", q: "He asked me where I ___.",
    options: ["live", "lived", "do live", "am living"], correct: 1 },

  { level: "B1", q: "He hasn't finished the report ___.",
    options: ["already", "still", "yet", "just"], correct: 2 },

  { level: "B1", q: "The letter ___ yesterday.",
    options: ["was sent", "sent", "is sent", "has sent"], correct: 0 },

  { level: "B1", q: "Neither of the students ___ the answer.",
    options: ["know", "knows", "knowing", "known"], correct: 1 },

  { level: "B1", q: "You ___ smoke here — it's forbidden.",
    options: ["mustn't", "don't have to", "needn't", "couldn't"], correct: 0 },

  { level: "B1", q: "I'd rather ___ tea than coffee.",
    options: ["to drink", "drinking", "drink", "drank"], correct: 2 },
];

/* =========================================================================
   НАБІР ДЛЯ ВПЕВНЕНИХ · B1 → C1
   Тут перевіряємо не базову граматику, а те, що зазвичай і відділяє
   B2 від C1: часові зсуви, інверсія, фразові дієслова, сталі вирази.
   ========================================================================= */

export const CONFIDENT_QUESTIONS = [
  { level: "B1", q: "By the time we arrived, the film ___.",
    options: ["started", "has started", "had started", "was starting"], correct: 2 },

  { level: "B1", q: "She's used to ___ up early.",
    options: ["get", "getting", "got", "gets"], correct: 1 },

  { level: "B1", q: "If I ___ known, I would have called you.",
    options: ["have", "had", "would have", "did"], correct: 1 },

  { level: "B1", q: "He denied ___ the money.",
    options: ["to take", "taking", "take", "taken"], correct: 1 },

  { level: "B2", q: "I'd rather you ___ smoke in here.",
    options: ["don't", "didn't", "won't", "wouldn't"], correct: 1 },

  { level: "B2", q: "It's high time we ___.",
    options: ["leave", "left", "are leaving", "will leave"], correct: 1 },

  { level: "B2", q: "___ the bad weather, the match went ahead.",
    options: ["Despite", "Although", "However", "Even"], correct: 0 },

  { level: "B2", q: "I can't put up ___ this noise any longer.",
    options: ["for", "to", "with", "on"], correct: 2 },

  { level: "B2", q: "The proposal was turned ___ by the board.",
    options: ["off", "down", "over", "up"], correct: 1 },

  { level: "B2", q: "We'll have finished the project ___ Friday.",
    options: ["until", "till", "by", "in"], correct: 2 },

  { level: "B2", q: "The situation calls ___ urgent action.",
    options: ["on", "for", "at", "to"], correct: 1 },

  { level: "B2", q: "He takes ___ his father — same stubborn character.",
    options: ["over", "after", "up", "on"], correct: 1 },

  { level: "B2", q: "The report needs ___ before Monday.",
    options: ["revise", "revising", "to revising", "revised"], correct: 1 },

  { level: "B2", q: "She's the kind of person ___ you can always rely.",
    options: ["who", "that", "on whom", "whom"], correct: 2 },

  { level: "B2", q: "I'm not used ___ so much in one day.",
    options: ["to walk", "to walking", "walking", "walk"], correct: 1 },

  { level: "B2", q: "If I were you, I ___ that offer.",
    options: ["will accept", "would accept", "accepted", "accept"], correct: 1 },

  { level: "B2", q: "The meeting was put ___ until next week.",
    options: ["off", "out", "away", "down"], correct: 0 },

  { level: "C1", q: "Not only ___ late, but he also forgot the tickets.",
    options: ["he was", "was he", "he is", "did he"], correct: 1 },

  { level: "C1", q: "Hardly ___ down when the phone rang.",
    options: ["I had sat", "had I sat", "I sat", "did I sit"], correct: 1 },

  { level: "C1", q: "Little ___ that he was being watched.",
    options: ["he knew", "did he know", "he did know", "knew he"], correct: 1 },

  { level: "C1", q: "Were it not ___ your help, we would have failed.",
    options: ["of", "to", "for", "with"], correct: 2 },

  { level: "C1", q: "___ he apologise, I would forgive him.",
    options: ["Should", "Would", "Could", "If"], correct: 0 },

  { level: "C1", q: "His argument simply doesn't hold ___.",
    options: ["up water", "water", "the water", "any water"], correct: 1 },

  { level: "C1", q: "The company is on the ___ of bankruptcy.",
    options: ["edge", "verge", "border", "side"], correct: 1 },

  { level: "C1", q: "She was ___ to tears by the news.",
    options: ["moved", "brought", "taken", "made"], correct: 0 },

  { level: "C1", q: "I'd sooner ___ than ask him for a favour.",
    options: ["resigning", "to resign", "resign", "resigned"], correct: 2 },

  { level: "C1", q: "Under no circumstances ___ the door unlocked.",
    options: ["you should leave", "should you leave", "you leave", "leave you"], correct: 1 },

  { level: "C1", q: "The new rules come ___ force next month.",
    options: ["in", "into", "to", "at"], correct: 1 },
];

/** Орієнтовний діапазон за кількістю правильних.
 *  Використовується для тексту в заявці — викладач бачить його ще до уроку. */
export function estimateBand(trackId, correct, total) {
  const pct = total ? (correct / total) * 100 : 0;

  if (trackId === "starter") {
    if (pct < 25) return "A1 (початковий)";
    if (pct < 50) return "A1–A2";
    if (pct < 72) return "A2";
    if (pct < 88) return "A2–B1";
    return "B1 — варто пройти складніший набір";
  }

  if (pct < 30) return "B1 або нижче — можливо, варто почати з базового набору";
  if (pct < 50) return "B1";
  if (pct < 70) return "B1–B2";
  if (pct < 85) return "B2";
  return "B2–C1";
}
