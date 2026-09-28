from datetime import date
from difflib import SequenceMatcher
from app.models import FoundItem


def score_item(item: FoundItem, query: str | None, color: str | None, location: str | None, date_lost: date | None) -> tuple[int, list[str]]:
    score, reasons = 0, []
    query = (query or "").strip().lower()
    if query:
        name_score = SequenceMatcher(None, query, item.name.lower()).ratio()
        description_score = SequenceMatcher(None, query, (item.description or "").lower()).ratio()
        if name_score >= .5: score += round(name_score * 35); reasons.append("Similar item name")
        if description_score >= .3: score += round(description_score * 15); reasons.append("Similar description")
        if item.brand and query in item.brand.lower(): score += 10; reasons.append("Matching brand or type")
    if color and item.color and color.lower().strip() == item.color.lower().strip(): score += 20; reasons.append("Similar color")
    if location and location.lower().strip() in item.location.lower(): score += 20; reasons.append("Same campus location")
    if date_lost:
        days = abs((item.date_found - date_lost).days)
        if days <= 7: score += 10; reasons.append("Found close to the date lost")
    return min(score, 100), reasons or ["Recently reported in this category"]
