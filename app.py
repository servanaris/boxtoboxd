from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
import datetime as dt
import hashlib
import html
import os
import re
import secrets
import sqlite3
import unicodedata


APP_NAME = "box-to-boxd"
BASE_DIR = Path(__file__).resolve().parent
LEGACY_DB_PATH = BASE_DIR / "data" / "matchboxd.sqlite3"
DEFAULT_DB_PATH = BASE_DIR / "data" / "box_to_boxd.sqlite3"
DB_PATH = Path(
    os.environ.get("BOX_TO_BOXD_DB")
    or os.environ.get("MATCHBOXD_DB")
    or (LEGACY_DB_PATH if LEGACY_DB_PATH.exists() and not DEFAULT_DB_PATH.exists() else DEFAULT_DB_PATH)
)
STATIC_DIR = BASE_DIR / "static"
HOST = "127.0.0.1"
PORT = int(os.environ.get("BOX_TO_BOXD_PORT") or os.environ.get("MATCHBOXD_PORT", "8000"))

SUPPORTED_LANGS = {"tr", "en"}
DEFAULT_LANG = "tr"
SESSIONS = {}
SEARCH_RESULT_LIMIT = 80
HOME_CLASSIC_LIMIT = 8
LOG_CATALOG_LIMIT = 12
MATCH_RESULT_STEP = 24
MAX_MATCH_RESULT_LIMIT = 240
MATCH_RESULTS_ANCHOR = "match-results"
MATCH_FILTER_KEYS = ("team", "opponent", "year", "organization")
SEARCH_INDEX_COLUMNS = [
    "match_id",
    "home_team",
    "away_team",
    "title",
    "competition",
    "league_name",
    "country",
    "season",
    "match_date",
    "league_aliases",
    "round_name",
    "stage",
    "summary",
    "summary_en",
]
LEAGUE_NAME_ALIASES = {
    "tr-super-lig": [
        "Süper Lig",
        "Super Lig",
        "Turkish Süper Lig",
        "Turkish Super Lig",
        "Turkish Super League",
        "Turkey Super League",
        "Türkiye Süper Lig",
        "Türkiye Super League",
        "Trendyol Süper Lig",
        "Trendyol Super Lig",
        "Spor Toto Süper Lig",
        "Spor Toto Super Lig",
        "Turkcell Süper Lig",
        "Turkcell Super Lig",
        "STSL",
        "TSL",
    ],
    "laliga": [
        "LaLiga",
        "La Liga",
        "LaLiga EA Sports",
        "LaLiga Santander",
        "Primera División",
        "Spanish La Liga",
    ],
    "serie-a": [
        "Serie A",
        "Serie A TIM",
        "Serie A Enilive",
        "Italian Serie A",
    ],
    "ligue-1": [
        "Ligue 1",
        "Ligue 1 Uber Eats",
        "Ligue 1 McDonald's",
        "French Ligue 1",
    ],
    "uefa-europa-league": [
        "UEFA Europa League",
        "Europa League",
        "UEFA Cup",
    ],
    "uefa-conference-league": [
        "UEFA Conference League",
        "UEFA Europa Conference League",
        "Conference League",
    ],
    "afc-champions-league": [
        "AFC Champions League Elite",
        "AFC Champions League",
        "Asian Champions League",
    ],
    "concacaf-champions-cup": [
        "Concacaf Champions Cup",
        "CONCACAF Champions League",
        "Concacaf Champions League",
    ],
}
COMPETITION_NAME_ALIASES = {
    "uefa cup": ["UEFA Europa League", "Europa League"],
    "uefa europa league": ["UEFA Cup"],
    "concacaf champions league": ["Concacaf Champions Cup"],
    "concacaf champions cup": ["CONCACAF Champions League"],
    "afc champions league": ["AFC Champions League Elite", "Asian Champions League"],
    "afc champions league elite": ["AFC Champions League", "Asian Champions League"],
}
SEARCH_ALIASES = {
    "afc": ["AFC"],
    "abd": ["United", "States"],
    "almanya": ["Germany"],
    "amerika": ["United", "States"],
    "arjantin": ["Argentina"],
    "arnavutluk": ["Albania"],
    "avusturya": ["Austria"],
    "avustralya": ["Australia"],
    "azerbaycan": ["Azerbaijan"],
    "belcika": ["Belgium"],
    "belçika": ["Belgium"],
    "besiktas": ["Beşiktaş"],
    "bjk": ["Beşiktaş"],
    "brezilya": ["Brazil"],
    "cl": ["UEFA", "Champions", "League"],
    "cekya": ["Czech", "Republic"],
    "çekya": ["Czech", "Republic"],
    "cin": ["China"],
    "çin": ["China"],
    "danimarka": ["Denmark"],
    "dunya": ["World"],
    "dünya": ["World"],
    "ecl": ["UEFA", "Conference", "League"],
    "ekvador": ["Ecuador"],
    "ermenistan": ["Armenia"],
    "epl": ["Premier", "League"],
    "fb": ["Fenerbahçe"],
    "fenerbahce": ["Fenerbahçe"],
    "fas": ["Morocco"],
    "fildisi": ["Ivory"],
    "fransa": ["France"],
    "gs": ["Galatasaray"],
    "galler": ["Wales"],
    "gana": ["Ghana"],
    "gurcistan": ["Georgia"],
    "gürcistan": ["Georgia"],
    "hirvatistan": ["Croatia"],
    "hollanda": ["Netherlands"],
    "ingiltere": ["England"],
    "iran": ["Iran"],
    "irak": ["Iraq"],
    "irlanda": ["Ireland"],
    "ispanya": ["Spain"],
    "israil": ["Israel"],
    "isvec": ["Sweden"],
    "isveç": ["Sweden"],
    "isvicre": ["Switzerland"],
    "isviçre": ["Switzerland"],
    "italya": ["Italy"],
    "izlanda": ["Iceland"],
    "japonya": ["Japan"],
    "kamerun": ["Cameroon"],
    "kanada": ["Canada"],
    "karadag": ["Montenegro"],
    "karadağ": ["Montenegro"],
    "katar": ["Qatar"],
    "kolombiya": ["Colombia"],
    "kore": ["Korea"],
    "kosta": ["Costa"],
    "kupasi": ["Cup"],
    "kupası": ["Cup"],
    "ligi": ["League"],
    "lig": ["League"],
    "macaristan": ["Hungary"],
    "pl": ["Premier", "League"],
    "meksika": ["Mexico"],
    "misir": ["Egypt"],
    "mısır": ["Egypt"],
    "nijerya": ["Nigeria"],
    "norvec": ["Norway"],
    "norveç": ["Norway"],
    "paraguay": ["Paraguay"],
    "peru": ["Peru"],
    "polonya": ["Poland"],
    "portekiz": ["Portugal"],
    "romanya": ["Romania"],
    "rusya": ["Russia"],
    "süper": ["Süper"],
    "sampiyonlar": ["UEFA", "Champions", "League"],
    "sampiyonasi": ["Championship"],
    "şampiyonlar": ["UEFA", "Champions", "League"],
    "şampiyonası": ["Championship"],
    "senegal": ["Senegal"],
    "sirbistan": ["Serbia"],
    "sırbistan": ["Serbia"],
    "slovakya": ["Slovakia"],
    "slovenya": ["Slovenia"],
    "super": ["Süper"],
    "superlig": ["Süper", "Lig"],
    "stsl": ["Spor", "Toto", "Süper", "Lig"],
    "sili": ["Chile"],
    "şili": ["Chile"],
    "tunus": ["Tunisia"],
    "turkiye": ["Turkey"],
    "türkiye": ["Turkey"],
    "manu": ["Manchester", "United"],
    "ts": ["Trabzonspor"],
    "tsl": ["Süper", "Lig"],
    "ucl": ["UEFA", "Champions", "League"],
    "uecl": ["UEFA", "Conference", "League"],
    "uel": ["UEFA", "Europa", "League"],
    "ukrayna": ["Ukraine"],
    "uruguay": ["Uruguay"],
    "utd": ["United"],
    "yunanistan": ["Greece"],
}
SEARCH_PHRASE_ALIASES = {
    ("afrika", "kupasi"): ["Africa", "Cup", "of", "Nations"],
    ("afrika", "uluslar", "kupasi"): ["Africa", "Cup", "of", "Nations"],
    ("amerika", "birlesik", "devletleri"): ["United", "States"],
    ("asya", "kupasi"): ["AFC", "Asian", "Cup"],
    ("avrupa", "ligi"): ["UEFA", "Europa", "League"],
    ("avrupa", "sampiyonasi"): ["UEFA", "EURO"],
    ("bae",): ["United", "Arab", "Emirates"],
    ("birlesik", "arap", "emirlikleri"): ["United", "Arab", "Emirates"],
    ("dunya", "kupasi"): ["FIFA", "World", "Cup"],
    ("fildisi", "sahili"): ["Ivory", "Coast"],
    ("guney", "afrika"): ["South", "Africa"],
    ("guney", "kore"): ["South", "Korea"],
    ("konferans", "ligi"): ["UEFA", "Conference", "League"],
    ("kosta", "rika"): ["Costa", "Rica"],
    ("kuzey", "irlanda"): ["Northern", "Ireland"],
    ("sampiyonlar", "ligi"): ["UEFA", "Champions", "League"],
    ("spor", "toto", "super", "lig"): ["Spor", "Toto", "Süper", "Lig"],
    ("spor", "toto", "süper", "lig"): ["Spor", "Toto", "Süper", "Lig"],
    ("suudi", "arabistan"): ["Saudi", "Arabia"],
    ("super", "lig"): ["Süper", "Lig"],
    ("turkcell", "super", "lig"): ["Turkcell", "Süper", "Lig"],
    ("turkcell", "süper", "lig"): ["Turkcell", "Süper", "Lig"],
    ("trendyol", "super", "lig"): ["Trendyol", "Süper", "Lig"],
    ("trendyol", "süper", "lig"): ["Trendyol", "Süper", "Lig"],
    ("yeni", "zelanda"): ["New", "Zealand"],
}


TRANSLATIONS = {
    "tr": {
        "add_to_watchlist": "izleme listesine ekle",
        "admin_review_hint": "gerçek olduğunu doğruladığın maçları kataloga ekleyebilirsin.",
        "admin_only": "bu sayfa sadece yönetici için.",
        "approve": "onayla ve kataloga ekle",
        "auth_copy": "puanlarını kaydet, yorum yaz ve izlediğin futbolun günlüğünü tut.",
        "avg": "ort.",
        "away_team": "deplasman takımı",
        "back_home": "eve dön",
        "already_have_account": "hesabın var mı?",
        "auth_dev_hint": "yerel geliştirme modunda linki burada gösteriyorum.",
        "catalog_matches": "katalogdaki maçlar",
        "classic_hint": "öneriler birkaç günde bir yenilenir",
        "competition": "lig / turnuva",
        "competition_database": "organizasyon veritabanı",
        "create_account": "hesap oluştur",
        "clear_filters": "temizle",
        "data_scope": "2000/01 sonrası sezon indeksi",
        "date": "tarih",
        "diary": "günlük",
        "discover": "ev",
        "empty_diary": "günlüğün boş. bir maç açıp ilk yorumunu yaz.",
        "empty_matches": "maç bulunamadı. başka bir arama dene ya da öneri gönder.",
        "empty_reviews": "henüz yorum yok.",
        "empty_reviews_feed": "henüz yorum yok. ilk düdüğü sen çal.",
        "empty_watchlist": "henüz kaydedilmiş maç yok.",
        "email": "e-posta",
        "email_verification_copy": "giriş yapmadan önce e-postanı doğrula.",
        "email_verification_link": "doğrulama linki",
        "email_verification_required": "giriş yapmak için önce e-postanı doğrula.",
        "email_verification_sent": "hesabını oluşturduk. giriş yapmadan önce e-postanı doğrula.",
        "email_verification_success": "e-posta doğrulandı. şimdi giriş yapabilirsin.",
        "email_verification_title": "e-postanı doğrula",
        "evidence_url": "kaynak linki",
        "evidence_placeholder": "TFF, lig sitesi, kulüp sitesi veya güvenilir maç sayfası",
        "field_error": "tüm zorunlu alanları doldur, geçerli bir tarih ve kaynak linki kullan.",
        "filter": "filtrele",
        "find_match": "maç ara",
        "forgot_password": "şifremi unuttum",
        "forgot_password_copy": "e-postanı yaz, şifre sıfırlama linkini oluşturalım.",
        "football_diary": "futbol günlüğü ve yorumları",
        "grow_catalog": "kataloğu birlikte büyüt",
        "home_team": "ev sahibi takım",
        "home_hero": "izlediğin maçları puanla. sezonunun hikayesini tut.",
        "home_support": "klasik finaller, derbiler, Süper Lig geceleri ve aklından çıkmayan kaotik maçlar için kişisel futbol arşivin.",
        "join": "katıl",
        "joined": "katıldı",
        "language": "dil",
        "league_database": "organizasyon veritabanı",
        "leagues": "lig",
        "log": "log",
        "log_after_approval": "onaylanınca bu maçı günlüğüme de ekle",
        "log_copy": "önce katalogdaki maçı bulup yorumla. maç yoksa kaynak linkiyle öner; yönetici doğrulayınca kataloga düşsün.",
        "log_in": "giriş yap",
        "log_in_required_diary": "günlüğünü görmek için giriş yap.",
        "log_in_required_log": "maç loglamak veya öneri göndermek için giriş yap.",
        "log_in_required_watchlist": "izleme listeni görmek için giriş yap.",
        "log_out": "çıkış",
        "match_date": "maç tarihi",
        "match_review_error": "puan, tarih ve yorum metni ekle.",
        "matches": "maç",
        "moderation": "moderasyon",
        "new_here": "yeni misin?",
        "new_password": "yeni şifre",
        "no_ratings": "henüz puan yok",
        "not_found_copy": "aradığın sayfa yok.",
        "not_found_title": "bu sayfa ofsaytta.",
        "note": "not",
        "note_placeholder": "skor, hafta, maç linki veya doğrulamayı kolaylaştıracak kısa bilgi.",
        "optional_log": "opsiyonel log",
        "opponent": "rakip",
        "opponent_placeholder": "Galatasaray",
        "password": "şifre",
        "pending": "bekliyor",
        "pending_submissions": "bekleyen öneriler",
        "popular_matches": "klasik maçlar",
        "profile": "profil",
        "rating": "puanın",
        "recent_reviews": "son yorumlar",
        "reject": "reddet",
        "remember_me": "kaydet",
        "remove_from_watchlist": "izleme listesinden çıkar",
        "reset_password": "şifreyi sıfırla",
        "reset_password_copy": "yeni şifreni belirle.",
        "review": "yorum",
        "review_placeholder": "maç sana nasıl hissettirdi?",
        "reviews": "yorum",
        "save_review": "yorumu güncelle",
        "search": "ara",
        "search_placeholder": "takım, ülke, lig",
        "search_results": "arama sonuçları",
        "search_suggestions": "hızlı aramalar",
        "send_reset_link": "sıfırlama linki gönder",
        "season": "sezon",
        "seasons": "sezon",
        "select_league": "organizasyon seç",
        "show_more": "daha fazlasını göster",
        "source": "kaynak",
        "submit_for_review": "veritabanına ekle",
        "submission_log_hint": "kutuyu işaretlersen, öneri onaylandığında yorumun otomatik olarak günlüğüne eklenir.",
        "submission_received": "önerin kaydedildi. yönetici doğrulayınca kataloga eklenecek.",
        "submissions": "öneri",
        "password_reset_ready": "şifre sıfırlama linkin hazır.",
        "password_reset_success": "şifren güncellendi. giriş yapabilirsin.",
        "password_reset_unavailable": "bu e-posta için hesap bulamadım.",
        "token_invalid": "link geçersiz veya süresi dolmuş.",
        "team": "takım",
        "team_placeholder": "Beşiktaş",
        "teams": "takım",
        "organizations": "organizasyon",
        "username": "kullanıcı adı",
        "username_or_email": "kullanıcı adı veya e-posta",
        "watchlist": "izleme listesi",
        "watched_on": "izleme tarihi",
        "watched_on_sentence": "şu tarihte izledi:",
        "want_to_log": "bu maçı loglamak ister misin?",
        "want_to_log_copy": "puanlamak, yorumlamak veya izleme listene almak için hesap oluştur.",
        "year": "yıl",
        "year_placeholder": "2024 veya 2024/25",
        "your_logbook": "kayıt defterin",
    },
    "en": {
        "add_to_watchlist": "add to watchlist",
        "admin_review_hint": "approve matches only after you verify that they really exist.",
        "admin_only": "this page is only for the admin.",
        "approve": "approve and add to catalog",
        "auth_copy": "save ratings, write reviews, and build a diary of the football you watch.",
        "avg": "avg",
        "away_team": "away team",
        "back_home": "back home",
        "already_have_account": "already have an account?",
        "auth_dev_hint": "in local development, the link is shown here.",
        "catalog_matches": "catalog matches",
        "classic_hint": "suggestions refresh every few days",
        "competition": "league / competition",
        "competition_database": "organization database",
        "create_account": "create account",
        "clear_filters": "clear",
        "data_scope": "season index since 2000/01",
        "date": "date",
        "diary": "diary",
        "discover": "home",
        "empty_diary": "your diary is empty. open a match and post your first review.",
        "empty_matches": "no matches found. try a different search or submit one.",
        "empty_reviews": "no reviews yet.",
        "empty_reviews_feed": "no reviews yet. be first on the team sheet.",
        "empty_watchlist": "no saved matches yet.",
        "email": "email",
        "email_verification_copy": "verify your email before logging in.",
        "email_verification_link": "verification link",
        "email_verification_required": "verify your email before logging in.",
        "email_verification_sent": "your account was created. verify your email before logging in.",
        "email_verification_success": "email verified. you can log in now.",
        "email_verification_title": "verify your email",
        "evidence_url": "source link",
        "evidence_placeholder": "TFF, league site, club site, or reliable match page",
        "field_error": "fill every required field and use a valid date and source link.",
        "filter": "filter",
        "find_match": "find a match",
        "forgot_password": "forgot password",
        "forgot_password_copy": "enter your email and we will create a password reset link.",
        "football_diary": "football diary and reviews",
        "grow_catalog": "grow the catalog together",
        "home_team": "home team",
        "home_hero": "rate the matches you watched. keep the story of your season.",
        "home_support": "your personal football archive for classic finals, derbies, league nights, and chaotic matches you cannot stop thinking about.",
        "join": "join",
        "joined": "joined",
        "language": "language",
        "league_database": "organization database",
        "leagues": "leagues",
        "log": "log",
        "log_after_approval": "add this match to my diary after approval",
        "log_copy": "find an existing match and review it. if the match is missing, submit it with a source link so an admin can verify it before it enters the catalog.",
        "log_in": "log in",
        "log_in_required_diary": "log in to view your diary.",
        "log_in_required_log": "log in to log matches or submit a match.",
        "log_in_required_watchlist": "log in to view your watchlist.",
        "log_out": "log out",
        "match_date": "match date",
        "match_review_error": "add a rating, date, and review text.",
        "matches": "matches",
        "moderation": "moderation",
        "new_here": "new here?",
        "new_password": "new password",
        "no_ratings": "no ratings yet",
        "not_found_copy": "the page you asked for does not exist.",
        "not_found_title": "that page is offside.",
        "note": "note",
        "note_placeholder": "score, matchweek, match link, or anything that helps verification.",
        "optional_log": "optional log",
        "opponent": "opponent",
        "opponent_placeholder": "Galatasaray",
        "password": "password",
        "pending": "pending",
        "pending_submissions": "pending submissions",
        "popular_matches": "classics",
        "profile": "profile",
        "rating": "your rating",
        "recent_reviews": "recent reviews",
        "reject": "reject",
        "remember_me": "save",
        "remove_from_watchlist": "remove from watchlist",
        "reset_password": "reset password",
        "reset_password_copy": "choose a new password.",
        "review": "review",
        "review_placeholder": "what did the match feel like?",
        "reviews": "reviews",
        "save_review": "update review",
        "search": "search",
        "search_placeholder": "club, nation, league",
        "search_results": "search results",
        "search_suggestions": "quick searches",
        "send_reset_link": "send reset link",
        "season": "season",
        "seasons": "seasons",
        "select_league": "select organization",
        "show_more": "show more",
        "source": "source",
        "submit_for_review": "add to database",
        "submission_log_hint": "if checked, your review will be posted automatically when the submission is approved.",
        "submission_received": "your submission was saved. it will be added to the catalog after admin verification.",
        "submissions": "submissions",
        "password_reset_ready": "your password reset link is ready.",
        "password_reset_success": "your password was updated. you can log in now.",
        "password_reset_unavailable": "I could not find an account for that email.",
        "token_invalid": "that link is invalid or expired.",
        "team": "team",
        "team_placeholder": "Beşiktaş",
        "teams": "teams",
        "organizations": "organizations",
        "username": "username",
        "username_or_email": "username or email",
        "watchlist": "watchlist",
        "watched_on": "watched on",
        "watched_on_sentence": "watched on",
        "want_to_log": "want to log this match?",
        "want_to_log_copy": "create an account to rate it, review it, or keep it in your watchlist.",
        "year": "year",
        "year_placeholder": "2024 or 2024/25",
        "your_logbook": "your logbook",
    },
}


SEASON_END_YEAR = 2026

SEED_LEAGUES = [
    {
        "code": "tr-super-lig",
        "name": "Trendyol Süper Lig",
        "country": "Türkiye",
        "season": "2025/26",
        "tier": 1,
        "color": "#d61f3c",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://www.tff.org/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "premier-league",
        "name": "Premier League",
        "country": "England",
        "season": "2025/26",
        "tier": 1,
        "color": "#3d195b",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://www.premierleague.com/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "laliga",
        "name": "LaLiga EA Sports",
        "country": "Spain",
        "season": "2025/26",
        "tier": 1,
        "color": "#e23d28",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://www.laliga.com/en-GB/laliga-easports",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "serie-a",
        "name": "Serie A Enilive",
        "country": "Italy",
        "season": "2025/26",
        "tier": 1,
        "color": "#1d4ed8",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://en.legaseriea.it/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "bundesliga",
        "name": "Bundesliga",
        "country": "Germany",
        "season": "2025/26",
        "tier": 1,
        "color": "#d71920",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://www.bundesliga.com/en/bundesliga",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "ligue-1",
        "name": "Ligue 1 McDonald's",
        "country": "France",
        "season": "2025/26",
        "tier": 1,
        "color": "#082f49",
        "kind": "domestic-league",
        "confederation": "UEFA",
        "source_url": "https://www.ligue1.com/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "fifa-world-cup",
        "name": "FIFA World Cup",
        "country": "world",
        "season": "2026",
        "tier": 1,
        "color": "#1f7a4d",
        "kind": "national-tournament",
        "confederation": "FIFA",
        "source_url": "https://www.fifa.com/en/tournaments/mens/worldcup",
        "season_mode": "editions",
        "editions": [2002, 2006, 2010, 2014, 2018, 2022, 2026],
    },
    {
        "code": "uefa-euro",
        "name": "UEFA EURO",
        "country": "Europe",
        "season": "2024",
        "tier": 1,
        "color": "#2157a4",
        "kind": "continental-cup",
        "confederation": "UEFA",
        "source_url": "https://www.uefa.com/uefaeuro/history/",
        "season_mode": "editions",
        "editions": [2000, 2004, 2008, 2012, 2016, 2020, 2024],
    },
    {
        "code": "copa-america",
        "name": "Copa América",
        "country": "South America",
        "season": "2024",
        "tier": 1,
        "color": "#22a3dd",
        "kind": "continental-cup",
        "confederation": "CONMEBOL",
        "source_url": "https://copaamerica.com/",
        "season_mode": "editions",
        "editions": [2001, 2004, 2007, 2011, 2015, 2016, 2019, 2021, 2024],
    },
    {
        "code": "afcon",
        "name": "Africa Cup of Nations",
        "country": "Africa",
        "season": "2025",
        "tier": 1,
        "color": "#178f4f",
        "kind": "continental-cup",
        "confederation": "CAF",
        "source_url": "https://www.cafonline.com/caf-africa-cup-of-nations/",
        "season_mode": "editions",
        "editions": [2000, 2002, 2004, 2006, 2008, 2010, 2012, 2013, 2015, 2017, 2019, 2021, 2023, 2025],
    },
    {
        "code": "afc-asian-cup",
        "name": "AFC Asian Cup",
        "country": "Asia",
        "season": "2023",
        "tier": 1,
        "color": "#c026d3",
        "kind": "continental-cup",
        "confederation": "AFC",
        "source_url": "https://www.the-afc.com/en/national/afc_asian_cup.html",
        "season_mode": "editions",
        "editions": [2000, 2004, 2007, 2011, 2015, 2019, 2023],
    },
    {
        "code": "concacaf-gold-cup",
        "name": "Concacaf Gold Cup",
        "country": "North America",
        "season": "2025",
        "tier": 1,
        "color": "#d4a017",
        "kind": "continental-cup",
        "confederation": "CONCACAF",
        "source_url": "https://www.concacaf.com/gold-cup/",
        "season_mode": "editions",
        "editions": [2000, 2002, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025],
    },
    {
        "code": "ofc-nations-cup",
        "name": "OFC Nations Cup",
        "country": "Oceania",
        "season": "2024",
        "tier": 1,
        "color": "#0f766e",
        "kind": "continental-cup",
        "confederation": "OFC",
        "source_url": "https://www.oceaniafootball.com/",
        "season_mode": "editions",
        "editions": [2000, 2002, 2004, 2008, 2012, 2016, 2024],
    },
    {
        "code": "uefa-champions-league",
        "name": "UEFA Champions League",
        "country": "Europe",
        "season": "2025/26",
        "tier": 1,
        "color": "#1d4ed8",
        "kind": "club-tournament",
        "confederation": "UEFA",
        "source_url": "https://www.uefa.com/uefachampionsleague/history/seasons/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "uefa-europa-league",
        "name": "UEFA Europa League",
        "country": "Europe",
        "season": "2025/26",
        "tier": 2,
        "color": "#f97316",
        "kind": "club-tournament",
        "confederation": "UEFA",
        "source_url": "https://www.uefa.com/uefaeuropaleague/history/seasons/",
        "season_mode": "split",
        "start_year": 2000,
    },
    {
        "code": "uefa-conference-league",
        "name": "UEFA Conference League",
        "country": "Europe",
        "season": "2025/26",
        "tier": 3,
        "color": "#16a34a",
        "kind": "club-tournament",
        "confederation": "UEFA",
        "source_url": "https://www.uefa.com/uefaconferenceleague/history/seasons/",
        "season_mode": "split",
        "start_year": 2021,
    },
    {
        "code": "copa-libertadores",
        "name": "Copa Libertadores",
        "country": "South America",
        "season": "2026",
        "tier": 1,
        "color": "#111827",
        "kind": "club-tournament",
        "confederation": "CONMEBOL",
        "source_url": "https://www.conmebol.com/libertadores/",
        "season_mode": "annual",
        "start_year": 2000,
    },
    {
        "code": "afc-champions-league",
        "name": "AFC Champions League Elite",
        "country": "Asia",
        "season": "2025/26",
        "tier": 1,
        "color": "#7c3aed",
        "kind": "club-tournament",
        "confederation": "AFC",
        "source_url": "https://www.the-afc.com/en/club/afc_champions_league_elite.html",
        "season_mode": "split",
        "start_year": 2002,
    },
    {
        "code": "concacaf-champions-cup",
        "name": "Concacaf Champions Cup",
        "country": "North America",
        "season": "2026",
        "tier": 1,
        "color": "#0e7490",
        "kind": "club-tournament",
        "confederation": "CONCACAF",
        "source_url": "https://www.concacaf.com/champions-cup/",
        "season_mode": "annual",
        "start_year": 2000,
    },
]


SEED_TEAMS = {
    "tr-super-lig": [
        "Corendon Alanyaspor", "Antalyaspor", "Rams Başakşehir", "Beşiktaş", "Eyüpspor",
        "Fatih Karagümrük", "Fenerbahçe", "Galatasaray", "Gaziantep FK", "Gençlerbirliği",
        "Göztepe", "Kasımpaşa", "Kayserispor", "Kocaelispor", "Konyaspor",
        "Çaykur Rizespor", "Samsunspor", "Trabzonspor",
    ],
    "premier-league": [
        "Arsenal", "Aston Villa", "AFC Bournemouth", "Brentford", "Brighton & Hove Albion",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds United",
        "Liverpool", "Manchester City", "Manchester United", "Newcastle United",
        "Nottingham Forest", "Sunderland", "Tottenham Hotspur", "West Ham United",
        "Wolverhampton Wanderers",
    ],
    "laliga": [
        "Athletic Club", "Atlético de Madrid", "CA Osasuna", "Celta", "Deportivo Alavés",
        "Elche CF", "FC Barcelona", "Getafe CF", "Girona FC", "Levante UD",
        "Rayo Vallecano", "RCD Espanyol de Barcelona", "RCD Mallorca", "Real Betis",
        "Real Madrid", "Real Oviedo", "Real Sociedad", "Sevilla FC", "Valencia CF",
        "Villarreal CF",
    ],
    "serie-a": [
        "Atalanta", "Bologna", "Cagliari", "Como", "Cremonese", "Fiorentina", "Genoa",
        "Hellas Verona", "Inter", "Juventus", "Lazio", "Lecce", "Milan", "Napoli",
        "Parma", "Pisa", "Roma", "Sassuolo", "Torino", "Udinese",
    ],
    "bundesliga": [
        "Bayern Munich", "Bayer Leverkusen", "Eintracht Frankfurt", "Borussia Dortmund",
        "Freiburg", "Mainz", "RB Leipzig", "Werder Bremen", "VfB Stuttgart",
        "Borussia Mönchengladbach", "Wolfsburg", "Augsburg", "Union Berlin",
        "St. Pauli", "Hoffenheim", "Heidenheim", "1. FC Köln", "Hamburger SV",
    ],
    "ligue-1": [
        "AJ Auxerre", "Angers SCO", "AS Monaco", "FC Lorient", "FC Metz", "FC Nantes",
        "Le Havre AC", "LOSC Lille", "Olympique Lyonnais", "Olympique de Marseille",
        "OGC Nice", "Paris FC", "Paris Saint-Germain", "RC Lens", "RC Strasbourg Alsace",
        "Stade Brestois 29", "Stade Rennais FC", "Toulouse FC",
    ],
}


SEED_MATCHES = [
    {
        "home_team": "Argentina",
        "away_team": "France",
        "competition": "FIFA World Cup Final",
        "season": "2022",
        "match_date": "2022-12-18",
        "venue": "",
        "summary": "Momentumun defalarca el değiştirdiği, uzatmalara ve penaltılara giden çılgın final.",
        "summary_en": "A wild final with momentum swings, extra time, and a penalty shootout.",
        "poster_color": "#37a06f",
    },
    {
        "home_team": "Liverpool",
        "away_team": "AC Milan",
        "competition": "UEFA Champions League Final",
        "season": "2004/05",
        "match_date": "2005-05-25",
        "venue": "",
        "summary": "İstanbul geri dönüşü: devre arasında üç fark, altı dakika içinde eşitlik.",
        "summary_en": "The Istanbul comeback: three goals down at half-time, level after six minutes.",
        "poster_color": "#c9343f",
    },
    {
        "home_team": "Deportivo Alavés",
        "away_team": "Liverpool",
        "competition": "UEFA Cup Final",
        "season": "2000/01",
        "match_date": "2001-05-16",
        "venue": "",
        "summary": "Dokuz gollü final, altın gol ve kupanın sahibini belirleyen nefes kesici gece.",
        "summary_en": "A nine-goal final decided by golden goal in a breathless European night.",
        "poster_color": "#f97316",
    },
    {
        "home_team": "Brazil",
        "away_team": "Germany",
        "competition": "FIFA World Cup Final",
        "season": "2002",
        "match_date": "2002-06-30",
        "venue": "",
        "summary": "Ronaldo'nun iki golüyle Brezilya'nın beşinci Dünya Kupası'na uzandığı final.",
        "summary_en": "Ronaldo scored twice as Brazil claimed their fifth World Cup.",
        "poster_color": "#f0b429",
    },
    {
        "home_team": "Portugal",
        "away_team": "Greece",
        "competition": "UEFA EURO Final",
        "season": "2004",
        "match_date": "2004-07-04",
        "venue": "",
        "summary": "Turnuvanın ev sahibine karşı tamamlanan büyük Yunanistan sürprizi.",
        "summary_en": "Greece completed a stunning upset against the host nation.",
        "poster_color": "#2157a4",
    },
    {
        "home_team": "Italy",
        "away_team": "France",
        "competition": "FIFA World Cup Final",
        "season": "2006",
        "match_date": "2006-07-09",
        "venue": "",
        "summary": "Uzatmalar, büyük gerilim ve penaltılarla İtalya'nın kupaya uzandığı final.",
        "summary_en": "Italy won a tense final after extra time and penalties.",
        "poster_color": "#1d4ed8",
    },
    {
        "home_team": "Manchester United",
        "away_team": "Chelsea",
        "competition": "UEFA Champions League Final",
        "season": "2007/08",
        "match_date": "2008-05-21",
        "venue": "",
        "summary": "Yağmur altında penaltılarla sonuçlanan ilk İngiliz Şampiyonlar Ligi finali.",
        "summary_en": "The first all-English Champions League final went to penalties in Moscow.",
        "poster_color": "#7f1d1d",
    },
    {
        "home_team": "Chelsea",
        "away_team": "Barcelona",
        "competition": "UEFA Champions League Semi-final",
        "season": "2008/09",
        "match_date": "2009-05-06",
        "venue": "",
        "summary": "Son dakikadaki Iniesta golüyle hafızalara kazınan yarı final.",
        "summary_en": "Iniesta's late strike made this semi-final impossible to forget.",
        "poster_color": "#3256a8",
    },
    {
        "home_team": "Internazionale",
        "away_team": "Barcelona",
        "competition": "UEFA Champions League Semi-final",
        "season": "2009/10",
        "match_date": "2010-04-20",
        "venue": "",
        "summary": "Mourinho'nun Inter'inin Barcelona'ya karşı final yolunu açtığı büyük gece.",
        "summary_en": "Mourinho's Inter opened their path to the final with a statement win.",
        "poster_color": "#1e3a8a",
    },
    {
        "home_team": "Manchester City",
        "away_team": "Queens Park Rangers",
        "competition": "Premier League",
        "season": "2011/12",
        "match_date": "2012-05-13",
        "venue": "",
        "summary": "Uzatma dakikalarındaki geri dönüşle Premier League tarihinin en dramatik şampiyonluk anı.",
        "summary_en": "A stoppage-time comeback delivered one of the Premier League's defining title moments.",
        "poster_color": "#60a5fa",
    },
    {
        "home_team": "Borussia Dortmund",
        "away_team": "Málaga",
        "competition": "UEFA Champions League Quarter-final",
        "season": "2012/13",
        "match_date": "2013-04-09",
        "venue": "",
        "summary": "Son anlarda gelen iki golle Dortmund'un yarı finale yürüdüğü kaotik maç.",
        "summary_en": "Two late goals sent Dortmund through in a chaotic finish.",
        "poster_color": "#facc15",
    },
    {
        "home_team": "Barcelona",
        "away_team": "Manchester United",
        "competition": "UEFA Champions League Final",
        "season": "2010/11",
        "match_date": "2011-05-28",
        "venue": "",
        "summary": "Zirve dönemindeki Barcelona'nın görkemli pas oyunu performansı.",
        "summary_en": "A peak-possession Barcelona performance against a decorated United side.",
        "poster_color": "#3256a8",
    },
    {
        "home_team": "Germany",
        "away_team": "Brazil",
        "competition": "FIFA World Cup Semi-final",
        "season": "2014",
        "match_date": "2014-07-08",
        "venue": "",
        "summary": "İlk yarıdaki ani kopuşuyla tarihe kazınan Dünya Kupası yarı finali.",
        "summary_en": "A historic semi-final remembered for its sudden first-half collapse.",
        "poster_color": "#f0b429",
    },
    {
        "home_team": "Barcelona",
        "away_team": "Juventus",
        "competition": "UEFA Champions League Final",
        "season": "2014/15",
        "match_date": "2015-06-06",
        "venue": "",
        "summary": "Barcelona'nın MSN dönemiyle Avrupa'nın zirvesine çıktığı final.",
        "summary_en": "Barcelona's MSN era reached the European summit in Berlin.",
        "poster_color": "#3256a8",
    },
    {
        "home_team": "Portugal",
        "away_team": "France",
        "competition": "UEFA EURO Final",
        "season": "2016",
        "match_date": "2016-07-10",
        "venue": "",
        "summary": "Ronaldo'nun erken sakatlığına rağmen Portekiz'in uzatmalarda kupayı aldığı final.",
        "summary_en": "Portugal won in extra time despite Ronaldo's early injury.",
        "poster_color": "#16a34a",
    },
    {
        "home_team": "Barcelona",
        "away_team": "Paris Saint-Germain",
        "competition": "UEFA Champions League Round of 16",
        "season": "2016/17",
        "match_date": "2017-03-08",
        "venue": "",
        "summary": "Altı gollü geri dönüşle Avrupa gecelerinin sözlüğüne giren remontada.",
        "summary_en": "A six-goal comeback made the remontada part of European football vocabulary.",
        "poster_color": "#7c2d12",
    },
    {
        "home_team": "Real Madrid",
        "away_team": "Liverpool",
        "competition": "UEFA Champions League Final",
        "season": "2017/18",
        "match_date": "2018-05-26",
        "venue": "",
        "summary": "Bale'in röveşatası ve Real Madrid'in üst üste üçüncü Avrupa şampiyonluğu.",
        "summary_en": "Bale's overhead kick helped Real Madrid complete three European titles in a row.",
        "poster_color": "#7b8794",
    },
    {
        "home_team": "Liverpool",
        "away_team": "Barcelona",
        "competition": "UEFA Champions League Semi-final",
        "season": "2018/19",
        "match_date": "2019-05-07",
        "venue": "",
        "summary": "Anfield'da dört gollü geri dönüş ve hızlı kullanılan unutulmaz korner.",
        "summary_en": "A four-goal Anfield comeback, sealed by an unforgettable quick corner.",
        "poster_color": "#c9343f",
    },
    {
        "home_team": "Paris Saint-Germain",
        "away_team": "Bayern Munich",
        "competition": "UEFA Champions League Final",
        "season": "2019/20",
        "match_date": "2020-08-23",
        "venue": "",
        "summary": "Pandemi sezonunun Lizbon finalinde Bayern'in mükemmel seriyi tamamladığı gece.",
        "summary_en": "Bayern completed a perfect European campaign in Lisbon's pandemic-season final.",
        "poster_color": "#d71920",
    },
    {
        "home_team": "Argentina",
        "away_team": "Brazil",
        "competition": "Copa América Final",
        "season": "2021",
        "match_date": "2021-07-10",
        "venue": "",
        "summary": "Arjantin'in Maracanã'da kupayı aldığı ve Messi'nin milli takım hasretini bitirdiği final.",
        "summary_en": "Argentina won at the Maracanã as Messi ended his senior international trophy wait.",
        "poster_color": "#22a3dd",
    },
    {
        "home_team": "Real Madrid",
        "away_team": "Atlético Madrid",
        "competition": "UEFA Champions League Final",
        "season": "2013/14",
        "match_date": "2014-05-24",
        "venue": "",
        "summary": "Uzatma dakikası golüyle yön değiştiren, ekstra zamanda açılan Madrid derbisi.",
        "summary_en": "A derby final changed by a stoppage-time equalizer and extra-time surge.",
        "poster_color": "#7b8794",
    },
    {
        "home_team": "Netherlands",
        "away_team": "Spain",
        "competition": "FIFA World Cup Group Stage",
        "season": "2014",
        "match_date": "2014-06-13",
        "venue": "",
        "summary": "Turnuvayı hız, intikam ve büyük bir skorla açan unutulmaz grup maçı.",
        "summary_en": "A statement win that opened the tournament with pace and revenge energy.",
        "poster_color": "#f97316",
    },
    {
        "home_team": "Manchester City",
        "away_team": "Inter",
        "competition": "UEFA Champions League Final",
        "season": "2022/23",
        "match_date": "2023-06-10",
        "venue": "",
        "summary": "Manchester City'nin üçlemeyi tamamladığı İstanbul finali.",
        "summary_en": "Manchester City completed the treble in Istanbul.",
        "poster_color": "#60a5fa",
    },
    {
        "home_team": "Real Madrid",
        "away_team": "Borussia Dortmund",
        "competition": "UEFA Champions League Final",
        "season": "2023/24",
        "match_date": "2024-06-01",
        "venue": "",
        "summary": "Real Madrid'in geç açılan final performansıyla Avrupa tacını büyüttüğü gece.",
        "summary_en": "Real Madrid grew into the final late and extended their European crown.",
        "poster_color": "#7b8794",
    },
    {
        "home_team": "Paris Saint-Germain",
        "away_team": "Inter",
        "competition": "UEFA Champions League Final",
        "season": "2024/25",
        "match_date": "2025-05-31",
        "venue": "",
        "summary": "Paris Saint-Germain'in Avrupa tarihine en baskın final performanslarından biriyle geçtiği gece.",
        "summary_en": "Paris Saint-Germain entered European history with one of the most dominant final performances.",
        "poster_color": "#082f49",
    },
]


def h(value):
    return html.escape(str(value or ""), quote=True)


def t(lang, key):
    lang = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG
    return TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, TRANSLATIONS["en"].get(key, key))


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_columns(db, table_name):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_column(db, table_name, column_name, ddl):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def ensure_search_index(db):
    try:
        existing_columns = [row["name"] for row in db.execute("PRAGMA table_info(match_search)").fetchall()]
        if existing_columns and existing_columns != SEARCH_INDEX_COLUMNS:
            db.execute("DROP TABLE match_search")
        db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS match_search USING fts5(
                match_id UNINDEXED,
                home_team,
                away_team,
                title,
                competition,
                league_name,
                country,
                season,
                match_date,
                league_aliases,
                round_name,
                stage,
                summary,
                summary_en,
                tokenize='unicode61 remove_diacritics 2'
            )
            """
        )
    except sqlite3.OperationalError:
        return False
    return True


def rebuild_match_search(db):
    if not ensure_search_index(db):
        return False
    db.execute("DELETE FROM match_search")
    rows = db.execute(
        """
        SELECT
            matches.id,
            matches.home_team,
            matches.away_team,
            matches.home_team || ' ' || matches.away_team,
            matches.competition,
            COALESCE(leagues.name, matches.competition),
            COALESCE(leagues.country, ''),
            COALESCE(leagues.code, ''),
            matches.season,
            matches.match_date,
            COALESCE(matches.round_name, ''),
            COALESCE(matches.stage, ''),
            COALESCE(matches.summary, ''),
            COALESCE(matches.summary_en, '')
        FROM matches
        LEFT JOIN leagues ON leagues.id = matches.league_id
        """
    ).fetchall()
    for row in rows:
        league_aliases = league_alias_text(row[7], row[5], row[4], row[6])
        db.execute(
            """
            INSERT INTO match_search (
                match_id, home_team, away_team, title, competition, league_name,
                country, season, match_date, league_aliases, round_name, stage, summary, summary_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                row[8],
                row[9],
                league_aliases,
                row[10],
                row[11],
                row[12],
                row[13],
            ),
        )
    return True


def upsert_match_search_entry(db, match_id):
    if not ensure_search_index(db):
        return False
    db.execute("DELETE FROM match_search WHERE match_id = ?", (match_id,))
    row = db.execute(
        """
        SELECT
            matches.id,
            matches.home_team,
            matches.away_team,
            matches.home_team || ' ' || matches.away_team,
            matches.competition,
            COALESCE(leagues.name, matches.competition),
            COALESCE(leagues.country, ''),
            COALESCE(leagues.code, ''),
            matches.season,
            matches.match_date,
            COALESCE(matches.round_name, ''),
            COALESCE(matches.stage, ''),
            COALESCE(matches.summary, ''),
            COALESCE(matches.summary_en, '')
        FROM matches
        LEFT JOIN leagues ON leagues.id = matches.league_id
        WHERE matches.id = ?
        """,
        (match_id,),
    ).fetchone()
    if not row:
        return False
    league_aliases = league_alias_text(row[7], row[5], row[4], row[6])
    db.execute(
        """
        INSERT INTO match_search (
            match_id, home_team, away_team, title, competition, league_name,
            country, season, match_date, league_aliases, round_name, stage, summary, summary_en
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[8],
            row[9],
            league_aliases,
            row[10],
            row[11],
            row[12],
            row[13],
        ),
    )
    return True


def clear_imported_match_summaries(db):
    db.execute(
        """
        UPDATE matches
        SET summary = ''
        WHERE summary LIKE '%fikstüründen içe aktarıldı%'
        """
    )
    db.execute(
        """
        UPDATE matches
        SET summary_en = ''
        WHERE summary_en LIKE 'imported from the % fixture list%'
        """
    )
    seed_summaries = [match["summary"] for match in SEED_MATCHES if match.get("summary")]
    if seed_summaries:
        placeholders = ", ".join("?" for _ in seed_summaries)
        db.execute(
            f"""
            UPDATE matches
            SET summary = ''
            WHERE (import_source IS NOT NULL OR external_id IS NOT NULL)
              AND summary IN ({placeholders})
            """,
            seed_summaries,
        )


def clear_match_venues(db):
    db.execute("UPDATE matches SET venue = '' WHERE COALESCE(venue, '') <> ''")
    db.execute("UPDATE match_submissions SET venue = '' WHERE COALESCE(venue, '') <> ''")


def init_db(seed=True):
    with connect_db() as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                email_verified INTEGER NOT NULL DEFAULT 1,
                email_verification_token TEXT,
                email_verified_at TEXT,
                password_reset_token TEXT,
                password_reset_expires_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                country TEXT NOT NULL,
                season TEXT NOT NULL,
                tier INTEGER NOT NULL DEFAULT 1,
                kind TEXT NOT NULL DEFAULT 'competition',
                confederation TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                data_status TEXT NOT NULL DEFAULT 'seeded',
                color TEXT NOT NULL DEFAULT '#1f7a4d',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS competition_seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                season TEXT NOT NULL,
                start_year INTEGER NOT NULL,
                end_year INTEGER,
                edition_year INTEGER,
                source_url TEXT NOT NULL DEFAULT '',
                data_status TEXT NOT NULL DEFAULT 'source-indexed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (league_id, season),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (league_id, name),
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_id INTEGER,
                competition_season_id INTEGER,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                competition TEXT NOT NULL,
                season TEXT NOT NULL,
                match_date TEXT NOT NULL,
                venue TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL,
                summary_en TEXT,
                source_url TEXT,
                home_score INTEGER,
                away_score INTEGER,
                round_name TEXT,
                stage TEXT,
                status TEXT NOT NULL DEFAULT 'finished',
                import_source TEXT,
                external_id TEXT,
                imported_at TEXT,
                poster_color TEXT NOT NULL DEFAULT '#37a06f',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (league_id) REFERENCES leagues(id),
                FOREIGN KEY (competition_season_id) REFERENCES competition_seasons(id)
            );

            CREATE TABLE IF NOT EXISTS data_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                league_id INTEGER,
                season TEXT NOT NULL,
                status TEXT NOT NULL,
                imported_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
                body TEXT NOT NULL,
                watched_on TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, match_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (match_id) REFERENCES matches(id)
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, match_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (match_id) REFERENCES matches(id)
            );

            CREATE TABLE IF NOT EXISTS match_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_by INTEGER NOT NULL,
                requested_league_id INTEGER,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                competition TEXT NOT NULL,
                season TEXT NOT NULL,
                match_date TEXT NOT NULL,
                venue TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                log_after_approval INTEGER NOT NULL DEFAULT 0,
                submit_rating INTEGER,
                submit_review_body TEXT NOT NULL DEFAULT '',
                submit_watched_on TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by INTEGER,
                reviewed_at TEXT,
                created_match_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (submitted_by) REFERENCES users(id),
                FOREIGN KEY (requested_league_id) REFERENCES leagues(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id),
                FOREIGN KEY (created_match_id) REFERENCES matches(id)
            );
            """
        )

        ensure_column(db, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "users", "email_verified", "email_verified INTEGER NOT NULL DEFAULT 1")
        ensure_column(db, "users", "email_verification_token", "email_verification_token TEXT")
        ensure_column(db, "users", "email_verified_at", "email_verified_at TEXT")
        ensure_column(db, "users", "password_reset_token", "password_reset_token TEXT")
        ensure_column(db, "users", "password_reset_expires_at", "password_reset_expires_at TEXT")
        ensure_column(db, "leagues", "kind", "kind TEXT NOT NULL DEFAULT 'competition'")
        ensure_column(db, "leagues", "confederation", "confederation TEXT NOT NULL DEFAULT ''")
        ensure_column(db, "leagues", "source_url", "source_url TEXT NOT NULL DEFAULT ''")
        ensure_column(db, "leagues", "data_status", "data_status TEXT NOT NULL DEFAULT 'seeded'")
        ensure_column(db, "matches", "league_id", "league_id INTEGER")
        ensure_column(db, "matches", "competition_season_id", "competition_season_id INTEGER")
        ensure_column(db, "matches", "summary_en", "summary_en TEXT")
        ensure_column(db, "matches", "source_url", "source_url TEXT")
        ensure_column(db, "matches", "home_score", "home_score INTEGER")
        ensure_column(db, "matches", "away_score", "away_score INTEGER")
        ensure_column(db, "matches", "round_name", "round_name TEXT")
        ensure_column(db, "matches", "stage", "stage TEXT")
        ensure_column(db, "matches", "status", "status TEXT NOT NULL DEFAULT 'finished'")
        ensure_column(db, "matches", "import_source", "import_source TEXT")
        ensure_column(db, "matches", "external_id", "external_id TEXT")
        ensure_column(db, "matches", "imported_at", "imported_at TEXT")
        ensure_column(db, "match_submissions", "log_after_approval", "log_after_approval INTEGER NOT NULL DEFAULT 0")
        ensure_column(db, "match_submissions", "submit_rating", "submit_rating INTEGER")
        ensure_column(db, "match_submissions", "submit_review_body", "submit_review_body TEXT NOT NULL DEFAULT ''")
        ensure_column(db, "match_submissions", "submit_watched_on", "submit_watched_on TEXT")

        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_matches_external_id ON matches(external_id)")
        db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_matches_league_season_date
            ON matches(league_id, season, match_date)
            """
        )

        if seed:
            seed_reference_data(db)
            seed_matches(db)
            refresh_seed_match_copy(db)
            ensure_first_admin(db)
        clear_imported_match_summaries(db)
        clear_match_venues(db)
        rebuild_match_search(db)


def seed_reference_data(db):
    for league in SEED_LEAGUES:
        db.execute(
            """
            INSERT INTO leagues (
                code, name, country, season, tier, kind,
                confederation, source_url, data_status, color
            )
            VALUES (
                :code, :name, :country, :season, :tier, :kind,
                :confederation, :source_url, 'source-indexed', :color
            )
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                country = excluded.country,
                season = excluded.season,
                tier = excluded.tier,
                kind = excluded.kind,
                confederation = excluded.confederation,
                source_url = excluded.source_url,
                data_status = excluded.data_status,
                color = excluded.color
            """,
            league,
        )

    league_ids = {row["code"]: row["id"] for row in db.execute("SELECT id, code FROM leagues").fetchall()}
    seed_competition_seasons(db, league_ids)
    for league_code, teams in SEED_TEAMS.items():
        league_id = league_ids.get(league_code)
        if not league_id:
            continue
        for team in teams:
            db.execute(
                "INSERT OR IGNORE INTO teams (league_id, name) VALUES (?, ?)",
                (league_id, team),
            )


def season_label(start_year):
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def competition_seasons_for(competition):
    mode = competition.get("season_mode", "split")
    source_url = competition.get("source_url", "")
    if mode == "editions":
        for year in competition.get("editions", []):
            yield {
                "season": str(year),
                "start_year": year,
                "end_year": year,
                "edition_year": year,
                "source_url": source_url,
            }
    elif mode == "annual":
        for year in range(competition.get("start_year", 2000), SEASON_END_YEAR + 1):
            yield {
                "season": str(year),
                "start_year": year,
                "end_year": year,
                "edition_year": year,
                "source_url": source_url,
            }
    else:
        for year in range(competition.get("start_year", 2000), SEASON_END_YEAR):
            yield {
                "season": season_label(year),
                "start_year": year,
                "end_year": year + 1,
                "edition_year": None,
                "source_url": source_url,
            }


def seed_competition_seasons(db, league_ids):
    for competition in SEED_LEAGUES:
        league_id = league_ids.get(competition["code"])
        if not league_id:
            continue
        for season in competition_seasons_for(competition):
            db.execute(
                """
                INSERT INTO competition_seasons (
                    league_id, season, start_year, end_year, edition_year,
                    source_url, data_status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'source-indexed')
                ON CONFLICT(league_id, season) DO UPDATE SET
                    start_year = excluded.start_year,
                    end_year = excluded.end_year,
                    edition_year = excluded.edition_year,
                    source_url = excluded.source_url,
                    data_status = excluded.data_status
                """,
                (
                    league_id,
                    season["season"],
                    season["start_year"],
                    season["end_year"],
                    season["edition_year"],
                    season["source_url"],
                ),
            )


def seed_matches(db):
    for match in SEED_MATCHES:
        exists = db.execute(
            """
            SELECT 1 FROM matches
            WHERE home_team = ?
              AND away_team = ?
              AND match_date = ?
            """,
            (match["home_team"], match["away_team"], match["match_date"]),
        ).fetchone()
        if exists:
            continue
        db.execute(
            """
            INSERT INTO matches (
                home_team, away_team, competition, season, match_date, venue,
                summary, summary_en, poster_color
            )
            VALUES (
                :home_team, :away_team, :competition, :season, :match_date, :venue,
                :summary, :summary_en, :poster_color
            )
            """,
            match,
        )



def refresh_seed_match_copy(db):
    for match in SEED_MATCHES:
        db.execute(
            """
            UPDATE matches
            SET summary = ?,
                summary_en = COALESCE(summary_en, ?),
                poster_color = ?
            WHERE home_team = ?
              AND away_team = ?
              AND match_date = ?
              AND import_source IS NULL
              AND external_id IS NULL
            """,
            (
                match["summary"],
                match["summary_en"],
                match["poster_color"],
                match["home_team"],
                match["away_team"],
                match["match_date"],
            ),
        )


def ensure_first_admin(db):
    admin_count = db.execute("SELECT COUNT(*) AS count FROM users WHERE is_admin = 1").fetchone()["count"]
    if admin_count:
        return
    first_user = db.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if first_user:
        db.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (first_user["id"],))


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored_hash):
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    test_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return secrets.compare_digest(test_digest.hex(), digest)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def create_email_verification_token(db, user_id):
    token = secrets.token_urlsafe(32)
    db.execute(
        """
        UPDATE users
        SET email_verified = 0,
            email_verification_token = ?,
            email_verified_at = NULL
        WHERE id = ?
        """,
        (token, user_id),
    )
    return token


def verify_email_token(token):
    token = (token or "").strip()
    if not token:
        return False
    with connect_db() as db:
        user = db.execute(
            "SELECT id FROM users WHERE email_verification_token = ?",
            (token,),
        ).fetchone()
        if not user:
            return False
        db.execute(
            """
            UPDATE users
            SET email_verified = 1,
                email_verification_token = NULL,
                email_verified_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user["id"],),
        )
    return True


def create_password_reset_token(email):
    email = (email or "").strip()
    if not email:
        return ""
    with connect_db() as db:
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            return ""
        token = secrets.token_urlsafe(32)
        expires_at = (utc_now() + dt.timedelta(hours=1)).isoformat()
        db.execute(
            """
            UPDATE users
            SET password_reset_token = ?,
                password_reset_expires_at = ?
            WHERE id = ?
            """,
            (token, expires_at, user["id"]),
        )
    return token


def password_reset_token_is_valid(expires_at):
    if not expires_at:
        return False
    try:
        expires = dt.datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=dt.timezone.utc)
    return expires >= utc_now()


def reset_password_with_token(token, password):
    token = (token or "").strip()
    if not token or len(password) < 6:
        return False
    with connect_db() as db:
        user = db.execute(
            "SELECT id, password_reset_expires_at FROM users WHERE password_reset_token = ?",
            (token,),
        ).fetchone()
        if not user or not password_reset_token_is_valid(user["password_reset_expires_at"]):
            return False
        db.execute(
            """
            UPDATE users
            SET password_hash = ?,
                password_reset_token = NULL,
                password_reset_expires_at = NULL,
                email_verified = 1,
                email_verified_at = COALESCE(email_verified_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (hash_password(password), user["id"]),
        )
    return True


def session_cookie(session_id, remember=False):
    max_age = "; Max-Age=2592000" if remember else ""
    return f"session_id={session_id}; HttpOnly; Path=/; SameSite=Lax{max_age}"


def rating_text(rating, lang=DEFAULT_LANG):
    if rating is None:
        return t(lang, "no_ratings")
    return f"{rating / 2:.1f}/5"


def plural_count(count, singular_key, plural_key, lang):
    key = singular_key if count == 1 else plural_key
    return f"{count} {t(lang, key)}"


def initials(home_team, away_team):
    def take(team):
        cleaned = team.split("(", 1)[0].strip()
        parts = [part.strip(".,") for part in cleaned.replace("-", " ").split(" ") if part.strip(".,")]
        if len(parts) == 1:
            return parts[0][:3].upper()
        return "".join(part[0] for part in parts[:3]).upper()

    return take(home_team), take(away_team)


def language_from_cookie(cookie_header):
    cookie = SimpleCookie()
    if cookie_header:
        cookie.load(cookie_header)
    lang = cookie.get("lang")
    if lang and lang.value in SUPPORTED_LANGS:
        return lang.value
    return DEFAULT_LANG


def safe_next(value):
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


def fetch_user_by_session(cookie_header):
    cookie = SimpleCookie()
    if cookie_header:
        cookie.load(cookie_header)
    session_id = cookie.get("session_id")
    if not session_id:
        return None
    user_id = SESSIONS.get(session_id.value)
    if not user_id:
        return None
    with connect_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def nav_link(path, label, active):
    class_name = "active" if active == path else ""
    return f'<a class="{class_name}" href="{path}">{h(label)}</a>'


def language_switch(lang, next_path):
    encoded_next = quote(safe_next(next_path), safe="")
    tr_class = "active" if lang == "tr" else ""
    en_class = "active" if lang == "en" else ""
    return f"""
    <div class="language-switch" aria-label="{h(t(lang, 'language'))}">
        <a class="{tr_class}" href="/language?lang=tr&next={encoded_next}">tr</a>
        <a class="{en_class}" href="/language?lang=en&next={encoded_next}">en</a>
    </div>
    """


def search_suggestions(lang=DEFAULT_LANG, action="/"):
    terms = (
        ["Galatasaray", "Fenerbahçe", "derbi", "UEFA Champions League", "FIFA World Cup", "2025/26"]
        if lang == "tr"
        else ["Galatasaray", "Fenerbahçe", "derby", "UEFA Champions League", "FIFA World Cup", "2025/26"]
    )
    links = "".join(
        f'<a href="{h(action)}?q={quote(term)}#{MATCH_RESULTS_ANCHOR}">{h(term)}</a>'
        for term in terms
    )
    return f'<div class="search-suggestions" aria-label="{h(t(lang, "search_suggestions"))}">{links}</div>'


def clean_match_filters(filters=None):
    filters = filters or {}
    cleaned = {}
    for key in MATCH_FILTER_KEYS:
        cleaned[key] = str(filters.get(key, "") or "").strip()[:120]
    return cleaned


def filters_from_query(query):
    return clean_match_filters({key: one(query, key) for key in MATCH_FILTER_KEYS})


def filters_active(filters=None):
    return any(clean_match_filters(filters).values())


def organization_filter_options(lang=DEFAULT_LANG, selected_id=""):
    with connect_db() as db:
        leagues = db.execute("SELECT id, name, country, season FROM leagues ORDER BY kind, country, name").fetchall()
    options = [f'<option value="">{h(t(lang, "select_league"))}</option>']
    for league in leagues:
        selected = "selected" if str(league["id"]) == str(selected_id) else ""
        label = f"{league['name']} ({league['country']}, {league['season']})"
        options.append(f'<option value="{league["id"]}" {selected}>{h(label)}</option>')
    return "".join(options)


def match_filter_panel(lang=DEFAULT_LANG, filters=None, action="/"):
    filters = clean_match_filters(filters)
    open_attr = " open" if filters_active(filters) else ""
    clear_label = t(lang, "clear_filters")
    return f"""
    <details class="filter-box"{open_attr}>
        <summary>{h(t(lang, "filter"))}</summary>
        <div class="filter-grid">
            <label>{h(t(lang, "team"))}
                <input name="team" value="{h(filters['team'])}" placeholder="{h(t(lang, 'team_placeholder'))}">
            </label>
            <label>{h(t(lang, "opponent"))}
                <input name="opponent" value="{h(filters['opponent'])}" placeholder="{h(t(lang, 'opponent_placeholder'))}">
            </label>
            <label>{h(t(lang, "year"))}
                <input name="year" value="{h(filters['year'])}" placeholder="{h(t(lang, 'year_placeholder'))}">
            </label>
            <label>{h(t(lang, "organizations"))}
                <select name="organization">{organization_filter_options(lang, filters['organization'])}</select>
            </label>
        </div>
        <div class="filter-actions">
            <button type="submit">{h(t(lang, "filter"))}</button>
            <a href="{h(action)}">{h(clear_label)}</a>
        </div>
    </details>
    """


def hidden_filter_inputs(filters=None):
    filters = clean_match_filters(filters)
    return "".join(
        f'<input type="hidden" name="{h(key)}" value="{h(value)}">'
        for key, value in filters.items()
        if value
    )


def bounded_result_limit(value, default):
    try:
        selected = int(value)
    except (TypeError, ValueError):
        selected = default
    selected = max(1, selected)
    return min(selected, MAX_MATCH_RESULT_LIMIT)


def split_visible_matches(matches, limit):
    return matches[:limit], len(matches) > limit and limit < MAX_MATCH_RESULT_LIMIT


def show_more_control(path, lang=DEFAULT_LANG, query="", filters=None, next_limit=0, show=False, anchor=""):
    if not show:
        return ""
    query_input = f'<input type="hidden" name="q" value="{h(query)}">' if query else ""
    filter_inputs = hidden_filter_inputs(filters)
    action = f"{path}#{quote(anchor, safe='-_')}" if anchor else path
    return f"""
    <form class="more-results" method="get" action="{h(action)}">
        {query_input}
        {filter_inputs}
        <input type="hidden" name="limit" value="{min(int(next_limit), MAX_MATCH_RESULT_LIMIT)}">
        <button type="submit">{h(t(lang, "show_more"))}</button>
    </form>
    """


def empty_matches_html(lang=DEFAULT_LANG):
    if lang == "tr":
        return '<p class="empty-state">maç bulunamadı. başka bir arama dene ya da <a href="/log">öneri gönder</a>.</p>'
    return '<p class="empty-state">no matches found. try a different search or <a href="/log">submit one</a>.</p>'


def layout(title, content, user=None, active="/", notice=None, lang=DEFAULT_LANG):
    logged_in_links = ""
    if user:
        admin_link = nav_link("/moderation", t(lang, "moderation"), active) if user["is_admin"] else ""
        logged_in_links = (
            f'{nav_link("/diary", t(lang, "diary"), active)}'
            f'{nav_link("/watchlist", t(lang, "watchlist"), active)}'
            f"{admin_link}"
            f'{nav_link("/profile", user["username"], active)}'
            '<form class="nav-form" method="post" action="/logout">'
            f'<button class="ghost-button" type="submit">{h(t(lang, "log_out"))}</button>'
            "</form>"
        )
    else:
        logged_in_links = (
            f'{nav_link("/login", t(lang, "log_in"), active)}'
            f'<a class="primary-nav" href="/signup">{h(t(lang, "join"))}</a>'
        )

    notice_html = f'<div class="notice">{h(notice)}</div>' if notice else ""
    return f"""<!doctype html>
<html lang="{h(lang)}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{h(title)} | {APP_NAME}</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <header class="site-header">
        <a class="brand" href="/" aria-label="{APP_NAME} home">
            <span class="brand-mark"></span>
            <span>{APP_NAME}</span>
        </a>
        <nav class="main-nav" aria-label="Primary navigation">
            {nav_link("/", t(lang, "discover"), active)}
            {nav_link("/log", t(lang, "log"), active)}
            {logged_in_links}
            {language_switch(lang, active)}
        </nav>
    </header>
    <main>
        {notice_html}
        {content}
    </main>
</body>
</html>"""


def match_title(match, lang=DEFAULT_LANG):
    separator = " - " if lang == "tr" else " vs "
    return f"{match['home_team']}{separator}{match['away_team']}"


def match_anchor(match):
    return f"match-{match['id']}"


def match_value(match, key, default=None):
    try:
        if hasattr(match, "keys") and key not in match.keys():
            return default
        value = match[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def match_scoreline(match):
    home_score = match_value(match, "home_score")
    away_score = match_value(match, "away_score")
    if home_score is None or away_score is None:
        return ""
    return f"{home_score}-{away_score}"


def match_summary(match, lang=DEFAULT_LANG):
    if lang == "en" and "summary_en" in match.keys() and match["summary_en"]:
        return match["summary_en"]
    return match["summary"]


def competition_label(match):
    if "league_name" in match.keys() and match["league_name"]:
        return match["league_name"]
    return match["competition"]


def match_poster(match, lang=DEFAULT_LANG):
    home, away = initials(match["home_team"], match["away_team"])
    scoreline = match_scoreline(match)
    center = h(scoreline) if scoreline else "v"
    return f"""
    <a class="match-poster" href="/match/{match['id']}" style="--accent: {h(match['poster_color'])}">
        <span class="poster-competition">{h(competition_label(match))}</span>
        <span class="poster-scoreline">
            <strong>{h(home)}</strong>
            <span>{center}</span>
            <strong>{h(away)}</strong>
        </span>
        <span class="poster-date">{h(match['match_date'])}</span>
    </a>
    """


def match_card(match, lang=DEFAULT_LANG):
    average = rating_text(match["average_rating"], lang)
    review_count = match["review_count"]
    summary = match_summary(match, lang)
    summary_html = f"<p>{h(summary)}</p>" if summary else ""
    return f"""
    <article class="match-card" id="{h(match_anchor(match))}">
        {match_poster(match, lang)}
        <div class="match-card-body">
            <p class="eyebrow">{h(competition_label(match))} / {h(match['season'])}</p>
            <h2><a href="/match/{match['id']}">{h(match_title(match, lang))}</a></h2>
            <p class="meta">{h(match['match_date'])}</p>
            {summary_html}
            <div class="metric-row">
                <span>{average}</span>
                <span>{h(plural_count(review_count, "reviews", "reviews", lang))}</span>
            </div>
        </div>
    </article>
    """


def review_item(review, lang=DEFAULT_LANG):
    return f"""
    <article class="review-item">
        <div>
            <p class="eyebrow">{h(review['username'])} {h(t(lang, 'watched_on_sentence'))} {h(review['watched_on'])}</p>
            <h3><a href="/match/{review['match_id']}">{h(match_title(review, lang))}</a></h3>
        </div>
        <span class="rating-pill">{rating_text(review['rating'], lang)}</span>
        <p>{h(review['body'])}</p>
    </article>
    """


def match_rows_query(where="", order_by="matches.match_date DESC", limit=None):
    limit_sql = f"LIMIT {int(limit)}" if limit else ""
    return f"""
        SELECT
            matches.*,
            leagues.name AS league_name,
            leagues.country AS league_country,
            ROUND(AVG(reviews.rating), 1) AS average_rating,
            COUNT(reviews.id) AS review_count
        FROM matches
        LEFT JOIN leagues ON leagues.id = matches.league_id
        LEFT JOIN reviews ON reviews.match_id = matches.id
        {where}
        GROUP BY matches.id
        ORDER BY {order_by}
        {limit_sql}
    """


def alias_key(value):
    text = str(value or "").casefold().replace("ı", "i")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", text).strip()


def unique_terms(terms):
    deduped = []
    seen = set()
    for term in terms:
        term = str(term or "").strip()
        key = alias_key(term)
        if key and key not in seen:
            deduped.append(term)
            seen.add(key)
    return deduped


def competition_aliases_for(competition):
    competition_key = alias_key(competition)
    aliases = []
    for key, values in COMPETITION_NAME_ALIASES.items():
        if key and (key in competition_key or competition_key in key):
            aliases.extend(values)
    return aliases


def league_alias_terms(code="", league_name="", competition="", country=""):
    terms = [league_name, competition]
    terms.extend(LEAGUE_NAME_ALIASES.get(code or "", []))
    terms.extend(competition_aliases_for(league_name))
    terms.extend(competition_aliases_for(competition))
    if code == "tr-super-lig":
        terms.extend([country, "Türkiye", "Turkey"])
    return unique_terms(terms)


def league_alias_text(code="", league_name="", competition="", country=""):
    return " ".join(league_alias_terms(code, league_name, competition, country))


def organization_alias_matches(query_key, candidate_key):
    if not query_key or not candidate_key:
        return False
    if query_key == candidate_key:
        return True
    query_word_count = len(query_key.split())
    candidate_word_count = len(candidate_key.split())
    if query_word_count >= 2 and query_key in candidate_key:
        return True
    if candidate_word_count >= 2 and candidate_key in query_key:
        return True
    return False


def league_codes_for_organization(value):
    keys = {alias_key(variant) for variant in alias_variants(value)}
    codes = []
    for league in SEED_LEAGUES:
        candidate_keys = {
            alias_key(term)
            for term in league_alias_terms(
                league.get("code", ""),
                league.get("name", ""),
                league.get("name", ""),
                league.get("country", ""),
            )
        }
        if any(organization_alias_matches(query_key, candidate_key) for query_key in keys for candidate_key in candidate_keys):
            codes.append(league["code"])
    return codes


def raw_search_tokens(value):
    return re.findall(r"[\w]+", str(value or "").casefold())


def normalized_search_tokens(value):
    return [alias_key(token) for token in raw_search_tokens(value)]


def alias_for_token(token):
    return SEARCH_ALIASES.get(token) or SEARCH_ALIASES.get(alias_key(token))


def phrase_alias_at(tokens, index):
    max_length = min(4, len(tokens) - index)
    for length in range(max_length, 0, -1):
        key = tuple(tokens[index:index + length])
        if key in SEARCH_PHRASE_ALIASES:
            return SEARCH_PHRASE_ALIASES[key], length
    return None, 0


def alias_phrase(value):
    raw_tokens = raw_search_tokens(value)
    normalized_tokens = normalized_search_tokens(value)
    words = []
    changed = False
    index = 0
    while index < len(normalized_tokens):
        phrase_alias, length = phrase_alias_at(normalized_tokens, index)
        if phrase_alias:
            words.extend(phrase_alias)
            changed = True
            index += length
            continue
        raw_token = raw_tokens[index]
        alias = alias_for_token(raw_token)
        if alias:
            words.extend(alias)
            changed = True
        else:
            words.append(raw_token)
        index += 1
    return " ".join(words) if changed else ""


def alias_variants(value):
    value = str(value or "").strip()
    variants = []
    if value:
        variants.append(value)
    translated = alias_phrase(value)
    if translated:
        variants.append(translated)
    deduped = []
    seen = set()
    for variant in variants:
        key = variant.casefold()
        if key and key not in seen:
            deduped.append(variant)
            seen.add(key)
    return deduped


def search_tokens(query):
    raw_tokens = raw_search_tokens(query)
    normalized_tokens = normalized_search_tokens(query)
    tokens = []
    index = 0
    while index < len(raw_tokens):
        phrase_alias, length = phrase_alias_at(normalized_tokens, index)
        if phrase_alias:
            tokens.extend(re.findall(r"[\w]+", " ".join(phrase_alias).casefold()))
            index += length
            continue
        token = raw_tokens[index]
        alias = alias_for_token(token)
        if alias:
            tokens.extend(re.findall(r"[\w]+", " ".join(alias).casefold()))
        elif len(token) > 1:
            tokens.append(token)
        index += 1
    deduped = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped[:10]


def build_fts_query(query):
    tokens = search_tokens(query)
    if not tokens:
        return ""
    return " ".join(f"{token}*" for token in tokens)


def field_like_clause(column, variants):
    variants = [variant for variant in variants if variant]
    if not variants:
        return "", []
    return "(" + " OR ".join(f"{column} LIKE ?" for _ in variants) + ")", [f"%{variant}%" for variant in variants]


def team_side_clause(column, value):
    return field_like_clause(column, alias_variants(value))


def match_filter_conditions(filters=None):
    filters = clean_match_filters(filters)
    clauses = []
    params = []
    team = filters["team"]
    opponent = filters["opponent"]
    if team and opponent:
        home_team_clause, home_team_params = team_side_clause("matches.home_team", team)
        away_opponent_clause, away_opponent_params = team_side_clause("matches.away_team", opponent)
        away_team_clause, away_team_params = team_side_clause("matches.away_team", team)
        home_opponent_clause, home_opponent_params = team_side_clause("matches.home_team", opponent)
        clauses.append(
            f"""
            (
                ({home_team_clause} AND {away_opponent_clause})
                OR ({away_team_clause} AND {home_opponent_clause})
            )
            """
        )
        params.extend(home_team_params + away_opponent_params + away_team_params + home_opponent_params)
    elif team:
        home_clause, home_params = team_side_clause("matches.home_team", team)
        away_clause, away_params = team_side_clause("matches.away_team", team)
        clauses.append(f"({home_clause} OR {away_clause})")
        params.extend(home_params + away_params)
    elif opponent:
        home_clause, home_params = team_side_clause("matches.home_team", opponent)
        away_clause, away_params = team_side_clause("matches.away_team", opponent)
        clauses.append(f"({home_clause} OR {away_clause})")
        params.extend(home_params + away_params)

    year = filters["year"]
    if year:
        if re.fullmatch(r"\d{4}", year):
            clauses.append("matches.match_date LIKE ?")
            params.append(f"{year}-%")
        else:
            year_like = f"%{year}%"
            clauses.append("(matches.season LIKE ? OR matches.match_date LIKE ?)")
            params.extend([year_like, year_like])

    organization = filters["organization"]
    if organization:
        try:
            organization_id = int(organization)
        except ValueError:
            alias_codes = league_codes_for_organization(organization)
            league_clause, league_params = field_like_clause("leagues.name", alias_variants(organization))
            competition_clause, competition_params = field_like_clause("matches.competition", alias_variants(organization))
            alias_clause = ""
            alias_params = []
            if alias_codes:
                alias_clause = "leagues.code IN (" + ", ".join("?" for _ in alias_codes) + ")"
                alias_params = alias_codes
            organization_clauses = [clause for clause in [alias_clause, league_clause, competition_clause] if clause]
            clauses.append("(" + " OR ".join(organization_clauses) + ")")
            params.extend(alias_params + league_params + competition_params)
        else:
            clauses.append("matches.league_id = ?")
            params.append(organization_id)

    return clauses, params


def match_filter_sql(filters=None, prefix="AND"):
    clauses, params = match_filter_conditions(filters)
    if not clauses:
        return "", []
    return f" {prefix} " + " AND ".join(clauses), params


def fetch_search_matches(db, query, limit, filters=None):
    fts_query = build_fts_query(query)
    if not fts_query or not ensure_search_index(db):
        return None
    rank_query = alias_phrase(query) or query
    normalized = rank_query.strip().lower()
    like_query = f"%{normalized}%"
    prefix_query = f"{normalized}%"
    filter_sql, filter_params = match_filter_sql(filters)
    try:
        return db.execute(
            f"""
            SELECT
                matches.*,
                leagues.name AS league_name,
                leagues.country AS league_country,
                review_stats.average_rating AS average_rating,
                COALESCE(review_stats.review_count, 0) AS review_count
            FROM match_search
            JOIN matches ON matches.id = match_search.match_id
            LEFT JOIN leagues ON leagues.id = matches.league_id
            LEFT JOIN (
                SELECT
                    match_id,
                    ROUND(AVG(rating), 1) AS average_rating,
                    COUNT(id) AS review_count
                FROM reviews
                GROUP BY match_id
            ) AS review_stats ON review_stats.match_id = matches.id
            WHERE match_search MATCH ?
            {filter_sql}
            ORDER BY
                CASE
                    WHEN lower(matches.home_team) = ? OR lower(matches.away_team) = ? THEN 0
                    WHEN lower(matches.home_team) LIKE ? OR lower(matches.away_team) LIKE ? THEN 1
                    WHEN lower(COALESCE(leagues.name, matches.competition)) LIKE ? THEN 2
                    WHEN lower(matches.home_team || ' ' || matches.away_team) LIKE ? THEN 3
                    ELSE 4
                END,
                bm25(
                    match_search,
                    0.0, 7.0, 7.0, 5.5, 4.2, 4.2, 2.3,
                    2.0, 1.2, 3.8, 1.0, 1.0, 0.8, 0.8
                ),
                review_count DESC,
                matches.match_date DESC
            LIMIT ?
            """,
            (
                fts_query,
                *filter_params,
                normalized,
                normalized,
                prefix_query,
                prefix_query,
                like_query,
                like_query,
                int(limit),
            ),
        ).fetchall()
    except sqlite3.OperationalError:
        return None


def fetch_matches(query="", limit=None, filters=None):
    clean_query = query.strip()
    filters = clean_match_filters(filters)
    has_filters = filters_active(filters)
    effective_limit = limit or (SEARCH_RESULT_LIMIT if clean_query or has_filters else None)
    query_filter = f"%{clean_query}%"
    with connect_db() as db:
        if not clean_query and not has_filters:
            return db.execute(match_rows_query(limit=effective_limit), []).fetchall()
        if clean_query:
            fts_rows = fetch_search_matches(db, clean_query, effective_limit, filters)
            if fts_rows is not None:
                return fts_rows
        clauses = []
        params = []
        if clean_query:
            clauses.append(
                """
                (
                    matches.home_team LIKE ?
                    OR matches.away_team LIKE ?
                    OR matches.competition LIKE ?
                    OR leagues.name LIKE ?
                    OR leagues.country LIKE ?
                    OR matches.season LIKE ?
                    OR matches.match_date LIKE ?
                    OR matches.round_name LIKE ?
                    OR matches.stage LIKE ?
                    OR matches.summary LIKE ?
                    OR matches.summary_en LIKE ?
                )
                """
            )
            params.extend([query_filter] * 11)
        filter_clauses, filter_params = match_filter_conditions(filters)
        clauses.extend(filter_clauses)
        params.extend(filter_params)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        return db.execute(match_rows_query(where=where, limit=effective_limit), params).fetchall()


def classic_refresh_seed():
    return dt.date.today().toordinal() // 3


def classic_match_where_clause():
    clauses = []
    params = []
    for match in SEED_MATCHES:
        clauses.append("(matches.home_team = ? AND matches.away_team = ? AND matches.match_date = ?)")
        params.extend([match["home_team"], match["away_team"], match["match_date"]])
    where = f"""
        WHERE ({' OR '.join(clauses)})
          AND matches.import_source IS NULL
          AND matches.external_id IS NULL
          AND (
              COALESCE(matches.summary, '') <> ''
              OR COALESCE(matches.summary_en, '') <> ''
          )
    """
    return where, params


def fetch_classic_matches(limit=8):
    seed = classic_refresh_seed()
    order = f"((matches.id * 1103515245 + {seed}) % 2147483647) ASC"
    where, params = classic_match_where_clause()
    with connect_db() as db:
        return db.execute(match_rows_query(where=where, order_by=order, limit=limit), params).fetchall()


def league_options(lang=DEFAULT_LANG, selected_id=""):
    with connect_db() as db:
        leagues = db.execute("SELECT id, name, country, season FROM leagues ORDER BY country, name").fetchall()
    options = [f'<option value="">{h(t(lang, "select_league"))}</option>']
    for league in leagues:
        selected = "selected" if str(league["id"]) == str(selected_id) else ""
        label = f"{league['name']} ({league['country']}, {league['season']})"
        options.append(f'<option value="{league["id"]}" {selected}>{h(label)}</option>')
    return "".join(options)


def render_home(user, lang=DEFAULT_LANG, query="", match_limit=None, filters=None):
    filters = clean_match_filters(filters)
    has_filters = filters_active(filters)
    is_catalog_view = bool(query or has_filters)
    default_limit = MATCH_RESULT_STEP if is_catalog_view else HOME_CLASSIC_LIMIT
    current_limit = bounded_result_limit(match_limit, default_limit)
    fetch_limit = current_limit + 1
    matches = fetch_matches(query=query, limit=fetch_limit, filters=filters) if is_catalog_view else fetch_classic_matches(limit=fetch_limit)
    matches, has_more_matches = split_visible_matches(matches, current_limit)
    show_more_anchor = match_anchor(matches[-1]) if matches else ""
    with connect_db() as db:
        recent_reviews = db.execute(
            """
            SELECT reviews.*, users.username, matches.home_team, matches.away_team
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN matches ON matches.id = reviews.match_id
            ORDER BY reviews.updated_at DESC
            LIMIT 6
            """
        ).fetchall()

        totals = db.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM matches) AS matches,
                (SELECT COUNT(*) FROM reviews) AS reviews,
                (SELECT COUNT(*) FROM users) AS users,
                (SELECT COUNT(*) FROM leagues) AS competitions,
                (SELECT COUNT(*) FROM competition_seasons) AS seasons,
                (SELECT COUNT(*) FROM teams) AS teams,
                (SELECT COUNT(*) FROM match_submissions WHERE status = 'pending') AS submissions
            """
        ).fetchone()
        leagues = db.execute(
            """
            SELECT
                leagues.*,
                COUNT(DISTINCT teams.id) AS team_count,
                COUNT(DISTINCT competition_seasons.id) AS season_count
            FROM leagues
            LEFT JOIN teams ON teams.league_id = leagues.id
            LEFT JOIN competition_seasons ON competition_seasons.league_id = leagues.id
            GROUP BY leagues.id
            ORDER BY leagues.kind, leagues.id
            """
        ).fetchall()

    empty = empty_matches_html(lang)
    match_grid = "".join(match_card(match, lang) for match in matches) or empty
    more_matches = show_more_control(
        "/",
        lang,
        query=query,
        filters=filters,
        next_limit=current_limit + (MATCH_RESULT_STEP if is_catalog_view else HOME_CLASSIC_LIMIT),
        show=has_more_matches,
        anchor=show_more_anchor,
    )
    feed = "".join(review_item(review, lang) for review in recent_reviews) or f'<p class="empty-state">{h(t(lang, "empty_reviews_feed"))}</p>'
    league_cards = "".join(
        f"""
        <article class="league-pill" style="--accent: {h(league['color'])}">
            <strong>{h(league['name'])}</strong>
            <span>{h(league['country'])} / {h(league['season'])}</span>
            <small>{league['season_count']} {h(t(lang, 'seasons'))}</small>
        </article>
        """
        for league in leagues
    )

    content = f"""
    <section class="dashboard-band">
        <div class="dashboard-copy">
            <p class="eyebrow">{h(t(lang, "football_diary"))}</p>
            <h1>{h(t(lang, "home_hero"))}</h1>
            <p>{h(t(lang, "home_support"))}</p>
        </div>
        <form class="search-panel" method="get" action="/#{MATCH_RESULTS_ANCHOR}">
            <label for="q">{h(t(lang, "find_match"))}</label>
            <div class="search-row">
                <input id="q" type="search" name="q" value="{h(query)}" placeholder="{h(t(lang, 'search_placeholder'))}">
                <button type="submit">{h(t(lang, "search"))}</button>
            </div>
            {match_filter_panel(lang, filters, "/")}
            {search_suggestions(lang)}
            <div class="stat-grid">
                <span><strong>{totals['matches']}</strong> {h(t(lang, 'matches'))}</span>
                <span><strong>{totals['competitions']}</strong> {h(t(lang, 'organizations'))}</span>
                <span><strong>{totals['seasons']}</strong> {h(t(lang, 'seasons'))}</span>
            </div>
        </form>
    </section>

    <section class="content-grid">
        <div>
            <div class="section-heading">
                <h2>{h(t(lang, 'search_results') if is_catalog_view else t(lang, 'popular_matches'))}</h2>
                <a href="/log">{h(t(lang, "classic_hint") if not is_catalog_view else t(lang, "log"))}</a>
            </div>
            <div id="{MATCH_RESULTS_ANCHOR}" class="match-grid">
                {match_grid}
            </div>
            {more_matches}
        </div>
        <aside class="sidebar-stack">
            <section class="league-strip">
                <div class="section-heading">
                    <h2>{h(t(lang, "league_database"))}</h2>
                    <a href="/log">{h(t(lang, "submit_for_review"))}</a>
                </div>
                <div class="league-grid">{league_cards}</div>
            </section>
            <section class="feed-panel">
                <h2>{h(t(lang, "recent_reviews"))}</h2>
                {feed}
            </section>
        </aside>
    </section>
    """
    return layout(t(lang, "discover"), content, user, active="/", lang=lang)


def render_match_detail(user, lang, match_id, notice=None):
    with connect_db() as db:
        match = db.execute(match_rows_query(where="WHERE matches.id = ?"), (match_id,)).fetchone()
        if not match:
            return None

        reviews = db.execute(
            """
            SELECT reviews.*, users.username, matches.home_team, matches.away_team
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN matches ON matches.id = reviews.match_id
            WHERE reviews.match_id = ?
            ORDER BY reviews.updated_at DESC
            """,
            (match_id,),
        ).fetchall()

        my_review = None
        in_watchlist = False
        if user:
            my_review = db.execute(
                "SELECT * FROM reviews WHERE user_id = ? AND match_id = ?",
                (user["id"], match_id),
            ).fetchone()
            in_watchlist = bool(
                db.execute(
                    "SELECT 1 FROM watchlist WHERE user_id = ? AND match_id = ?",
                    (user["id"], match_id),
                ).fetchone()
            )

    watched_on = h(my_review["watched_on"] if my_review else dt.date.today().isoformat())
    body = h(my_review["body"] if my_review else "")
    current_rating = my_review["rating"] if my_review else 8
    options = ""
    for value in range(10, 0, -1):
        selected = "selected" if value == current_rating else ""
        options += f'<option value="{value}" {selected}>{rating_text(value, lang)}</option>'

    if user:
        watchlist_text = t(lang, "remove_from_watchlist") if in_watchlist else t(lang, "add_to_watchlist")
        review_form = f"""
        <form class="action-form" method="post" action="/watchlist/toggle">
            <input type="hidden" name="match_id" value="{match['id']}">
            <button type="submit">{h(watchlist_text)}</button>
        </form>
        <form class="review-form" method="post" action="/reviews/create">
            <input type="hidden" name="match_id" value="{match['id']}">
            <label for="rating">{h(t(lang, 'rating'))}</label>
            <select id="rating" name="rating">{options}</select>
            <label for="watched_on">{h(t(lang, 'watched_on'))}</label>
            <input id="watched_on" type="date" name="watched_on" value="{watched_on}">
            <label for="body">{h(t(lang, 'review'))}</label>
            <textarea id="body" name="body" rows="6" placeholder="{h(t(lang, 'review_placeholder'))}">{body}</textarea>
            <button type="submit">{h(t(lang, 'save_review') if my_review else t(lang, 'review'))}</button>
        </form>
        """
    else:
        review_form = f"""
        <div class="auth-prompt">
            <h2>{h(t(lang, "want_to_log"))}</h2>
            <p>{h(t(lang, "want_to_log_copy"))}</p>
            <a class="button-link" href="/signup">{h(t(lang, "join"))}</a>
        </div>
        """

    feed = "".join(review_item(review, lang) for review in reviews) or f'<p class="empty-state">{h(t(lang, "empty_reviews"))}</p>'
    content = f"""
    <section class="match-detail">
        <div class="detail-poster">
            {match_poster(match, lang)}
        </div>
        <div class="detail-copy">
            <p class="eyebrow">{h(competition_label(match))} / {h(match['season'])}</p>
            <h1>{h(match_title(match, lang))}</h1>
            <p class="meta">{h(match['match_date'])}</p>
            <p>{h(match_summary(match, lang))}</p>
            <div class="metric-row wide">
                <span>{rating_text(match['average_rating'], lang)}</span>
                <span>{h(plural_count(match['review_count'], 'reviews', 'reviews', lang))}</span>
            </div>
        </div>
        <aside class="review-panel">
            {review_form}
        </aside>
    </section>
    <section class="review-list">
        <h2>{h(t(lang, "reviews"))}</h2>
        {feed}
    </section>
    """
    return layout(match_title(match, lang), content, user, active="/", notice=notice, lang=lang)


def render_auth_page(kind, lang=DEFAULT_LANG, error=None, notice=None):
    is_signup = kind == "signup"
    title = t(lang, "create_account") if is_signup else t(lang, "log_in")
    action = "/signup" if is_signup else "/login"
    username_label = t(lang, "username") if is_signup else t(lang, "username_or_email")
    username_autocomplete = "username" if is_signup else "username email"
    extra_field = """
        <label for="email">__EMAIL_LABEL__</label>
        <input id="email" name="email" type="email" autocomplete="email" required>
    """.replace("__EMAIL_LABEL__", h(t(lang, "email"))) if is_signup else ""
    login_controls = ""
    if not is_signup:
        login_controls = f"""
            <label class="check-row auth-check">
                <input type="checkbox" name="remember" value="1">
                <span>{h(t(lang, "remember_me"))}</span>
            </label>
            <div class="auth-actions">
                <button type="submit">{h(title)}</button>
                <a class="auth-link-button" href="/forgot-password">{h(t(lang, "forgot_password"))}</a>
            </div>
        """
    else:
        login_controls = f'<button type="submit">{h(title)}</button>'
    switch = (
        f'{h(t(lang, "already_have_account"))} <a href="/login">{h(t(lang, "log_in"))}</a>.'
        if is_signup
        else f'{h(t(lang, "new_here"))} <a href="/signup">{h(t(lang, "create_account"))}</a>.'
    )
    error_html = f'<p class="form-error">{h(error)}</p>' if error else ""
    notice_html = f'<p class="form-notice">{h(notice)}</p>' if notice else ""
    content = f"""
    <section class="auth-layout">
        <div>
            <p class="eyebrow">{APP_NAME}</p>
            <h1>{h(title)}</h1>
            <p>{h(t(lang, "auth_copy"))}</p>
        </div>
        <form class="auth-form" method="post" action="{action}">
            {error_html}
            {notice_html}
            <label for="username">{h(username_label)}</label>
            <input id="username" name="username" type="text" autocomplete="{h(username_autocomplete)}" required>
            {extra_field}
            <label for="password">{h(t(lang, "password"))}</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required>
            {login_controls}
            <p>{switch}</p>
        </form>
    </section>
    """
    return layout(title, content, active=action, lang=lang)


def render_auth_link_page(title, copy, link, link_label, lang=DEFAULT_LANG):
    link_html = (
        f'<a class="button-link auth-dev-link" href="{h(link)}">{h(link_label)}</a>'
        if link
        else ""
    )
    content = f"""
    <section class="auth-layout">
        <div>
            <p class="eyebrow">{APP_NAME}</p>
            <h1>{h(title)}</h1>
            <p>{h(copy)}</p>
        </div>
        <div class="auth-form">
            <p class="form-notice">{h(t(lang, "auth_dev_hint"))}</p>
            {link_html}
            <a class="auth-link-button" href="/login">{h(t(lang, "log_in"))}</a>
        </div>
    </section>
    """
    return layout(title, content, active="/login", lang=lang)


def render_forgot_password_page(lang=DEFAULT_LANG, error=None, notice=None, reset_link=""):
    error_html = f'<p class="form-error">{h(error)}</p>' if error else ""
    notice_html = f'<p class="form-notice">{h(notice)}</p>' if notice else ""
    reset_link_html = (
        f'<a class="button-link auth-dev-link" href="{h(reset_link)}">{h(t(lang, "reset_password"))}</a>'
        if reset_link
        else ""
    )
    content = f"""
    <section class="auth-layout">
        <div>
            <p class="eyebrow">{APP_NAME}</p>
            <h1>{h(t(lang, "forgot_password"))}</h1>
            <p>{h(t(lang, "forgot_password_copy"))}</p>
        </div>
        <form class="auth-form" method="post" action="/forgot-password">
            {error_html}
            {notice_html}
            {reset_link_html}
            <label for="email">{h(t(lang, "email"))}</label>
            <input id="email" name="email" type="email" autocomplete="email" required>
            <button type="submit">{h(t(lang, "send_reset_link"))}</button>
            <a class="auth-link-button" href="/login">{h(t(lang, "log_in"))}</a>
        </form>
    </section>
    """
    return layout(t(lang, "forgot_password"), content, active="/login", lang=lang)


def render_reset_password_page(token, lang=DEFAULT_LANG, error=None):
    error_html = f'<p class="form-error">{h(error)}</p>' if error else ""
    content = f"""
    <section class="auth-layout">
        <div>
            <p class="eyebrow">{APP_NAME}</p>
            <h1>{h(t(lang, "reset_password"))}</h1>
            <p>{h(t(lang, "reset_password_copy"))}</p>
        </div>
        <form class="auth-form" method="post" action="/reset-password">
            {error_html}
            <input type="hidden" name="token" value="{h(token)}">
            <label for="password">{h(t(lang, "new_password"))}</label>
            <input id="password" name="password" type="password" autocomplete="new-password" required>
            <button type="submit">{h(t(lang, "reset_password"))}</button>
            <a class="auth-link-button" href="/login">{h(t(lang, "log_in"))}</a>
        </form>
    </section>
    """
    return layout(t(lang, "reset_password"), content, active="/login", lang=lang)


def render_log(user, lang=DEFAULT_LANG, query="", match_limit=None, filters=None, error=None, notice=None):
    if not user:
        return render_auth_page("login", lang, t(lang, "log_in_required_log"))
    filters = clean_match_filters(filters)
    has_filters = filters_active(filters)
    default_limit = MATCH_RESULT_STEP if query or has_filters else LOG_CATALOG_LIMIT
    current_limit = bounded_result_limit(match_limit, default_limit)
    matches = fetch_matches(query=query, limit=current_limit + 1, filters=filters)
    matches, has_more_matches = split_visible_matches(matches, current_limit)
    show_more_anchor = match_anchor(matches[-1]) if matches else ""
    error_html = f'<p class="form-error">{h(error)}</p>' if error else ""
    match_grid = "".join(match_card(match, lang) for match in matches) or empty_matches_html(lang)
    more_matches = show_more_control(
        "/log",
        lang,
        query=query,
        filters=filters,
        next_limit=current_limit + (MATCH_RESULT_STEP if query or has_filters else LOG_CATALOG_LIMIT),
        show=has_more_matches,
        anchor=show_more_anchor,
    )
    rating_options = "".join(
        f'<option value="{value}" {"selected" if value == 8 else ""}>{rating_text(value, lang)}</option>'
        for value in range(10, 0, -1)
    )
    content = f"""
    <section class="form-layout log-layout">
        <div>
            <p class="eyebrow">{h(t(lang, "grow_catalog"))}</p>
            <h1>{h(t(lang, "log"))}</h1>
            <p>{h(t(lang, "log_copy"))}</p>
            <form class="search-panel compact-search" method="get" action="/log#{MATCH_RESULTS_ANCHOR}">
                <label for="q">{h(t(lang, "find_match"))}</label>
                <div class="search-row">
                    <input id="q" type="search" name="q" value="{h(query)}" placeholder="{h(t(lang, 'search_placeholder'))}">
                    <button type="submit">{h(t(lang, "search"))}</button>
                </div>
                {match_filter_panel(lang, filters, "/log")}
                {search_suggestions(lang, "/log")}
            </form>
        </div>
        <form class="wide-form" method="post" action="/submissions/create">
            {error_html}
            <label>{h(t(lang, "select_league"))}
                <select name="requested_league_id">{league_options(lang)}</select>
            </label>
            <div class="two-col">
                <label>{h(t(lang, "home_team"))}<input name="home_team" required></label>
                <label>{h(t(lang, "away_team"))}<input name="away_team" required></label>
            </div>
            <div class="two-col">
                <label>{h(t(lang, "competition"))}<input name="competition" required></label>
                <label>{h(t(lang, "season"))}<input name="season" placeholder="2025/26" required></label>
            </div>
            <label>{h(t(lang, "match_date"))}<input name="match_date" type="date" required></label>
            <label>{h(t(lang, "evidence_url"))}
                <input name="source_url" type="url" placeholder="{h(t(lang, 'evidence_placeholder'))}" required>
            </label>
            <label>{h(t(lang, "note"))}
                <textarea name="note" rows="4" placeholder="{h(t(lang, 'note_placeholder'))}"></textarea>
            </label>
            <section class="inline-panel">
                <label class="check-row">
                    <input type="checkbox" name="log_after_approval" value="1">
                    <span>{h(t(lang, "log_after_approval"))}</span>
                </label>
                <p>{h(t(lang, "submission_log_hint"))}</p>
                <div class="two-col">
                    <label>{h(t(lang, "rating"))}
                        <select name="submit_rating">{rating_options}</select>
                    </label>
                    <label>{h(t(lang, "watched_on"))}
                        <input type="date" name="submit_watched_on" value="{dt.date.today().isoformat()}">
                    </label>
                </div>
                <label>{h(t(lang, "review"))}
                    <textarea name="submit_review_body" rows="4" placeholder="{h(t(lang, 'review_placeholder'))}"></textarea>
                </label>
            </section>
            <button type="submit">{h(t(lang, "submit_for_review"))}</button>
        </form>
    </section>
    <section class="review-list">
        <div class="section-heading">
            <h2>{h(t(lang, "catalog_matches"))}</h2>
        </div>
        <div id="{MATCH_RESULTS_ANCHOR}" class="match-grid">{match_grid}</div>
        {more_matches}
    </section>
    """
    return layout(t(lang, "log"), content, user, active="/log", notice=notice, lang=lang)


def render_diary(user, lang=DEFAULT_LANG):
    if not user:
        return render_auth_page("login", lang, t(lang, "log_in_required_diary"))
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT reviews.*, users.username, matches.home_team, matches.away_team
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN matches ON matches.id = reviews.match_id
            WHERE reviews.user_id = ?
            ORDER BY watched_on DESC, reviews.updated_at DESC
            """,
            (user["id"],),
        ).fetchall()
    feed = "".join(review_item(row, lang) for row in rows) or f'<p class="empty-state">{h(t(lang, "empty_diary"))}</p>'
    content = f"""
    <section class="page-heading">
        <p class="eyebrow">{h(t(lang, "your_logbook"))}</p>
        <h1>{h(t(lang, "diary"))}</h1>
    </section>
    <section class="review-list">
        {feed}
    </section>
    """
    return layout(t(lang, "diary"), content, user, active="/diary", lang=lang)


def render_watchlist(user, lang=DEFAULT_LANG):
    if not user:
        return render_auth_page("login", lang, t(lang, "log_in_required_watchlist"))
    with connect_db() as db:
        rows = db.execute(
            match_rows_query(
                where="""
                WHERE matches.id IN (
                    SELECT match_id FROM watchlist WHERE user_id = ?
                )
                """,
                order_by="matches.match_date DESC",
            ),
            (user["id"],),
        ).fetchall()
    grid = "".join(match_card(row, lang) for row in rows) or f'<p class="empty-state">{h(t(lang, "empty_watchlist"))}</p>'
    content = f"""
    <section class="page-heading">
        <p class="eyebrow">{h(t(lang, "watchlist"))}</p>
        <h1>{h(t(lang, "watchlist"))}</h1>
    </section>
    <section class="match-grid">
        {grid}
    </section>
    """
    return layout(t(lang, "watchlist"), content, user, active="/watchlist", lang=lang)


def render_profile(user, lang=DEFAULT_LANG, username=None):
    if not user and not username:
        return render_auth_page("login", lang, t(lang, "log_in"))
    username = username or user["username"]
    with connect_db() as db:
        profile = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not profile:
            return None
        stats = db.execute(
            """
            SELECT
                COUNT(*) AS reviews,
                ROUND(AVG(rating), 1) AS average_rating,
                COUNT(DISTINCT match_id) AS matches
            FROM reviews
            WHERE user_id = ?
            """,
            (profile["id"],),
        ).fetchone()
        rows = db.execute(
            """
            SELECT reviews.*, users.username, matches.home_team, matches.away_team
            FROM reviews
            JOIN users ON users.id = reviews.user_id
            JOIN matches ON matches.id = reviews.match_id
            WHERE reviews.user_id = ?
            ORDER BY reviews.updated_at DESC
            LIMIT 5
            """,
            (profile["id"],),
        ).fetchall()
    feed = "".join(review_item(row, lang) for row in rows) or f'<p class="empty-state">{h(t(lang, "empty_reviews"))}</p>'
    content = f"""
    <section class="profile-header">
        <div class="avatar">{h(profile['username'][:2].upper())}</div>
        <div>
            <p class="eyebrow">{h(t(lang, "profile"))}</p>
            <h1>{h(profile['username'])}</h1>
            <p>{h(t(lang, "joined"))} {h(profile['created_at'][:10])}</p>
        </div>
        <div class="stat-grid profile-stats">
            <span><strong>{stats['matches']}</strong> {h(t(lang, 'matches'))}</span>
            <span><strong>{stats['reviews']}</strong> {h(t(lang, 'reviews'))}</span>
            <span><strong>{rating_text(stats['average_rating'], lang)}</strong> {h(t(lang, 'avg'))}</span>
        </div>
    </section>
    <section class="review-list">
        <h2>{h(t(lang, "recent_reviews"))}</h2>
        {feed}
    </section>
    """
    return layout(profile["username"], content, user, active="/profile", lang=lang)


def render_moderation(user, lang=DEFAULT_LANG, notice=None):
    if not user:
        return render_auth_page("login", lang, t(lang, "log_in"))
    if not user["is_admin"]:
        content = f"""
        <section class="page-heading">
            <p class="eyebrow">{h(t(lang, "moderation"))}</p>
            <h1>{h(t(lang, "admin_only"))}</h1>
            <a class="button-link" href="/">{h(t(lang, "back_home"))}</a>
        </section>
        """
        return layout(t(lang, "moderation"), content, user, active="/moderation", lang=lang)

    with connect_db() as db:
        submissions = db.execute(
            """
            SELECT match_submissions.*, users.username, leagues.name AS league_name
            FROM match_submissions
            JOIN users ON users.id = match_submissions.submitted_by
            LEFT JOIN leagues ON leagues.id = match_submissions.requested_league_id
            WHERE match_submissions.status = 'pending'
            ORDER BY match_submissions.created_at DESC
            """
        ).fetchall()

    rows = []
    for item in submissions:
        league_line = item["league_name"] or item["competition"]
        log_line = ""
        if item["log_after_approval"]:
            log_line = f'<p class="submitted-log">{h(t(lang, "optional_log"))}: {rating_text(item["submit_rating"], lang)} / {h(item["submit_watched_on"])}</p>'
        rows.append(
            f"""
            <article class="submission-card">
                <div>
                    <p class="eyebrow">{h(item['username'])} / {h(item['created_at'][:10])} / {h(t(lang, 'pending'))}</p>
                    <h2>{h(item['home_team'])} - {h(item['away_team'])}</h2>
                    <p class="meta">{h(league_line)} / {h(item['season'])} / {h(item['match_date'])}</p>
                    <p>{h(item['note'])}</p>
                    {log_line}
                    <a href="{h(item['source_url'])}" target="_blank" rel="noreferrer">{h(t(lang, "source"))}</a>
                </div>
                <div class="moderation-actions">
                    <form method="post" action="/submissions/approve">
                        <input type="hidden" name="submission_id" value="{item['id']}">
                        <button type="submit">{h(t(lang, "approve"))}</button>
                    </form>
                    <form method="post" action="/submissions/reject">
                        <input type="hidden" name="submission_id" value="{item['id']}">
                        <button class="danger-button" type="submit">{h(t(lang, "reject"))}</button>
                    </form>
                </div>
            </article>
            """
        )

    pending = "".join(rows) or f'<p class="empty-state">{h(t(lang, "empty_matches"))}</p>'
    content = f"""
    <section class="page-heading">
        <div>
            <p class="eyebrow">{h(t(lang, "moderation"))}</p>
            <h1>{h(t(lang, "pending_submissions"))}</h1>
            <p>{h(t(lang, "admin_review_hint"))}</p>
        </div>
    </section>
    <section class="moderation-list">
        {pending}
    </section>
    """
    return layout(t(lang, "moderation"), content, user, active="/moderation", notice=notice, lang=lang)


def one(form, key, default=""):
    values = form.get(key, [default])
    return values[0].strip()


def is_valid_date(value):
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def is_valid_source_url(value):
    return value.startswith("https://") or value.startswith("http://")


def parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class BoxToBoxdHandler(BaseHTTPRequestHandler):
    server_version = "box-to-boxd/1.0"

    def do_GET(self):
        self.handle_get(send_body=True)

    def do_HEAD(self):
        self.handle_get(send_body=False)

    def handle_get(self, send_body=True):
        lang = language_from_cookie(self.headers.get("Cookie"))
        user = fetch_user_by_session(self.headers.get("Cookie"))
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/language":
            selected = one(query, "lang", DEFAULT_LANG)
            if selected not in SUPPORTED_LANGS:
                selected = DEFAULT_LANG
            return self.redirect(
                safe_next(unquote(one(query, "next", "/"))),
                {"Set-Cookie": f"lang={selected}; Path=/; SameSite=Lax"},
            )
        if path.startswith("/static/"):
            return self.serve_static(path, lang=lang, send_body=send_body)
        if path == "/":
            notice = t(lang, "submission_received") if one(query, "submitted") else None
            return self.send_html(
                render_home(user, lang, one(query, "q"), one(query, "limit"), filters_from_query(query)),
                send_body=send_body,
            )
        if path == "/signup":
            return self.send_html(render_auth_page("signup", lang), send_body=send_body)
        if path == "/login":
            return self.send_html(render_auth_page("login", lang), send_body=send_body)
        if path == "/verify-email":
            token = one(query, "token")
            if verify_email_token(token):
                return self.send_html(
                    render_auth_page("login", lang, notice=t(lang, "email_verification_success")),
                    send_body=send_body,
                )
            return self.send_html(render_auth_page("login", lang, error=t(lang, "token_invalid")), send_body=send_body)
        if path == "/forgot-password":
            return self.send_html(render_forgot_password_page(lang), send_body=send_body)
        if path == "/reset-password":
            token = one(query, "token")
            with connect_db() as db:
                user = db.execute(
                    "SELECT password_reset_expires_at FROM users WHERE password_reset_token = ?",
                    (token,),
                ).fetchone()
            if not user or not password_reset_token_is_valid(user["password_reset_expires_at"]):
                return self.send_html(render_auth_page("login", lang, error=t(lang, "token_invalid")), send_body=send_body)
            return self.send_html(render_reset_password_page(token, lang), send_body=send_body)
        if path in {"/log", "/add-match"}:
            if path == "/add-match":
                return self.redirect("/log")
            notice = t(lang, "submission_received") if one(query, "submitted") else None
            return self.send_html(
                render_log(user, lang, one(query, "q"), one(query, "limit"), filters_from_query(query), notice=notice),
                send_body=send_body,
            )
        if path == "/diary":
            return self.send_html(render_diary(user, lang), send_body=send_body)
        if path == "/watchlist":
            return self.send_html(render_watchlist(user, lang), send_body=send_body)
        if path == "/profile":
            return self.send_html(render_profile(user, lang), send_body=send_body)
        if path == "/moderation":
            notice = t(lang, "submission_received") if one(query, "approved") else None
            return self.send_html(render_moderation(user, lang, notice=notice), send_body=send_body)
        if path.startswith("/profile/"):
            username = unquote(path.removeprefix("/profile/"))
            page = render_profile(user, lang, username)
            return self.send_html(page, send_body=send_body) if page else self.not_found(lang, send_body=send_body)
        if path.startswith("/match/"):
            match_id = parse_int(path.removeprefix("/match/"))
            if match_id is None:
                return self.not_found(lang, send_body=send_body)
            page = render_match_detail(user, lang, match_id)
            return self.send_html(page, send_body=send_body) if page else self.not_found(lang, send_body=send_body)
        return self.not_found(lang, send_body=send_body)

    def do_POST(self):
        lang = language_from_cookie(self.headers.get("Cookie"))
        user = fetch_user_by_session(self.headers.get("Cookie"))
        parsed = urlparse(self.path)
        form = self.read_form()

        if parsed.path == "/signup":
            return self.handle_signup(form, lang)
        if parsed.path == "/login":
            return self.handle_login(form, lang)
        if parsed.path == "/forgot-password":
            return self.handle_forgot_password(form, lang)
        if parsed.path == "/reset-password":
            return self.handle_reset_password(form, lang)
        if parsed.path == "/logout":
            return self.handle_logout()
        if parsed.path == "/reviews/create":
            return self.handle_review(form, user, lang)
        if parsed.path == "/watchlist/toggle":
            return self.handle_watchlist(form, user)
        if parsed.path == "/submissions/create":
            return self.handle_submission(form, user, lang)
        if parsed.path == "/submissions/approve":
            return self.handle_approve_submission(form, user, lang)
        if parsed.path == "/submissions/reject":
            return self.handle_reject_submission(form, user, lang)
        return self.not_found(lang)

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return parse_qs(body)

    def send_html(self, html_body, status=HTTPStatus.OK, headers=None, send_body=True):
        encoded = html_body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if send_body:
            self.wfile.write(encoded)

    def redirect(self, location, headers=None):
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()

    def not_found(self, lang=DEFAULT_LANG, send_body=True):
        content = f"""
        <section class="page-heading">
            <p class="eyebrow">404</p>
            <h1>{h(t(lang, "not_found_title"))}</h1>
            <p>{h(t(lang, "not_found_copy"))}</p>
            <a class="button-link" href="/">{h(t(lang, "back_home"))}</a>
        </section>
        """
        self.send_html(layout("404", content, lang=lang), status=HTTPStatus.NOT_FOUND, send_body=send_body)

    def serve_static(self, path, lang=DEFAULT_LANG, send_body=True):
        filename = path.removeprefix("/static/")
        if "/" in filename or "\\" in filename:
            return self.not_found(lang, send_body=send_body)
        file_path = STATIC_DIR / filename
        if not file_path.exists():
            return self.not_found(lang, send_body=send_body)
        content_type = "text/css" if file_path.suffix == ".css" else "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def handle_signup(self, form, lang):
        username = one(form, "username")
        email = one(form, "email")
        password = one(form, "password")
        if len(username) < 3 or len(password) < 6 or "@" not in email:
            message = "kullanıcı adı en az 3, şifre en az 6 karakter olmalı." if lang == "tr" else "use a username with 3+ characters and a password with 6+ characters."
            return self.send_html(render_auth_page("signup", lang, message))
        try:
            with connect_db() as db:
                is_admin = 1 if db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"] == 0 else 0
                cursor = db.execute(
                    """
                    INSERT INTO users (
                        username, email, password_hash, is_admin,
                        email_verified, email_verification_token
                    )
                    VALUES (?, ?, ?, ?, 0, NULL)
                    """,
                    (username, email, hash_password(password), is_admin),
                )
                user_id = cursor.lastrowid
                verification_token = create_email_verification_token(db, user_id)
        except sqlite3.IntegrityError:
            message = "bu kullanıcı adı alınmış." if lang == "tr" else "that username is already taken."
            return self.send_html(render_auth_page("signup", lang, message))
        verification_link = f"/verify-email?token={quote(verification_token)}"
        return self.send_html(
            render_auth_link_page(
                t(lang, "email_verification_title"),
                t(lang, "email_verification_sent"),
                verification_link,
                t(lang, "email_verification_link"),
                lang,
            )
        )

    def handle_login(self, form, lang):
        identifier = one(form, "username")
        password = one(form, "password")
        remember = one(form, "remember") == "1"
        with connect_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identifier, identifier),
            ).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            message = "kullanıcı adı veya şifre hatalı." if lang == "tr" else "username or password is incorrect."
            return self.send_html(render_auth_page("login", lang, message))
        if not user["email_verified"]:
            return self.send_html(render_auth_page("login", lang, t(lang, "email_verification_required")))
        session_id = secrets.token_urlsafe(32)
        SESSIONS[session_id] = user["id"]
        self.redirect("/", {"Set-Cookie": session_cookie(session_id, remember)})

    def handle_forgot_password(self, form, lang):
        email = one(form, "email")
        token = create_password_reset_token(email)
        if not token:
            return self.send_html(render_forgot_password_page(lang, error=t(lang, "password_reset_unavailable")))
        reset_link = f"/reset-password?token={quote(token)}"
        return self.send_html(
            render_forgot_password_page(
                lang,
                notice=t(lang, "password_reset_ready"),
                reset_link=reset_link,
            )
        )

    def handle_reset_password(self, form, lang):
        token = one(form, "token")
        password = one(form, "password")
        if len(password) < 6:
            message = "şifre en az 6 karakter olmalı." if lang == "tr" else "use a password with 6+ characters."
            return self.send_html(render_reset_password_page(token, lang, error=message))
        if not reset_password_with_token(token, password):
            return self.send_html(render_auth_page("login", lang, error=t(lang, "token_invalid")))
        return self.send_html(render_auth_page("login", lang, notice=t(lang, "password_reset_success")))

    def handle_logout(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        session_id = cookie.get("session_id")
        if session_id:
            SESSIONS.pop(session_id.value, None)
        self.redirect("/", {"Set-Cookie": "session_id=; Max-Age=0; Path=/; SameSite=Lax"})

    def handle_review(self, form, user, lang):
        if not user:
            return self.redirect("/login")
        match_id = parse_int(one(form, "match_id"))
        rating = parse_int(one(form, "rating"))
        if match_id is None or rating is None:
            return self.redirect("/")
        body = one(form, "body")
        watched_on = one(form, "watched_on", dt.date.today().isoformat())
        if rating < 1 or rating > 10 or not body or not is_valid_date(watched_on):
            page = render_match_detail(user, lang, match_id, t(lang, "match_review_error"))
            return self.send_html(page)
        with connect_db() as db:
            db.execute(
                """
                INSERT INTO reviews (user_id, match_id, rating, body, watched_on)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, match_id) DO UPDATE SET
                    rating = excluded.rating,
                    body = excluded.body,
                    watched_on = excluded.watched_on,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user["id"], match_id, rating, body, watched_on),
            )
        self.redirect(f"/match/{match_id}")

    def handle_watchlist(self, form, user):
        if not user:
            return self.redirect("/login")
        match_id = parse_int(one(form, "match_id"))
        if match_id is None:
            return self.redirect("/")
        with connect_db() as db:
            exists = db.execute(
                "SELECT 1 FROM watchlist WHERE user_id = ? AND match_id = ?",
                (user["id"], match_id),
            ).fetchone()
            if exists:
                db.execute("DELETE FROM watchlist WHERE user_id = ? AND match_id = ?", (user["id"], match_id))
            else:
                db.execute("INSERT INTO watchlist (user_id, match_id) VALUES (?, ?)", (user["id"], match_id))
        self.redirect(f"/match/{match_id}")

    def handle_submission(self, form, user, lang):
        if not user:
            return self.redirect("/login")
        fields = {
            "requested_league_id": parse_int(one(form, "requested_league_id")),
            "home_team": one(form, "home_team"),
            "away_team": one(form, "away_team"),
            "competition": one(form, "competition"),
            "season": one(form, "season"),
            "match_date": one(form, "match_date"),
            "venue": "",
            "source_url": one(form, "source_url"),
            "note": one(form, "note"),
            "log_after_approval": 1 if one(form, "log_after_approval") == "1" else 0,
            "submit_rating": parse_int(one(form, "submit_rating")),
            "submit_watched_on": one(form, "submit_watched_on"),
            "submit_review_body": one(form, "submit_review_body"),
        }
        required = ["home_team", "away_team", "competition", "season", "match_date", "source_url"]
        if any(not fields[key] for key in required) or not is_valid_date(fields["match_date"]) or not is_valid_source_url(fields["source_url"]):
            return self.send_html(render_log(user, lang, error=t(lang, "field_error")))
        if fields["log_after_approval"]:
            valid_rating = fields["submit_rating"] is not None and 1 <= fields["submit_rating"] <= 10
            if not valid_rating or not fields["submit_review_body"] or not is_valid_date(fields["submit_watched_on"]):
                return self.send_html(render_log(user, lang, error=t(lang, "match_review_error")))
        with connect_db() as db:
            db.execute(
                """
                INSERT INTO match_submissions (
                    submitted_by, requested_league_id, home_team, away_team, competition,
                    season, match_date, venue, source_url, note, log_after_approval,
                    submit_rating, submit_watched_on, submit_review_body
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user["id"],
                    fields["requested_league_id"],
                    fields["home_team"],
                    fields["away_team"],
                    fields["competition"],
                    fields["season"],
                    fields["match_date"],
                    fields["venue"],
                    fields["source_url"],
                    fields["note"],
                    fields["log_after_approval"],
                    fields["submit_rating"] if fields["log_after_approval"] else None,
                    fields["submit_watched_on"] if fields["log_after_approval"] else None,
                    fields["submit_review_body"] if fields["log_after_approval"] else "",
                ),
            )
        self.redirect("/log?submitted=1")

    def handle_approve_submission(self, form, user, lang):
        if not user or not user["is_admin"]:
            return self.send_html(render_moderation(user, lang), status=HTTPStatus.FORBIDDEN)
        submission_id = parse_int(one(form, "submission_id"))
        if submission_id is None:
            return self.redirect("/moderation")
        with connect_db() as db:
            item = db.execute(
                "SELECT * FROM match_submissions WHERE id = ? AND status = 'pending'",
                (submission_id,),
            ).fetchone()
            if not item:
                return self.redirect("/moderation")
            color_row = db.execute("SELECT color FROM leagues WHERE id = ?", (item["requested_league_id"],)).fetchone()
            poster_color = color_row["color"] if color_row else "#37a06f"
            summary = f"yönetici tarafından doğrulanan kullanıcı önerisi. kaynak: {item['source_url']}"
            summary_en = f"user submission verified by an admin. source: {item['source_url']}"
            cursor = db.execute(
                """
                INSERT INTO matches (
                    league_id, home_team, away_team, competition, season,
                    match_date, venue, summary, summary_en, source_url, poster_color
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["requested_league_id"],
                    item["home_team"],
                    item["away_team"],
                    item["competition"],
                    item["season"],
                    item["match_date"],
                    item["venue"],
                    summary,
                    summary_en,
                    item["source_url"],
                    poster_color,
                ),
            )
            match_id = cursor.lastrowid
            upsert_match_search_entry(db, match_id)
            if item["log_after_approval"] and item["submit_rating"] and item["submit_review_body"] and item["submit_watched_on"]:
                db.execute(
                    """
                    INSERT INTO reviews (user_id, match_id, rating, body, watched_on)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, match_id) DO UPDATE SET
                        rating = excluded.rating,
                        body = excluded.body,
                        watched_on = excluded.watched_on,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        item["submitted_by"],
                        match_id,
                        item["submit_rating"],
                        item["submit_review_body"],
                        item["submit_watched_on"],
                    ),
                )
            db.execute(
                """
                UPDATE match_submissions
                SET status = 'approved',
                    reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP,
                    created_match_id = ?
                WHERE id = ?
                """,
                (user["id"], match_id, submission_id),
            )
        self.redirect("/moderation?approved=1")

    def handle_reject_submission(self, form, user, lang):
        if not user or not user["is_admin"]:
            return self.send_html(render_moderation(user, lang), status=HTTPStatus.FORBIDDEN)
        submission_id = parse_int(one(form, "submission_id"))
        if submission_id is None:
            return self.redirect("/moderation")
        with connect_db() as db:
            db.execute(
                """
                UPDATE match_submissions
                SET status = 'rejected',
                    reviewed_by = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'pending'
                """,
                (user["id"], submission_id),
            )
        self.redirect("/moderation")

    def log_message(self, format, *args):
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), BoxToBoxdHandler)
    print(f"{APP_NAME} running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
