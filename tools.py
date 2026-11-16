import json
from pathlib import Path
from math import ceil
from datetime import datetime, timezone

DATA_DIR = Path(__file__).resolve().parent
USERS_FILE = DATA_DIR / "users.json"
TRIPS_FILE = DATA_DIR / "trips.json"


def _read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def start_trip(name: str, email: str) -> dict:
    """Реєструє користувача та створює нову подорож зі статусом planning."""
    name = name.strip()
    email = email.strip().lower()
    if not name or "@" not in email or "." not in email.split("@")[-1]:
        return {"success": False, "error": "Потрібні коректні ім'я та email. Уточни їх у користувача."}

    users = _read_json(USERS_FILE, [])
    if not any(u.get("email") == email for u in users):
        users.append({"name": name, "email": email})
        _write_json(USERS_FILE, users)

    trips = _read_json(TRIPS_FILE, [])
    trip = {
        "trip_id": f"trip-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "name": name,
        "email": email,
        "status": "planning",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "itinerary": {},
        "budget": None,
        "history": []
    }
    trips.append(trip)
    _write_json(TRIPS_FILE, trips)
    return {"success": True, "message": f"Планування розпочато для {name}.", "trip_id": trip["trip_id"]}


def estimate_budget(days, daily_food, daily_transport, accommodation_per_night, activities_total, currency="EUR"):
    """Розрахунок орієнтовного бюджету з переданих припущень."""
    days = max(1, int(days))
    nights = max(0, days - 1)
    food = max(0.0, float(daily_food)) * days
    transport = max(0.0, float(daily_transport)) * days
    accommodation = max(0.0, float(accommodation_per_night)) * nights
    activities = max(0.0, float(activities_total))
    return {
        "notice": "Орієнтовний розрахунок на основі припущень, не підтверджені ціни.",
        "currency": currency,
        "days": days,
        "food": round(food, 2),
        "local_transport": round(transport, 2),
        "accommodation": round(accommodation, 2),
        "activities": round(activities, 2),
        "estimated_total": round(food + transport + accommodation + activities, 2),
    }


def suggest_daily_route(city, days, places, pace="помірний"):
    """Розподіляє запропоновані місця за днями; не перевіряє відстані чи години."""
    days = max(1, int(days))
    cleaned = list(dict.fromkeys(str(p).strip() for p in (places or []) if str(p).strip()))
    if not cleaned:
        return {"city": city, "days": days, "route": [],
                "notice": "Немає конкретних місць для розподілу. Уточни інтереси користувача."}
    per_day = ceil(len(cleaned) / days)
    route = []
    for i in range(days):
        group = cleaned[i * per_day:(i + 1) * per_day]
        if group:
            route.append({"day": i + 1, "places": group, "pace": pace})
    return {"city": city, "days": days, "route": route,
            "notice": "Чернетка розподілу місць, не перевірений маршрут з годинами роботи чи транспортом."}


def create_packing_list(days, season, trip_type):
    """Створює загальний список речей."""
    days = max(1, int(days))
    items = ["Документи та квитки", "Телефон і зарядний пристрій", "Гаманець і картка",
             "Засоби гігієни", "Зручне взуття", "Базова аптечка"]
    s = season.lower()
    if any(x in s for x in ("зима", "winter", "осінь", "autumn", "fall")):
        items += ["Тепла куртка", "Шапка та рукавички", "Шарф"]
    elif any(x in s for x in ("літо", "summer")):
        items += ["Сонцезахисний крем", "Окуляри", "Головний убір"]
    else:
        items += ["Одяг відповідно до прогнозу погоди"]
    t = trip_type.lower()
    if any(x in t for x in ("актив", "гори", "hiking")):
        items += ["Спортивний одяг", "Пляшка для води", "Дощовик"]
    if any(x in t for x in ("пляж", "beach")):
        items += ["Купальник", "Рушник", "Пляжна сумка"]
    return {"days": days, "suggested_clothing_sets": min(days, 7), "items": items,
            "notice": "Загальний список; перевір його відповідно до сезону, погоди та правил перевізника."}


def save_trip(email: str, itinerary: dict, budget: float, history=None) -> dict:
    """Зберігає погоджений маршрут, бюджет та історію діалогу у trips.json."""
    email = email.strip().lower()
    trips = _read_json(TRIPS_FILE, [])
    matches = [t for t in trips if t.get("email") == email]
    if not matches:
        return {"success": False, "error": "Не знайдено активної подорожі для цього email."}
    trip = matches[-1]
    trip["itinerary"] = itinerary if isinstance(itinerary, dict) else {"plan": itinerary}
    trip["budget"] = float(budget) if budget is not None else None
    trip["history"] = history or []
    trip["status"] = "saved"
    trip["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(TRIPS_FILE, trips)
    return {"success": True, "message": "Подорож збережено.", "trip_id": trip["trip_id"]}


def update_trip(email: str, changes: dict) -> dict:
    """Зберігає передані зміни в останній подорожі користувача."""
    email = email.strip().lower()
    trips = _read_json(TRIPS_FILE, [])
    for trip in reversed(trips):
        if trip.get("email") == email:
            trip.setdefault("itinerary", {})
            if not isinstance(trip["itinerary"], dict):
                trip["itinerary"] = {"plan": trip["itinerary"]}
            trip["itinerary"].update(changes or {})
            trip["status"] = "updated"
            trip["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_json(TRIPS_FILE, trips)
            return {"success": True, "message": "Зміни збережено.", "itinerary": trip["itinerary"]}
    return {"success": False, "error": "Не знайдено подорожі для цього email."}


FUNCTIONS = {
    "start_trip": start_trip,
    "estimate_budget": estimate_budget,
    "suggest_daily_route": suggest_daily_route,
    "create_packing_list": create_packing_list,
    "save_trip": save_trip,
    "update_trip": update_trip,
}
