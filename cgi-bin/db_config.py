# -*- coding: utf-8 -*-
"""
Datenbank-Konfiguration für MariaDB (bioprakt17).
Credentials per Umgebungsvariable oder diese Datei (nicht in Git committen).
"""
import os

DB_CONFIG = {
    "host": os.environ.get("ALIGNMENT_DB_HOST", "mysql2-ext.bio.ifi.lmu.de"),
    "user": os.environ.get("ALIGNMENT_DB_USER", "bioprakt17"),
    "password": os.environ.get("ALIGNMENT_DB_PASSWORD", ""),  # Auf Server setzen: export ALIGNMENT_DB_PASSWORD='...'
    "database": os.environ.get("ALIGNMENT_DB_NAME", "bioprakt17"),
    "charset": "utf8mb4",
}

def get_connection():
    """Erstellt eine DB-Verbindung (PyMySQL)."""
    try:
        import pymysql
    except ImportError:
        return None
    if not DB_CONFIG.get("password"):
        return None
    try:
        return pymysql.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"],
            cursorclass=pymysql.cursors.DictCursor,
        )
    except Exception:
        return None
