import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")

DEFAULT_DATA = {
    "shop_name": "RazkiWaka 🍓",
    "categories": [
        {
            "title": "⚡ Waka10000 Pro — 14 000₸",
            "flavors": [
                {"name": "🍓🫐 Черника Малина Лимон", "available": True},
                {"name": "🍎🍑 Яблоко Персик", "available": True},
                {"name": "🥭🧊 Манго со льдом", "available": True},
                {"name": "🍓🍇 Клубника Виноград", "available": True},
                {"name": "🍏⚡ Кислое Яблоко", "available": True},
                {"name": "🫐🍒 Черника Вишня", "available": True},
                {"name": "🍉🧊 Арбуз со льдом", "available": True},
                {"name": "🍍🍋 Ананас Лимон", "available": True},
                {"name": "🍓🌿 Малина Мохито", "available": True},
                {"name": "🍬 Мармелад", "available": True},
                {"name": "🍓🍉 Клубника Арбуз", "available": True},
                {"name": "🍇🫐 Виноград Ягоды", "available": True},
                {"name": "🍓🍒 Тройная Ягода", "available": True},
                {"name": "🍓💗🍒 Клубника Малина Вишня", "available": True},
                {"name": "🌿❄️ Свежая Мята", "available": True},
            ],
        },
        {
            "title": "🔥 Waka10000 (старый) — 14 000₸",
            "flavors": [
                {"name": "🍉 Арбуз Холодок", "available": True},
                {"name": "🍏 Яблоко Свежесть", "available": True},
                {"name": "🥝 Клубника Киви", "available": True},
            ],
        },
    ],
}


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        _save(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_data() -> dict:
    return _load()


def get_categories() -> list[dict]:
    return _load()["categories"]


def toggle_flavor(cat_idx: int, flavor_idx: int) -> dict:
    """Переключает наличие вкуса и сохраняет. Возвращает обновленный вкус."""
    data = _load()
    flavor = data["categories"][cat_idx]["flavors"][flavor_idx]
    flavor["available"] = not flavor["available"]
    _save(data)
    return flavor


def add_flavor(cat_idx: int, name: str) -> None:
    data = _load()
    data["categories"][cat_idx]["flavors"].append({"name": name, "available": True})
    _save(data)


def remove_flavor(cat_idx: int, flavor_idx: int) -> None:
    data = _load()
    del data["categories"][cat_idx]["flavors"][flavor_idx]
    _save(data)


def all_flavors_flat() -> list[dict]:
    flavors = []
    for cat in get_categories():
        flavors.extend(cat["flavors"])
    return flavors


def available_flavor_names() -> list[str]:
    return [f["name"] for f in all_flavors_flat() if f["available"]]


def find_flavor(text: str) -> dict | None:
    text_norm = text.strip().lower()
    for flavor in all_flavors_flat():
        name_norm = flavor["name"].lower()
        if text_norm == name_norm or text_norm in name_norm:
            return flavor
    return None
