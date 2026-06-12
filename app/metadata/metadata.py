"""
Metadata download module for EmbyD.

Handles:
- Downloading subtitles
- Generating Kodi-compatible NFO files
"""

import os
import re
import xml.dom.minidom
from pathlib import Path
from typing import Any, Optional

from app.core.emby_api import EmbyApiClient
from app.utils.logger import get_logger

_logger = get_logger()


# ---- Subtitle Download ----

async def download_subtitles(
    client: EmbyApiClient,
    item_id: str,
    media_source_id: str,
    dest_dir: str,
    base_name: str,
    language_filter: Optional[list[str]] = None,
) -> list[str]:
    """
    Download available subtitle tracks for a movie.

    Args:
        client: Authenticated EmbyApiClient.
        item_id: Emby item ID.
        media_source_id: MediaSource ID.
        dest_dir: Directory to save subtitles.
        base_name: Base filename (without extension).
        language_filter: Only download these languages (e.g. ["chi", "eng"]).
                        None = download all.

    Returns:
        List of saved subtitle file paths.
    """
    import aiohttp
    import aiofiles

    saved = []
    subtitles = client.get_subtitles(item_id, media_source_id)

    for sub in subtitles:
        if sub.get("Type") != "Subtitle":
            continue

        lang = sub.get("Language", "und")
        codec = sub.get("Codec", "srt").lower()
        index = sub.get("Index", 0)
        display_title = sub.get("DisplayTitle", "")

        # Filter by language
        if language_filter and lang not in language_filter:
            continue

        # Map codec to file extension
        ext_map = {
            "srt": "srt",
            "ass": "ass",
            "ssa": "ass",
            "sub": "sub",
            "smi": "smi",
            "vtt": "vtt",
            "pgs": "sup",
            "dvd": "sub",
        }
        ext = ext_map.get(codec, "srt")

        # Build filename: movie.chi.srt, movie.eng.srt
        sub_filename = f"{base_name}.{lang}.{ext}"
        sub_path = os.path.join(dest_dir, sub_filename)

        url = client.get_subtitle_url(item_id, media_source_id, index, codec)
        if not url:
            continue

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        _logger.warning(f"Subtitle download returned HTTP {response.status}")
                        continue

                    async with aiofiles.open(sub_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(65536):
                            await f.write(chunk)

            file_size = os.path.getsize(sub_path)
            if file_size > 0:
                saved.append(sub_path)
                _logger.info(f"Subtitle saved: {sub_path} ({lang}, {file_size} bytes)")
        except Exception as e:
            _logger.warning(f"Failed to download subtitle index {index}: {e}")

    return saved


# ---- NFO Generator ----

def generate_nfo(
    item: dict[str, Any],
    file_path: Optional[str] = None,
    dest_dir: Optional[str] = None,
    base_name: Optional[str] = None,
) -> str:
    """
    Generate a Kodi-compatible NFO file from Emby item metadata.

    Args:
        item: Full Emby item object from get_item_metadata().
        file_path: If set, write NFO to this path.
        dest_dir: Directory to write NFO (used with base_name).
        base_name: Base filename for NFO (used with dest_dir).

    Returns:
        NFO XML content as string.
    """
    root = _create_nfo_root(item)
    xml_str = _pretty_xml(root)

    # Determine output path
    if file_path:
        nfo_path = file_path
    elif dest_dir and base_name:
        nfo_path = os.path.join(dest_dir, f"{base_name}.nfo")
    else:
        return xml_str

    # Write to file
    Path(nfo_path).parent.mkdir(parents=True, exist_ok=True)
    with open(nfo_path, "w", encoding="utf-8") as f:
        f.write(xml_str)

    _logger.info(f"NFO saved: {nfo_path}")
    return xml_str


def _create_nfo_root(item: dict) -> Any:
    """Create the XML document for a movie NFO."""
    import xml.etree.ElementTree as ET

    movie = ET.Element("movie")

    # Title
    title = ET.SubElement(movie, "title")
    title.text = item.get("Name", "Unknown")

    # Sort title
    sort_title = item.get("SortName") or item.get("Name", "")
    st = ET.SubElement(movie, "sorttitle")
    st.text = sort_title

    # Original title
    orig_title = item.get("OriginalTitle", "")
    if orig_title:
        ot = ET.SubElement(movie, "originaltitle")
        ot.text = orig_title

    # Year
    year = item.get("ProductionYear", "")
    if year:
        y = ET.SubElement(movie, "year")
        y.text = str(year)

    # Release date
    premiere = item.get("PremiereDate", "")
    if premiere:
        pd = ET.SubElement(movie, "premiered")
        pd.text = premiere[:10]  # YYYY-MM-DD

    # Rating
    rating = item.get("CommunityRating", item.get("CriticRating", ""))
    if rating:
        r = ET.SubElement(movie, "rating")
        r.text = str(rating)

    # Votes
    votes = item.get("VoteCount", 0)
    if votes:
        v = ET.SubElement(movie, "votes")
        v.text = str(votes)

    # Outline / Plot
    overview = item.get("Overview", "")
    if overview:
        plot = ET.SubElement(movie, "plot")
        plot.text = overview
        outline = ET.SubElement(movie, "outline")
        outline.text = overview[:300] if len(overview) > 300 else overview

    # Tagline
    tagline = item.get("Taglines", [{}])
    if tagline and isinstance(tagline, list) and len(tagline) > 0:
        if isinstance(tagline[0], str):
            tl = ET.SubElement(movie, "tagline")
            tl.text = tagline[0]

    # Runtime
    runtime_ticks = item.get("RunTimeTicks", 0)
    if runtime_ticks:
        minutes = runtime_ticks // 100 // 60
        rt = ET.SubElement(movie, "runtime")
        rt.text = str(minutes)

    # MPAA / Certification
    official_rating = item.get("OfficialRating", "")
    if official_rating:
        mpaa = ET.SubElement(movie, "mpaa")
        mpaa.text = official_rating

    # Genres
    genres = item.get("Genres", [])
    for genre in genres:
        g = ET.SubElement(movie, "genre")
        g.text = genre

    # Studios
    studios = item.get("Studios", [])
    for studio in studios:
        if isinstance(studio, dict):
            s = ET.SubElement(movie, "studio")
            s.text = studio.get("Name", "")

    # Directors (from People)
    people = item.get("People", [])
    directors_added = set()
    writers_added = set()
    for person in people:
        ptype = person.get("Type", "")
        pname = person.get("Name", "")
        role = person.get("Role", "")

        if ptype == "Director" and pname not in directors_added:
            d = ET.SubElement(movie, "director")
            d.text = pname
            directors_added.add(pname)
        elif ptype == "Writer" and pname not in writers_added:
            w = ET.SubElement(movie, "writer")
            w.text = pname
            writers_added.add(pname)

    # Actors
    for person in people:
        if person.get("Type") == "Actor":
            actor = ET.SubElement(movie, "actor")
            an = ET.SubElement(actor, "name")
            an.text = person.get("Name", "")
            arole = ET.SubElement(actor, "role")
            arole.text = person.get("Role", "")

    # Country
    production_locations = item.get("ProductionLocations", [])
    for loc in production_locations:
        if isinstance(loc, str):
            c = ET.SubElement(movie, "country")
            c.text = loc

    # IMDB / TMDB IDs
    provider_ids = item.get("ProviderIds", {})
    imdb_id = provider_ids.get("Imdb", "") or provider_ids.get("IMDB", "")
    tmdb_id = provider_ids.get("Tmdb", "") or provider_ids.get("TMDB", "")
    tvdb_id = provider_ids.get("Tvdb", "") or provider_ids.get("TVDB", "")

    if imdb_id:
        iid = ET.SubElement(movie, "id")
        iid.text = imdb_id
        imdb_elem = ET.SubElement(movie, "imdb_id")
        imdb_elem.text = imdb_id
    if tmdb_id:
        tmdb_elem = ET.SubElement(movie, "tmdb_id")
        tmdb_elem.text = str(tmdb_id)

    # Unique IDs (Kodi v18+)
    if imdb_id:
        uid = ET.SubElement(movie, "uniqueid")
        uid.set("type", "imdb")
        uid.set("default", "true" if not tmdb_id else "false")
        uid.text = imdb_id
    if tmdb_id:
        uid = ET.SubElement(movie, "uniqueid")
        uid.set("type", "tmdb")
        uid.set("default", "true" if not imdb_id else "false")
        uid.text = str(tmdb_id)
    if tvdb_id:
        uid = ET.SubElement(movie, "uniqueid")
        uid.set("type", "tvdb")
        uid.set("default", "false")
        uid.text = str(tvdb_id)

    return movie


def _pretty_xml(root: Any) -> str:
    """Convert XML Element to pretty-printed string."""
    import xml.etree.ElementTree as ET

    rough_string = ET.tostring(root, encoding="unicode")
    dom = xml.dom.minidom.parseString(rough_string)
    return dom.toprettyxml(indent="  ")


def format_runtime(minutes: int) -> str:
    """Format runtime for display."""
    h = minutes // 60
    m = minutes % 60
    if h > 0:
        return f"{h}h {m}min"
    return f"{m}min"
