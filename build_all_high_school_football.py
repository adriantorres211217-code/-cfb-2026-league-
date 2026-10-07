#!/usr/bin/env python3
"""
Build a nationwide U.S. high-school football league JSON from MaxPreps school pages.

Output:
    high_school_football_all_usa.json
    high_school_football_all_usa_raw_schools.json

The league JSON matches the user's existing import schema:
conferences -> teams -> name/mascot/colors/prestige/schemes/abbreviation/region/logoURL
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.maxpreps.com"
OUTPUT = "high_school_football_all_usa.json"
RAW_OUTPUT = "high_school_football_all_usa_raw_schools.json"

STATES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
    "HI":"Hawaii","ID":"Idaho","IL":"Illinois","IN":"Indiana","IA":"Iowa",
    "KS":"Kansas","KY":"Kentucky","LA":"Louisiana","ME":"Maine","MD":"Maryland",
    "MA":"Massachusetts","MI":"Michigan","MN":"Minnesota","MS":"Mississippi","MO":"Missouri",
    "MT":"Montana","NE":"Nebraska","NV":"Nevada","NH":"New Hampshire","NJ":"New Jersey",
    "NM":"New Mexico","NY":"New York","NC":"North Carolina","ND":"North Dakota","OH":"Ohio",
    "OK":"Oklahoma","OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont",
    "VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
    "DC":"District of Columbia",
}

REGIONS = {
    "AL":"Southeast","AK":"West","AZ":"West","AR":"South","CA":"West","CO":"West",
    "CT":"Northeast","DE":"Northeast","FL":"Southeast","GA":"Southeast","HI":"West",
    "ID":"West","IL":"Midwest","IN":"Midwest","IA":"Midwest","KS":"Midwest","KY":"South",
    "LA":"South","ME":"Northeast","MD":"Northeast","MA":"Northeast","MI":"Midwest",
    "MN":"Midwest","MS":"South","MO":"Midwest","MT":"West","NE":"Midwest","NV":"West",
    "NH":"Northeast","NJ":"Northeast","NM":"West","NY":"Northeast","NC":"Southeast",
    "ND":"Midwest","OH":"Midwest","OK":"South","OR":"West","PA":"Northeast","RI":"Northeast",
    "SC":"Southeast","SD":"Midwest","TN":"South","TX":"South","UT":"West","VT":"Northeast",
    "VA":"Southeast","WA":"West","WV":"South","WI":"Midwest","WY":"West","DC":"Northeast",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)

def slug_state(abbr: str) -> str:
    # MaxPreps uses lower-case state abbreviations.
    return abbr.lower()

def stable_colors(name: str) -> tuple[str, str, str]:
    """
    Fallback only when MaxPreps does not expose school colors.
    Generates consistent colors from school name so teams are visually distinct.
    """
    h = hashlib.sha256(name.encode("utf-8")).hexdigest()
    p = f"#{h[:6].upper()}"
    s = f"#{h[6:12].upper()}"
    return p, s, "#FFFFFF"

def abbreviation(name: str, state: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    if not words:
        return state
    if len(words) == 1:
        core = words[0][:4]
    else:
        core = "".join(w[0] for w in words[:4])
    return (core + state)[:6]

def get(url: str, tries: int = 4) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 429:
                time.sleep(3 + i * 4)
                continue
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(1.5 + i * 2)
    raise RuntimeError(f"GET failed: {url}: {last}")

def find_build_id() -> str | None:
    try:
        html = get(BASE + "/").text
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
        if not m:
            return None
        data = json.loads(m.group(1))
        return data.get("buildId")
    except Exception:
        return None

def schools_from_next_data(build_id: str, state: str) -> list[dict[str, Any]]:
    url = f"{BASE}/_next/data/{build_id}/{slug_state(state)}/football/schools.json"
    r = get(url)
    data = r.json()
    groups = data.get("pageProps", {}).get("groupings", [])
    schools = []
    for item in groups:
        if isinstance(item, dict):
            schools.append(item)
    return schools

def schools_from_html(state: str) -> list[dict[str, Any]]:
    """
    HTML fallback. MaxPreps state football pages list schools with links.
    """
    url = f"{BASE}/{slug_state(state)}/football/schools/"
    html = get(url).text
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = " ".join(a.stripped_strings).strip()
        if not text:
            continue
        # Team/school URLs typically contain /football/ somewhere beneath a school slug.
        if "/football/" not in href:
            continue
        if href.endswith("/schools/") or "/rankings/" in href or "/scores/" in href:
            continue

        full = urljoin(BASE, href)
        key = full.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)

        # Avoid nav links.
        if text.lower() in {"football", "teams", "players", "rankings", "scores", "news",
                            "photos", "videos", "playoffs", "stat leaders"}:
            continue

        found.append({
            "name": text,
            "canonicalUrl": full,
            "state": state,
        })
    return found

def normalize_entry(raw: dict[str, Any], state: str) -> dict[str, Any]:
    name = (
        raw.get("name")
        or raw.get("schoolName")
        or raw.get("teamName")
        or raw.get("title")
        or "Unknown School"
    )
    city = raw.get("city") or ""
    team_id = raw.get("teamId") or raw.get("id") or ""
    canonical = raw.get("canonicalUrl") or raw.get("url") or ""
    if canonical and canonical.startswith("/"):
        canonical = urljoin(BASE, canonical)

    logo = (
        raw.get("mascotUrl")
        or raw.get("logoUrl")
        or raw.get("logoURL")
        or raw.get("imageUrl")
        or ""
    )
    mascot = raw.get("mascot") or raw.get("nickname") or ""

    # Prefer real colors if source supplies them.
    primary = raw.get("primaryColor") or raw.get("primary") or ""
    secondary = raw.get("secondaryColor") or raw.get("secondary") or ""
    tertiary = raw.get("tertiaryColor") or raw.get("tertiary") or "#FFFFFF"

    return {
        "teamId": team_id,
        "name": str(name).strip(),
        "mascot": str(mascot).strip(),
        "city": str(city).strip(),
        "state": state,
        "canonicalUrl": canonical,
        "logoURL": logo,
        "primary": primary,
        "secondary": secondary,
        "tertiary": tertiary,
        "raw": raw,
    }

def parse_team_page(school: dict[str, Any]) -> dict[str, Any]:
    """
    Best-effort enrichment. Extracts mascot, colors and logo when exposed in page metadata.
    Failure never removes the school.
    """
    url = school.get("canonicalUrl")
    if not url:
        return school

    try:
        html = get(url, tries=3).text
        soup = BeautifulSoup(html, "html.parser")

        # OG image is frequently the school/mascot image.
        og = soup.find("meta", attrs={"property":"og:image"})
        if og and og.get("content") and not school.get("logoURL"):
            school["logoURL"] = og["content"]

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        # Common title shape: "School Mascot ... Football"
        school_name = school["name"]
        if not school.get("mascot") and title:
            before_football = re.split(r"\bFootball\b", title, flags=re.I)[0].strip(" -|")
            if before_football.lower().startswith(school_name.lower()):
                rest = before_football[len(school_name):].strip(" -|")
                # Avoid swallowing city/state metadata.
                rest = re.split(r"\s+\([A-Z]{2}\)\s*$", rest)[0].strip()
                if rest and len(rest) <= 40:
                    school["mascot"] = rest

        # Parse JSON-LD / embedded data for explicit fields.
        for script in soup.find_all("script"):
            txt = script.string or script.get_text("", strip=False)
            if not txt or len(txt) > 2_000_000:
                continue
            if not school.get("mascot"):
                m = re.search(r'"mascot"\s*:\s*"([^"]+)"', txt, re.I)
                if m:
                    school["mascot"] = m.group(1)
            if not school.get("primary"):
                m = re.search(r'"primaryColor"\s*:\s*"(#[0-9A-Fa-f]{6})"', txt)
                if m:
                    school["primary"] = m.group(1)
            if not school.get("secondary"):
                m = re.search(r'"secondaryColor"\s*:\s*"(#[0-9A-Fa-f]{6})"', txt)
                if m:
                    school["secondary"] = m.group(1)
    except Exception:
        pass
    return school

def prestige_from_raw(raw: dict[str, Any]) -> float:
    """
    Use any live ranking/rating values MaxPreps exposes. Otherwise a neutral HS baseline.
    Elite national teams should sort higher when rank/rating data is present.
    """
    # Direct rating-like values.
    for k in ("rating", "computerRating", "maxPrepsRating", "score"):
        v = raw.get(k)
        try:
            v = float(v)
            # map arbitrary ratings into a sane 40-100 band
            if v > 0:
                return round(max(40.0, min(100.0, 50.0 + v)), 1)
        except Exception:
            pass

    # Rank-like values: national rank is strongest signal, then state rank.
    for k, ceiling in (("nationalRank", 100.0), ("rank", 96.0), ("stateRank", 90.0)):
        v = raw.get(k)
        try:
            rank = int(v)
            if rank > 0:
                # Smooth decay: rank 1 ~= ceiling, rank 100 ~= ~80, rank 1000 ~= ~60.
                import math
                val = ceiling - 12.0 * math.log10(rank)
                return round(max(40.0, min(100.0, val)), 1)
        except Exception:
            pass

    return 50.0

def to_team(s: dict[str, Any]) -> dict[str, Any]:
    p, q, t = s.get("primary"), s.get("secondary"), s.get("tertiary")
    if not p or not q:
        fp, fq, ft = stable_colors(s["name"] + s["state"])
        p = p or fp
        q = q or fq
        t = t or ft

    mascot = s.get("mascot") or "Football"
    raw = s.get("raw") or {}

    return {
        "name": s["name"],
        "mascot": mascot,
        "primary": p,
        "secondary": q,
        "tertiary": t or "#FFFFFF",
        "prestige": prestige_from_raw(raw),
        "offenseScheme": "spread",
        "defenseScheme": "4-2-5",
        "abbreviation": abbreviation(s["name"], s["state"]),
        "region": REGIONS.get(s["state"], "National"),
        "logoURL": s.get("logoURL") or "",
    }

def scrape_state(build_id: str | None, state: str) -> list[dict[str, Any]]:
    print(f"[{state}] loading schools...", flush=True)
    raws = []
    if build_id:
        try:
            raws = schools_from_next_data(build_id, state)
        except Exception as e:
            print(f"[{state}] Next-data failed, using HTML fallback: {e}", flush=True)

    if not raws:
        raws = schools_from_html(state)

    schools = [normalize_entry(x, state) for x in raws]
    # de-dupe by teamId/url/name+city
    uniq = {}
    for s in schools:
        key = s["teamId"] or s["canonicalUrl"] or f'{s["name"]}|{s["city"]}|{state}'
        uniq[key] = s
    schools = list(uniq.values())

    # Enrich pages concurrently but conservatively.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        schools = list(ex.map(parse_team_page, schools))

    print(f"[{state}] {len(schools)} schools", flush=True)
    return schools

def main():
    build_id = find_build_id()
    print("MaxPreps build id:", build_id or "not found (HTML fallback will be used)")

    all_raw: list[dict[str, Any]] = []
    conferences = []

    for state, state_name in STATES.items():
        try:
            schools = scrape_state(build_id, state)
        except Exception as e:
            print(f"[{state}] FAILED: {e}", file=sys.stderr)
            schools = []

        all_raw.extend(schools)

        teams = [to_team(s) for s in schools]
        teams.sort(key=lambda x: (-x["prestige"], x["name"]))

        conferences.append({
            "name": f"{state_name} High School Football",
            "requiredConferenceGames": 0,
            "conferencePrestige": 50.0,
            "tier": "High School",
            "teams": teams,
            "protectedPairs": [],
        })

        # Incremental save so a long run is crash-safe.
        partial = {
            "conferences": conferences,
            "independents": [],
            "bowls": [],
            "ny6Bowls": [],
            "rivalries": [],
            "protectedPairs": [],
            "nationalChampionshipLogoURL": "",
            "subdivisionTeams": [],
            "awardCustomizations": [],
        }
        with open(OUTPUT + ".partial", "w", encoding="utf-8") as f:
            json.dump(partial, f, indent=2, ensure_ascii=False)

        time.sleep(1.0)

    league = {
        "conferences": conferences,
        "independents": [],
        "bowls": [],
        "ny6Bowls": [],
        "rivalries": [],
        "protectedPairs": [],
        "nationalChampionshipLogoURL": "",
        "subdivisionTeams": [],
        "awardCustomizations": [],
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(league, f, indent=2, ensure_ascii=False)

    cleaned_raw = []
    for s in all_raw:
        x = dict(s)
        x.pop("raw", None)
        cleaned_raw.append(x)
    with open(RAW_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(cleaned_raw, f, indent=2, ensure_ascii=False)

    total = sum(len(c["teams"]) for c in conferences)
    print(f"DONE: {total:,} football schools across {len(conferences)} state/DC groups")
    print(f"League file: {OUTPUT}")
    print(f"Raw school file: {RAW_OUTPUT}")

if __name__ == "__main__":
    main()
