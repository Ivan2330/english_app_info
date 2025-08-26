# 1. Вихідний образ
FROM python:3.11-slim

# 2. Встановлення робочої директорії
WORKDIR /app

# 3. Копіюємо файли requirements та встановлюємо залежності
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Копіюємо весь проєкт
COPY . .

# 5. Встановлюємо змінні середовища
ENV PYTHONUNBUFFERED=1

# 6. Запускаємо сервер
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
