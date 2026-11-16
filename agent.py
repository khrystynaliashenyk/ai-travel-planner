import json
from groq import Groq
from tools import FUNCTIONS, save_trip

MODEL_DEFAULT = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """
Ти — AI Travel Planner. Спілкуйся українською та працюй як діалоговий агент.
На початку попроси ім'я та email користувача. Не проси API-ключ у чаті.
Коли отримав обидва значення, виклич start_trip(name, email). Якщо функція повернула помилку,
уточни дані. Не починай збір деталей подорожі, доки реєстрація не успішна.

Після реєстрації послідовно з'ясуй: звідки й куди людина їде; дати або тривалість;
кількість мандрівників; загальний бюджет і валюту; інтереси; темп, транспорт,
проживання та харчування. Став одне-два питання за повідомлення, не перепитуй відоме.

Коли інформації достатньо, запропонуй маршрут. Використовуй інструменти за потреби:
suggest_daily_route розподіляє названі місця за днями; estimate_budget рахує лише з
переданих припущень; create_packing_list створює загальний список речей.
Не вигадуй місця як перевірені рекомендації, актуальні ціни, доступність, розклади чи бронювання.
Якщо припущення щодо витрат невідомі, спочатку уточни їх або чітко познач як умовні.

Якщо користувач змінює маршрут, бюджет, дати чи інші умови, збережи попередній контекст
і змінюй лише потрібне. Після кожної суттєвої зміни викликай update_trip, передаючи
email і лише зміни у форматі словника.

Коли користувач явно погодив фінальний план або просить його зберегти, виклич save_trip.
Передай email, повний підсумковий itinerary як словник і загальний бюджет числом.
Не стверджуй, що зберіг план, доки інструмент не повернув success=true.
Історію діалогу для save_trip система додасть автоматично.

Завжди враховуй встановлений бюджет. Якщо оцінка перевищує бюджет, запропонуй дешевші
варіанти. Усі неперевірені суми називай орієнтовними. Не заявляй, що бронювання здійснено.
"""

def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required}
    }}

TOOLS = [
    _tool("start_trip", "Зареєструвати користувача і почати планування. Викликати після отримання імені та email.",
          {"name": {"type": "string"}, "email": {"type": "string"}}, ["name", "email"]),
    _tool("suggest_daily_route", "Розподілити місця за днями; не перевіряє відстані чи години роботи.",
          {"city": {"type": "string"}, "days": {"type": "integer", "minimum": 1},
           "places": {"type": "array", "items": {"type": "string"}}, "pace": {"type": "string"}},
          ["city", "days", "places", "pace"]),
    _tool("estimate_budget", "Порахувати орієнтовний бюджет з припущень, не підтверджених цін.",
          {"days": {"type": "integer", "minimum": 1}, "daily_food": {"type": "number", "minimum": 0},
           "daily_transport": {"type": "number", "minimum": 0},
           "accommodation_per_night": {"type": "number", "minimum": 0},
           "activities_total": {"type": "number", "minimum": 0}, "currency": {"type": "string"}},
          ["days", "daily_food", "daily_transport", "accommodation_per_night", "activities_total", "currency"]),
    _tool("create_packing_list", "Створити загальний список речей.",
          {"days": {"type": "integer", "minimum": 1}, "season": {"type": "string"},
           "trip_type": {"type": "string"}}, ["days", "season", "trip_type"]),
    _tool("update_trip", "Зберегти зміни в останній подорожі користувача.",
          {"email": {"type": "string"}, "changes": {"type": "object"}},
          ["email", "changes"]),
    _tool("save_trip", "Зберегти погоджений фінальний план подорожі.",
          {"email": {"type": "string"}, "itinerary": {"type": "object"},
           "budget": {"type": "number"}},
          ["email", "itinerary", "budget"]),
]

class TravelAgent:
    def __init__(self, api_key: str, model: str = MODEL_DEFAULT):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.registered_email = None

    def start(self):
        return self.respond("Привіт! Почнімо планувати подорож.")

    def respond(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})
        for _ in range(6):
            response = self.client.chat.completions.create(
                model=self.model, messages=self.history, tools=TOOLS, tool_choice="auto"
            )
            message = response.choices[0].message
            self.history.append(message.model_dump(exclude_none=True))
            if not message.tool_calls:
                return message.content or "Не вдалося сформувати відповідь. Спробуй ще раз."

            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    name = call.function.name
                    if name == "start_trip":
                        result = FUNCTIONS[name](**args)
                        if result.get("success"):
                            self.registered_email = args["email"].strip().lower()
                    elif name == "save_trip":
                        args["history"] = self._serializable_history()
                        result = save_trip(**args)
                    elif name in FUNCTIONS:
                        if name == "update_trip" and not args.get("email"):
                            args["email"] = self.registered_email
                        result = FUNCTIONS[name](**args)
                    else:
                        result = {"success": False, "error": "Невідомий інструмент"}
                except Exception as exc:
                    result = {"success": False, "error": f"Помилка виконання інструмента"}

                self.history.append({
                    "role": "tool", "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)
                })

        response = self.client.chat.completions.create(model=self.model, messages=self.history)
        message = response.choices[0].message
        self.history.append(message.model_dump(exclude_none=True))
        return message.content or "План оновлено."

    def _serializable_history(self):
        result = []
        for item in self.history:
            role = item.get("role")
            if role == "system":
                continue
            if role == "assistant" and item.get("tool_calls"):
                content = json.dumps(item["tool_calls"], ensure_ascii=False, default=str)
                result.append({"role": "tool_call", "content": content})
            elif role in ("user", "assistant", "tool"):
                result.append({"role": role, "content": str(item.get("content", ""))})
        return result
