import asyncio
import argparse
import string
import random
import os
from datetime import datetime
from app.db.database import async_session_maker
from app.models.certificate import Certificate

def generate_public_code(length=12):
    chars = string.ascii_uppercase + string.digits
    raw = ''.join(random.choices(chars, k=length))
    return '-'.join(raw[i:i+4] for i in range(0, len(raw), 4))

def generate_serial_number(prefix="PA"):
    unique_part = int(datetime.now().timestamp())
    return f"{prefix}-{datetime.now().year}-{unique_part}"

async def create_certificate(args):
    # Перевіряємо, чи існує файл фізично у контейнері
    file_path_in_container = f"/app/static/certificates/{args.file}"
    
    if args.file and not os.path.exists(file_path_in_container):
        print(f"⚠️ УВАГА: Файл '{args.file}' не знайдено у папці static/certificates!")
        print("Переконайтеся, що ви завантажили його на сервер у папку ./certificates")
        confirm = input("Продовжити створення запису в БД без файлу? (y/n): ")
        if confirm.lower() != 'y':
            return

    async with async_session_maker() as session:
        s_number = args.serial or generate_serial_number()
        p_code = args.code or generate_public_code()

        # Посилання, яке буде у базі (відносне, щоб Nginx його зрозумів)
        pdf_link = f"/static/certificates/{args.file}" if args.file else None

        new_cert = Certificate(
            serial_number=s_number,
            public_code=p_code,
            student_full_name=args.student,
            course_title=args.course,
            level_cefr=args.level,
            hours=args.hours,
            pdf_url=pdf_link,
            issued_at=datetime.utcnow()
        )

        session.add(new_cert)
        await session.commit()
        
        print("\n✅ СЕРТИФІКАТ СТВОРЕНО!")
        print("-" * 30)
        print(f"Студент:  {new_cert.student_full_name}")
        print(f"Курс:     {new_cert.course_title}")
        print(f"URL:      {new_cert.pdf_url}")
        print("-" * 30)
        print(f"КОД:      {new_cert.public_code}")
        print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--student", required=True, help="ПІБ студента")
    parser.add_argument("-c", "--course", required=True, help="Назва курсу")
    parser.add_argument("-f", "--file", required=True, help="Назва файлу (напр. cert.pdf)")
    parser.add_argument("-l", "--level", help="Рівень (A1, B2)")
    parser.add_argument("--hours", type=int)
    parser.add_argument("--serial")
    parser.add_argument("--code")
    
    args = parser.parse_args()
    asyncio.run(create_certificate(args))