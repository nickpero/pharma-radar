"""
Pharma Radar — FDA Matcher

Collega una FDA News Item alle aziende e ai programmi
presenti nella watchlist Pharma Radar.

Il matcher utilizza:
- ticker
- nome società
- alias società
- nome programma/farmaco
- alias programma/farmaco
- contenuto esteso della FDA News Item

IMPORTANTE:
Il ticker viene verificato separatamente e in modo
case-sensitive per evitare falsi positivi causati da
parole comuni inglesi.

Esempio:
ticker = RARE
testo = "a rare blood disorder"

NON deve essere considerato un match.

Per la pipeline FDA destinata agli alert, un semplice
match aziendale NON è sufficiente.

Deve essere identificato anche uno specifico
programma/farmaco.

Il matcher non produce raccomandazioni di acquisto
o vendita.
"""

import json
import re
from pathlib import Path


# ============================================
# FILES
# ============================================

WATCHLIST_FILE = Path(
    "data/watchlist.json"
)

ALIASES_FILE = Path(
    "data/aliases.json"
)


# ============================================
# EXTENDED NEWS FIELDS
# ============================================

NEWS_TEXT_FIELDS = (
    "title",
    "summary",
    "description",
    "content",
    "body",
    "text",
    "article_text",
    "full_text",
    "drug",
    "drug_name",
    "program",
    "program_name",
    "company",
    "company_name",
    "sponsor",
    "manufacturer",
    "applicant",
    "raw_text",
)


# ============================================
# NORMALIZATION
# ============================================

def normalize(text):
    """
    Normalizza un testo per il matching generale.
    """

    if text is None:
        return ""

    text = str(text).lower()

    replacements = {
        ",": " ",
        ".": " ",
        "-": " ",
        "_": " ",
        "/": " ",
        "(": " ",
        ")": " ",
        ":": " ",
        ";": " ",
        "[": " ",
        "]": " ",
        "{": " ",
        "}": " ",
        "'": " ",
        '"': " ",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    return " ".join(
        text.split()
    )


# ============================================
# LOAD JSON
# ============================================

def load_json(path):
    """
    Carica un file JSON.

    Restituisce {} se il file non esiste.
    """

    if not path.exists():
        return {}

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ============================================
# LOAD WATCHLIST
# ============================================

def load_watchlist():
    """
    Carica la watchlist Pharma Radar.
    """

    return load_json(
        WATCHLIST_FILE
    )


# ============================================
# LOAD ALIASES
# ============================================

def load_aliases():
    """
    Carica gli alias delle aziende
    e dei programmi.
    """

    return load_json(
        ALIASES_FILE
    )


# ============================================
# TEXT EXTRACTION
# ============================================

def _stringify_news_value(value):
    """
    Converte in testo un valore proveniente
    da una News Item.

    Supporta:
    - stringhe
    - numeri
    - liste
    - tuple
    - set
    - dizionari
    """

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return " ".join(
            _stringify_news_value(item)
            for item in value
        )

    if isinstance(value, dict):
        return " ".join(
            _stringify_news_value(item)
            for item in value.values()
        )

    return str(value)


def get_news_text_parts(news_item):
    """
    Estrae tutti i campi testuali utili della news.

    I campi vengono deduplicati mantenendo l'ordine
    originale.
    """

    if not isinstance(
        news_item,
        dict,
    ):
        raise TypeError(
            "news_item must be a dictionary"
        )

    parts = []
    seen = set()

    for field in NEWS_TEXT_FIELDS:
        value = news_item.get(field)

        text = _stringify_news_value(
            value
        ).strip()

        if not text:
            continue

        normalized = text.strip()

        if normalized in seen:
            continue

        seen.add(normalized)
        parts.append(text)

    return parts


# ============================================
# TEXT CONSTRUCTION
# ============================================

def build_news_text(news_item):
    """
    Costruisce il testo complessivo utilizzato
    per il matching della news FDA.
    """

    parts = get_news_text_parts(
        news_item
    )

    return normalize(
        " ".join(parts)
    )


def build_raw_news_text(news_item):
    """
    Costruisce il testo originale della news.

    Viene utilizzato per il matching del ticker,
    che deve essere case-sensitive.
    """

    parts = get_news_text_parts(
        news_item
    )

    return " ".join(parts)


# ============================================
# ALIAS EXTRACTION
# ============================================

def get_company_aliases(
    ticker,
    company,
):
    """
    Restituisce gli alias della società.

    Il ticker NON viene incluso negli alias
    generici: viene gestito separatamente con
    matching case-sensitive.
    """

    aliases_data = load_aliases()

    company_config = aliases_data.get(
        ticker,
        {},
    )

    aliases = []

    company_name = company.get(
        "company",
        "",
    )

    if company_name:
        aliases.append(
            company_name
        )

    configured_aliases = (
        company_config.get(
            "company_aliases",
            [],
        )
    )

    if isinstance(
        configured_aliases,
        list,
    ):
        aliases.extend(
            configured_aliases
        )

    return [
        alias
        for alias in aliases
        if normalize(alias)
    ]


def get_program_aliases(
    ticker,
    program,
):
    """
    Restituisce tutti gli alias disponibili
    per un programma/farmaco.
    """

    aliases_data = load_aliases()

    company_config = aliases_data.get(
        ticker,
        {},
    )

    program_aliases = (
        company_config.get(
            "program_aliases",
            {},
        )
    )

    aliases = [
        program
    ]

    configured_aliases = (
        program_aliases.get(
            program,
            [],
        )
    )

    if isinstance(
        configured_aliases,
        list,
    ):
        aliases.extend(
            configured_aliases
        )

    return [
        alias
        for alias in aliases
        if normalize(alias)
    ]


# ============================================
# TOKEN MATCH
# ============================================

def contains_alias(
    text,
    alias,
):
    """
    Verifica la presenza di un alias nel testo.

    Il matching generale è case-insensitive.
    """

    normalized_text = normalize(
        text
    )

    normalized_alias = normalize(
        alias
    )

    if not normalized_text:
        return False

    if not normalized_alias:
        return False

    text_tokens = set(
        normalized_text.split()
    )

    alias_tokens = (
        normalized_alias.split()
    )

    if len(alias_tokens) == 1:
        return alias_tokens[0] in text_tokens

    return (
        normalized_alias
        in normalized_text
    )


# ============================================
# TICKER MATCH
# ============================================

def contains_ticker(
    news_item,
    ticker,
):
    """
    Verifica la presenza del ticker nel testo
    originale della news.

    Il matching è case-sensitive.

    Esempio:

        ticker = RARE

        "rare blood disorder"
            -> NO MATCH

        "RARE announces FDA approval"
            -> MATCH
    """

    if not ticker:
        return False

    ticker = str(
        ticker
    ).strip()

    if not ticker:
        return False

    raw_text = build_raw_news_text(
        news_item
    )

    if not raw_text:
        return False

    pattern = (
        r"(?<![A-Za-z0-9])"
        + re.escape(ticker)
        + r"(?![A-Za-z0-9])"
    )

    return bool(
        re.search(
            pattern,
            raw_text,
        )
    )


# ============================================
# MATCH COMPANY
# ============================================

def match_company(
    news_item,
    ticker,
    company,
):
    """
    Determina se la news contiene riferimenti
    riconducibili alla società.

    Il match può avvenire tramite:
    - nome società;
    - alias società;
    - ticker esatto case-sensitive.
    """

    news_text = build_news_text(
        news_item
    )

    aliases = get_company_aliases(
        ticker,
        company,
    )

    matches = []

    # ----------------------------------------
    # COMPANY NAME / ALIASES
    # ----------------------------------------

    for alias in aliases:

        if contains_alias(
            news_text,
            alias,
        ):
            if alias not in matches:
                matches.append(
                    alias
                )

    # ----------------------------------------
    # TICKER
    # ----------------------------------------

    if contains_ticker(
        news_item,
        ticker,
    ):
        if ticker not in matches:
            matches.append(
                ticker
            )

    return matches


# ============================================
# MATCH PROGRAM
# ============================================

def match_program(
    news_item,
    ticker,
    program,
):
    """
    Determina se la news contiene riferimenti
    al programma/farmaco.

    Il matching utilizza:
    - nome programma;
    - alias programma;
    - eventuali riferimenti presenti nel
      contenuto esteso della news.
    """

    news_text = build_news_text(
        news_item
    )

    aliases = get_program_aliases(
        ticker,
        program,
    )

    matches = []

    for alias in aliases:

        if contains_alias(
            news_text,
            alias,
        ):
            if alias not in matches:
                matches.append(
                    alias
                )

    return matches


# ============================================
# MATCH WATCHLIST
# ============================================

def match_fda_news(
    news_item,
    watchlist=None,
):
    """
    Cerca tutte le corrispondenze della news FDA
    nella watchlist.

    Una corrispondenza può essere ottenuta tramite:
    - società;
    - ticker;
    - programma/farmaco;
    - società + programma;
    - ticker + programma.

    Questa funzione mantiene anche i match
    COMPANY per compatibilità con il motore
    di matching.

    La decisione finale utilizzata dalla pipeline
    FDA viene presa da identify_fda_target(),
    che richiede un programma specifico.
    """

    if not isinstance(
        news_item,
        dict,
    ):
        raise TypeError(
            "news_item must be a dictionary"
        )

    if watchlist is None:
        watchlist = load_watchlist()

    if not isinstance(
        watchlist,
        dict,
    ):
        raise TypeError(
            "watchlist must be a dictionary"
        )

    matches = []

    for ticker, company in (
        watchlist.items()
    ):

        if not isinstance(
            company,
            dict,
        ):
            continue

        programs = company.get(
            "programs",
            [],
        )

        if not isinstance(
            programs,
            list,
        ):
            continue

        company_matches = match_company(
            news_item,
            ticker,
            company,
        )

        for program in programs:

            program_matches = match_program(
                news_item,
                ticker,
                program,
            )

            if (
                not company_matches
                and not program_matches
            ):
                continue

            match_type = "UNKNOWN"

            if (
                company_matches
                and program_matches
            ):
                match_type = (
                    "COMPANY_AND_PROGRAM"
                )

            elif company_matches:
                match_type = "COMPANY"

            elif program_matches:
                match_type = "PROGRAM"

            matches.append({
                "ticker": ticker,
                "company": company.get(
                    "company",
                    ticker,
                ),
                "program": program,
                "match_type": match_type,
                "company_matches": (
                    company_matches
                ),
                "program_matches": (
                    program_matches
                ),
                "confidence": (
                    get_match_confidence(
                        match_type
                    )
                ),
                "news": news_item,
            })

    return matches


# ============================================
# MATCH CONFIDENCE
# ============================================

def get_match_confidence(
    match_type,
):
    """
    Assegna un livello di confidenza
    alla corrispondenza.
    """

    match_type = str(
        match_type or ""
    ).upper()

    if match_type == (
        "COMPANY_AND_PROGRAM"
    ):
        return "HIGH"

    if match_type == "PROGRAM":
        return "HIGH"

    if match_type == "COMPANY":
        return "MEDIUM"

    return "LOW"


# ============================================
# BEST MATCH
# ============================================

def get_best_match(
    matches,
):
    """
    Restituisce il match più affidabile.

    Priorità:
    1. COMPANY_AND_PROGRAM
    2. PROGRAM
    3. COMPANY
    """

    if not matches:
        return None

    priority = {
        "COMPANY_AND_PROGRAM": 3,
        "PROGRAM": 2,
        "COMPANY": 1,
    }

    ordered = sorted(
        matches,
        key=lambda item: priority.get(
            item.get(
                "match_type",
                "",
            ),
            0,
        ),
        reverse=True,
    )

    return ordered[0]


# ============================================
# MATCH SINGLE NEWS
# ============================================

def identify_fda_target(
    news_item,
    watchlist=None,
):
    """
    Identifica il miglior target della news FDA.

    REGOLA DI SICUREZZA:

    Per la pipeline FDA destinata agli alert
    non è sufficiente identificare soltanto
    l'azienda o il ticker.

    Deve essere identificato anche uno specifico
    programma/farmaco.

    Questo impedisce casi come:

        RARE
        -> Ultragenyx
        -> UX111

    quando UX111 NON compare realmente nella news.

    Esempi:

        "FDA approves VYVGART..."
            -> ARGX / VYVGART

        "FDA approves zidesamtinib..."
            -> NUVL / zidesamtinib

        "RARE sector activity..."
            -> None

        "Ultragenyx announces UX111 update..."
            -> RARE / UX111
    """

    matches = match_fda_news(
        news_item,
        watchlist,
    )

    if not matches:
        return None

    # ----------------------------------------
    # SAFETY FILTER
    # ----------------------------------------
    #
    # Scartiamo tutti i match che non hanno
    # identificato un programma specifico.
    #
    # Questo è il punto fondamentale della
    # correzione anti-falso-positivo.
    # ----------------------------------------

    program_matches = [
        match
        for match in matches
        if match.get("program_matches")
    ]

    if not program_matches:
        return None

    return get_best_match(
        program_matches
    )


# ============================================
# MULTIPLE NEWS
# ============================================

def match_fda_news_batch(
    news_items,
    watchlist=None,
):
    """
    Applica il matching a una lista di news FDA.

    Restituisce una lista di risultati, inclusi
    anche quelli senza corrispondenza valida.
    """

    if not news_items:
        return []

    results = []

    for news_item in news_items:

        matches = match_fda_news(
            news_item,
            watchlist,
        )

        best_match = identify_fda_target(
            news_item,
            watchlist,
        )

        results.append({
            "news": news_item,
            "matches": matches,
            "best_match": best_match,
            "matched": best_match is not None,
        })

    return results


# ============================================
# FILTER MATCHED NEWS
# ============================================

def filter_matched_fda_news(
    news_items,
    watchlist=None,
):
    """
    Restituisce soltanto le news FDA
    che hanno un target valido nella watchlist.

    Un target valido deve avere anche uno
    specifico programma/farmaco identificato.
    """

    batch = match_fda_news_batch(
        news_items,
        watchlist,
    )

    return [
        item
        for item in batch
        if item["matched"]
    ]


# ============================================
# PUBLIC API
# ============================================

__all__ = [
    "normalize",
    "load_json",
    "load_watchlist",
    "load_aliases",
    "get_news_text_parts",
    "build_news_text",
    "build_raw_news_text",
    "get_company_aliases",
    "get_program_aliases",
    "contains_alias",
    "contains_ticker",
    "match_company",
    "match_program",
    "match_fda_news",
    "get_match_confidence",
    "get_best_match",
    "identify_fda_target",
    "match_fda_news_batch",
    "filter_matched_fda_news",
]


# ============================================
# DIRECT EXECUTION
# ============================================

if __name__ == "__main__":
    print(
        "FDA Matcher module loaded successfully."
    )