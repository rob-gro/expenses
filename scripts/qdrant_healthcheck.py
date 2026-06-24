#!/usr/bin/env python3
"""
Qdrant health-check (read-only). Bezpieczny do uruchamiania z SSH/cron.
NIE tworzy, nie usuwa ani nie modyfikuje kolekcji. NIE drukuje sekretow.

Zakres: polaczenie z Qdrant, lista kolekcji, liczba punktow w kolekcji 'expenses'.

Exit codes:
  0 = OK
  1 = brak wymaganych zmiennych srodowiskowych
  2 = blad polaczenia/autoryzacji (np. 403)
  3 = kolekcja 'expenses' nie istnieje
  4 = blad nieoczekiwany
"""
import os
import sys
import hashlib
from urllib.parse import urlparse

# --- Jawne ladowanie .env dla SSH/cron, z lokalnym fallbackiem ---
from dotenv import load_dotenv
_PROD_ENV = "/home/robgro/expenses/.env"
if os.path.exists(_PROD_ENV):
    load_dotenv(dotenv_path=_PROD_ENV)   # cron/SSH: nie polegaj na cwd
else:
    load_dotenv()                        # lokalny fallback

COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "expenses")


def _fingerprint(secret: str) -> str:
    """Krotki, niewrazliwy odcisk do porownywania kluczy miedzy zrodlami."""
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def _sanitized(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")


def _strip_port(url: str) -> str:
    p = urlparse(url)
    netloc = p.hostname or ""
    return f"{p.scheme}://{netloc}{p.path}"


def _probe(url: str, api_key: str, label: str) -> bool:
    """Read-only proba: tylko get_collections(). Zwraca True jesli OK."""
    from qdrant_client import QdrantClient
    try:
        client = QdrantClient(url=url, api_key=api_key, timeout=30)
        cols = [c.name for c in client.get_collections().collections]
        print(f"  [{label}] OK -> kolekcje: {cols}")
        return True
    except Exception as e:
        print(f"  [{label}] BLAD: {type(e).__name__}: {e}")
        return False


def main() -> int:
    import importlib.metadata as md
    print(f"Python: {sys.version.split()[0]}")
    print(f"qdrant-client: {md.version('qdrant-client')}")

    url = os.getenv("QDRANT_URL")
    key = os.getenv("QDRANT_API_KEY")
    print(f"QDRANT_URL set: {bool(url)} | QDRANT_API_KEY set: {bool(key)}")
    if not url or not key:
        print("ERROR: brak QDRANT_URL lub QDRANT_API_KEY")
        return 1

    print(f"Host (sanitized): {_sanitized(url)}")
    print(f"API key: len={len(key)} fingerprint={_fingerprint(key)}")

    # --- Tryb porownania portu (read-only) przy diagnozie 403 ---
    if "--compare-port" in sys.argv:
        print("\n[compare-port] Porownanie URL z portem i bez (read-only):")
        ok_as_is = _probe(url, key, "as-is")
        ok_stripped = _probe(_strip_port(url), key, "port-stripped")
        if not ok_as_is and not ok_stripped:
            print("\nWNIOSEK: oba warianty zawiodly -> problem z kluczem API "
                  "(wygeneruj nowy klucz dla TEGO klastra i zsynchronizuj "
                  "panel AlwaysData oraz .env).")
            return 2
        return 0

    # --- Standardowy health-check ---
    from qdrant_client import QdrantClient
    try:
        client = QdrantClient(url=url, api_key=key, timeout=30)
        cols = [c.name for c in client.get_collections().collections]
        print(f"Kolekcje: {cols}")
    except Exception as e:
        print(f"ERROR: polaczenie/autoryzacja nieudane: {type(e).__name__}: {e}")
        print("Wskazowka: 403 'forbidden' = klucz API odrzucony. "
              "Uruchom z --compare-port aby potwierdzic.")
        return 2

    if COLLECTION not in cols:
        print(f"ERROR: kolekcja '{COLLECTION}' nie istnieje "
              f"(zostanie odtworzona przy najblizszym treningu).")
        return 3

    cnt = client.count(collection_name=COLLECTION, exact=True).count
    print(f"Kolekcja '{COLLECTION}': punktow={cnt}")

    print("HEALTHCHECK OK")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: nieoczekiwany blad: {type(e).__name__}: {e}")
        sys.exit(4)
