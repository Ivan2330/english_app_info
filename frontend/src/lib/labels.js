// Українські підписи для осей каталогу.
// Бекенд віддає технічні ключі (adults / group / general), уся локалізація — тут.

export const AUDIENCE = {
  adults: { label: "Дорослі", note: "18+" },
  teens: { label: "Підлітки", note: "13–17 років" },
  kids: { label: "Діти", note: "5–12 років" },
  corporate: { label: "Для компаній", note: "корпоративне навчання" },
};

export const FORMAT = {
  individual: { label: "Індивідуально", note: "Один на один із викладачем" },
  pair: { label: "У парі", note: "Ви + друг або колега вашого рівня" },
  group: { label: "Група", note: "Міні-група до 6 людей за рівнем" },
  club: { label: "Speaking Club", note: "Тільки розмовна практика" },
};

export const TRACK = {
  general: {
    label: "Загальний рівень",
    note: "Системно підняти англійську за CEFR, без прив'язки до іспиту",
  },
  speaking: {
    label: "Розмовний фокус",
    note: "Для тих, хто все розуміє, але мовчить",
  },
  school: {
    label: "Школа",
    note: "Шкільна програма без нудьги, підтягнути оцінки",
  },
  business: { label: "Робота та кар'єра", note: "Співбесіди, мітинги, листування" },
  nmt: { label: "НМТ", note: "Підготовка до національного мультитесту" },
  exam: { label: "Іспити", note: "IELTS, TOEFL, Cambridge" },
  job_ready: { label: "Job Ready", note: "Резюме, LinkedIn, тренувальні співбесіди" },
  it: { label: "English for IT", note: "Мітинги, код-рев'ю, документація" },
  travel: { label: "Travel English", note: "Подорожі без мовного бар'єру" },
};

export const FAMILY = {
  subscription: "Абонемент",
  course: "Курс",
  club: "Speaking Club",
  corporate: "Для компаній",
};

export function money(value, currency = "UAH") {
  if (value == null) return null;
  try {
    return new Intl.NumberFormat("uk-UA", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value} ₴`;
  }
}

/** Правильне закінчення: 1 урок, 2 уроки, 5 уроків. */
export function lessonsWord(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "урок";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "уроки";
  return "уроків";
}
