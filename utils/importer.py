import csv
import io
import re
from typing import List, Dict, Any
import openpyxl


def parse_employee_text(raw_text: str, start_id: int = 101) -> List[Dict[str, Any]]:
    """
    Парсит простой построчный текст со списком сотрудников.
    Поддерживает форматы:
    - Александр Смирнов
    - Смирнов Александр
    - Александр Смирнов, +7 (999) 111-22-33, example.com
    - Иван, Иванов, 105, +79990000000, site.ru
    """
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    results = []
    current_id = start_id

    for line in lines:
        if line.startswith("#") or line.startswith("//"):
            continue

        # Проверяем, есть ли разделители (запятая, точка с запятой или табуляция)
        if any(sep in line for sep in (",", ";", "\t")):
            parts = [p.strip() for p in re.split(r"[,;\t]+", line) if p.strip()]
            full_name = parts[0]
            name_parts = full_name.split(maxsplit=1)
            name = name_parts[0] if name_parts else ""
            surname = name_parts[1] if len(name_parts) > 1 else ""

            emp_id = None
            phone = None
            website = None

            for part in parts[1:]:
                # Если часть состоит только из цифр — возможно это ID
                if part.isdigit() and emp_id is None:
                    emp_id = int(part)
                elif re.search(r"\+?\d[\d\s\-\(\)]{6,}", part) and phone is None:
                    phone = part
                elif ("." in part or part.startswith("http")) and website is None:
                    website = part

            results.append({
                "name": name,
                "surname": surname,
                "full_name": full_name,
                "id": emp_id if emp_id is not None else current_id,
                "phone": phone,
                "website": website,
            })
            if emp_id is None or emp_id >= current_id:
                current_id = (emp_id or current_id) + 1
        else:
            # Просто строка с именем и фамилией
            name_parts = line.split(maxsplit=1)
            name = name_parts[0] if name_parts else ""
            surname = name_parts[1] if len(name_parts) > 1 else ""
            results.append({
                "name": name,
                "surname": surname,
                "full_name": line,
                "id": current_id,
                "phone": None,
                "website": None,
            })
            current_id += 1

    return results


def parse_employee_file(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Парсит файлы Excel (.xlsx, .xls) или CSV (.csv).
    Автоматически определяет заголовки колонок или использует позиционный парсинг.
    """
    lower_name = filename.lower()
    rows = []

    if lower_name.endswith(".csv") or lower_name.endswith(".txt"):
        # Декодируем CSV (с поддержкой utf-8 и cp1251)
        for enc in ("utf-8-sig", "utf-8", "cp1251"):
            try:
                content = file_bytes.decode(enc)
                # Определяем диалект и разделитель
                delimiter = ","
                if ";" in content and content.count(";") > content.count(","):
                    delimiter = ";"
                elif "\t" in content and content.count("\t") > content.count(","):
                    delimiter = "\t"

                reader = csv.reader(io.StringIO(content), delimiter=delimiter)
                rows = [list(r) for r in reader if any(r)]
                break
            except UnicodeDecodeError:
                continue

    elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            if any(r):
                rows.append([str(cell).strip() if cell is not None else "" for cell in r])

    if not rows:
        return []

    # Анализируем первую строку на заголовки
    header_indices = {}
    first_row = [str(c).lower().strip() for c in rows[0]]

    col_map = {
        "name": ("имя", "name", "first name", "firstname", "first_name"),
        "surname": ("фамилия", "surname", "last name", "lastname", "last_name"),
        "full_name": ("фио", "сотрудник", "полное имя", "full name", "fullname", "full_name"),
        "id": ("id", "ид", "номер", "табельный номер", "номер бейджа"),
        "phone": ("телефон", "тел", "phone", "mobile", "тел.", "номер телефона"),
        "website": ("сайт", "ссылка", "web", "website", "url", "сайт компании"),
    }

    for col_idx, cell_val in enumerate(first_row):
        for field, keywords in col_map.items():
            if any(kw == cell_val or kw in cell_val for kw in keywords):
                if field not in header_indices:
                    header_indices[field] = col_idx

    has_headers = len(header_indices) > 0
    data_rows = rows[1:] if has_headers else rows

    results = []
    current_id = 101

    for row in data_rows:
        if not any(row):
            continue

        name = ""
        surname = ""
        full_name = ""
        emp_id = None
        phone = None
        website = None

        if has_headers:
            if "full_name" in header_indices and header_indices["full_name"] < len(row):
                full_name = str(row[header_indices["full_name"]]).strip()
            if "name" in header_indices and header_indices["name"] < len(row):
                name = str(row[header_indices["name"]]).strip()
            if "surname" in header_indices and header_indices["surname"] < len(row):
                surname = str(row[header_indices["surname"]]).strip()
            if "id" in header_indices and header_indices["id"] < len(row):
                val = str(row[header_indices["id"]]).strip()
                if val.isdigit():
                    emp_id = int(val)
            if "phone" in header_indices and header_indices["phone"] < len(row):
                phone = str(row[header_indices["phone"]]).strip() or None
            if "website" in header_indices and header_indices["website"] < len(row):
                website = str(row[header_indices["website"]]).strip() or None

            # Если было только ФИО в одной колонке
            if full_name and not name:
                parts = full_name.split(maxsplit=1)
                name = parts[0] if parts else ""
                surname = parts[1] if len(parts) > 1 else ""
            elif name and surname and not full_name:
                full_name = f"{name} {surname}".strip()
        else:
            # Позиционный парсинг (первая колонка — имя или ФИО)
            first_cell = str(row[0]).strip()
            if len(row) >= 2 and not any(char.isdigit() for char in str(row[1])):
                # 1 колонка = Имя, 2 колонка = Фамилия
                name = first_cell
                surname = str(row[1]).strip()
                full_name = f"{name} {surname}".strip()
            else:
                parts = first_cell.split(maxsplit=1)
                name = parts[0] if parts else ""
                surname = parts[1] if len(parts) > 1 else ""
                full_name = first_cell

            # Поиск телефона / сайта / id в остальных колонках
            for col_val in row[1:]:
                val = str(col_val).strip()
                if not val:
                    continue
                if val.isdigit() and emp_id is None:
                    emp_id = int(val)
                elif re.search(r"\+?\d[\d\s\-\(\)]{6,}", val) and phone is None:
                    phone = val
                elif ("." in val or val.startswith("http")) and website is None:
                    website = val

        if not name and not full_name:
            continue

        results.append({
            "name": name,
            "surname": surname,
            "full_name": full_name or f"{name} {surname}".strip(),
            "id": emp_id if emp_id is not None else current_id,
            "phone": phone,
            "website": website,
        })
        if emp_id is None or emp_id >= current_id:
            current_id = (emp_id or current_id) + 1

    return results
