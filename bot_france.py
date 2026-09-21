#!/usr/bin/env python3
"""Détecte les nouveaux tournois de Beach Tennis en France métropolitaine."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

TENUP_API = "https://tenup.fft.fr/back/public/v1/tournois"
TENUP_SEARCH = "https://tenup.fft.fr/recherche/tournois"
STATE_FILE = Path("seen_tournaments_france.json")
CURRENT_FILE = Path("current_tournaments_france.json")

RADIUS_KM = 199
SEARCH_DAYS = 365
PAGE_SIZE = 10
TIMEOUT_SECONDS = 30

# Maillage couvrant la France métropolitaine et la Corse avec des recherches
# de 199 km. Les doublons sont ensuite fusionnés par idHomologation.
SEARCH_CENTERS = [
    ("Brest", 48.3904, -4.4861),
    ("Rennes", 48.1173, -1.6778),
    ("Caen", 49.1829, -0.3707),
    ("Rouen", 49.4432, 1.0993),
    ("Lille", 50.6292, 3.0573),
    ("Reims", 49.2583, 4.0317),
    ("Paris", 48.8566, 2.3522),
    ("Orléans", 47.9030, 1.9093),
    ("Strasbourg", 48.5734, 7.7521),
    ("Nancy", 48.6921, 6.1844),
    ("Nantes", 47.2184, -1.5536),
    ("Tours", 47.3941, 0.6848),
    ("Dijon", 47.3220, 5.0415),
    ("Besançon", 47.2378, 6.0241),
    ("La Rochelle", 46.1603, -1.1511),
    ("Limoges", 45.8336, 1.2611),
    ("Clermont-Ferrand", 45.7772, 3.0870),
    ("Lyon", 45.7640, 4.8357),
    ("Grenoble", 45.1885, 5.7245),
    ("Bordeaux", 44.8378, -0.5792),
    ("Pau", 43.2951, -0.3708),
    ("Toulouse", 43.6047, 1.4442),
    ("Perpignan", 42.6887, 2.8948),
    ("Montpellier", 43.6108, 3.8767),
    ("Marseille", 43.2965, 5.3698),
    ("Nice", 43.7102, 7.2620),
    ("Ajaccio", 41.9192, 8.7386),
    ("Bastia", 42.6973, 9.4509),
]


class BotError(RuntimeError):
    pass


def request_payload(lat: float, lng: float, offset: int) -> dict[str, Any]:
    today = date.today()
    return {
        "dateDebut": today.isoformat(),
        "dateFin": (today + timedelta(days=SEARCH_DAYS)).isoformat(),
        "distance": RADIUS_KM,
        "from": offset,
        "lat": lat,
        "lng": lng,
        "pratique": "BEACH",
        "size": PAGE_SIZE,
        "sort": "DATE_DEBUT",
    }


def tournament_id(card: dict[str, Any]) -> str:
    homologation = card.get("idHomologation")
    if homologation:
        return str(homologation)
    return "|".join(str(card.get(key, "")) for key in (
        "libelleTournoi", "dateDebut", "dateFin", "ville", "club"
    ))


def fetch_zone(
    session: requests.Session, name: str, lat: float, lng: float
) -> list[dict[str, Any]]:
    cards_found: list[dict[str, Any]] = []
    offset = 0

    while True:
        response = session.post(
            TENUP_API,
            json=request_payload(lat, lng, offset),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        cards = data.get("cards", [])

        if not isinstance(cards, list):
            raise BotError(f"Réponse Ten'Up inattendue pour la zone {name}.")

        cards_found.extend(card for card in cards if isinstance(card, dict))

        if len(cards) < PAGE_SIZE:
            break
        offset += len(cards)
        if offset > 5000:
            raise BotError(f"Pagination anormalement longue pour la zone {name}.")

    print(f"{name}: {len(cards_found)} résultat(s)")
    return cards_found


def fetch_all_tournaments() -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://tenup.fft.fr",
        "Referer": TENUP_SEARCH,
        "User-Agent": "BeachTennisFranceNotifier/1.0",
    })

    unique: dict[str, dict[str, Any]] = {}
    for name, lat, lng in SEARCH_CENTERS:
        for card in fetch_zone(session, name, lat, lng):
            unique[tournament_id(card)] = card

    return list(unique.values())


def load_state() -> tuple[bool, set[str]]:
    if not STATE_FILE.exists():
        return False, set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise BotError(f"Impossible de lire {STATE_FILE}: {exc}") from exc

    if isinstance(data, list):
        return bool(data), {str(item) for item in data}
    if isinstance(data, dict):
        return bool(data.get("initialized", False)), {
            str(item) for item in data.get("ids", [])
        }
    raise BotError(f"Format invalide dans {STATE_FILE}.")


def save_state(initialized: bool, ids: set[str]) -> None:
    data = {"initialized": initialized, "ids": sorted(ids)}
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def save_current_tournaments(tournaments: list[dict[str, Any]]) -> None:
    ordered = sorted(tournaments, key=lambda card: str(card.get("dateDebut", "")))
    CURRENT_FILE.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def first_text(value: Any, default: str = "Non précisé") -> str:
    if value is None or value == "":
        return default
    if isinstance(value, dict):
        for key in ("libelle", "nom", "name", "ville"):
            if value.get(key):
                return str(value[key])
        return default
    if isinstance(value, list):
        texts = [first_text(item, "") for item in value]
        return ", ".join(text for text in texts if text) or default
    return str(value)


def french_date(raw: Any) -> str:
    if not raw:
        return "Date non précisée"
    try:
        parsed = date.fromisoformat(str(raw)[:10])
        months = (
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        )
        return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
    except ValueError:
        return str(raw)


def nature_label(card: dict[str, Any]) -> str:
    return first_text(card.get("naturesEpreuves"), "Épreuve non précisée")


def tournament_embed(card: dict[str, Any]) -> dict[str, Any]:
    title = first_text(card.get("libelleTournoi"), "Tournoi de Beach Tennis")
    city = first_text(card.get("ville"))
    club = first_text(card.get("club"), "")
    start = french_date(card.get("dateDebut"))
    end = french_date(card.get("dateFin"))
    date_text = start if start == end else f"Du {start} au {end}"
    place = city + (f" — {club}" if club and club.upper() != city.upper() else "")

    return {
        "title": title[:256],
        "url": TENUP_SEARCH,
        "color": 0x3498DB,
        "fields": [
            {"name": "📅 Date", "value": date_text[:1024], "inline": True},
            {"name": "📍 Lieu", "value": place[:1024], "inline": True},
            {"name": "👥 Épreuve", "value": nature_label(card)[:1024], "inline": False},
        ],
        "footer": {"text": f"Ten'Up • {tournament_id(card)}"},
    }


def send_to_discord(webhook_url: str, card: dict[str, Any]) -> None:
    payload = {
        "username": "Tournois Beach Tennis France",
        "content": "🇫🇷 🆕 **Nouveau tournoi de Beach Tennis en France métropolitaine !**",
        "embeds": [tournament_embed(card)],
        "allowed_mentions": {"parse": []},
    }
    response = requests.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
    if response.status_code == 429:
        retry_after = float(response.json().get("retry_after", 1))
        time.sleep(min(retry_after, 30))
        response = requests.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()


def main() -> int:
    webhook_url = os.getenv("DISCORD_WEBHOOK_FRANCE_URL", "").strip()
    if not webhook_url:
        raise BotError(
            "Le secret DISCORD_WEBHOOK_FRANCE_URL est absent dans GitHub Actions."
        )

    tournaments = fetch_all_tournaments()
    save_current_tournaments(tournaments)
    current_ids = {tournament_id(card) for card in tournaments}
    initialized, seen = load_state()

    if not initialized:
        save_state(True, current_ids)
        print(
            f"Initialisation nationale : {len(current_ids)} tournoi(s) "
            "mémorisé(s), aucune notification."
        )
        return 0

    new_cards = [card for card in tournaments if tournament_id(card) not in seen]
    new_cards.sort(key=lambda card: str(card.get("dateDebut", "")))

    sent_ids: set[str] = set()
    errors: list[str] = []
    for card in new_cards:
        try:
            send_to_discord(webhook_url, card)
            sent_ids.add(tournament_id(card))
            time.sleep(1)
        except requests.RequestException as exc:
            errors.append(f"{tournament_id(card)}: {exc}")

    save_state(True, seen | sent_ids)
    print(
        f"{len(tournaments)} tournoi(s) national(aux), "
        f"{len(new_cards)} nouveau(x), {len(sent_ids)} notification(s) envoyée(s)."
    )

    if errors:
        raise BotError("Échec de certaines notifications : " + "; ".join(errors))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.RequestException as exc:
        print(f"Erreur réseau : {exc}", file=sys.stderr)
        sys.exit(1)
    except BotError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
