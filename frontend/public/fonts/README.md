# Сюди покласти шрифт e-Ukraine

Шрифт «Дії» від Міністерства цифрової трансформації.
Завантажити: https://thedigital.gov.ua/fonts

## Які саме файли

Підключення чекає на ці імена (див. `styles/variables.css`):

```
e-Ukraine-Regular.woff2
e-Ukraine-Medium.woff2
e-Ukraine-Bold.woff2
e-UkraineHead-Regular.woff2
e-UkraineHead-Bold.woff2
```

В архіві з сайту лежать `.otf` / `.ttf`. Перегнати у `woff2`:

```bash
pip install fonttools brotli
python -c "
from fontTools.ttLib import TTFont
import sys
f = TTFont(sys.argv[1]); f.flavor='woff2'
f.save(sys.argv[1].rsplit('.',1)[0] + '.woff2')
" e-Ukraine-Regular.otf
```

`woff2` важить у 3–5 разів менше за `otf` — для шрифту, який вантажиться
першим і блокує показ тексту, різниця відчутна на мобільному.

## Поки файлів немає

Сайт не ламається: стек у `--font-text` / `--font-head` відкочується
на Manrope і Unbounded з Google Fonts. Тому класти їх можна коли завгодно,
окремим комітом.

## Ліцензія — зазначення авторства ОБОВ'ЯЗКОВЕ

CC BY 4.0. Комерційне використання дозволене, але рядок про авторство
має бути на сайті. Він стоїть у футері — **не прибирати**.
