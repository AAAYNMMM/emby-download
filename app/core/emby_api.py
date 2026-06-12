"""
Emby REST API client.

Provides a thin wrapper around the Emby HTTP API for all endpoints
used by EmbyD.
"""

from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.utils.logger import get_logger

# Default headers required by Emby API
EMBY_CLIENT_HEADERS = {
    "X-Emby-Client": "EmbyD",
    "X-Emby-Client-Version": "0.1.0",
    "X-Emby-Device-Name": "EmbyD-Desktop",
    "X-Emby-Device-Id": "embyd-desktop-001",
}


class EmbyApiError(Exception):
    """Base exception for Emby API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[requests.Response] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class EmbyAuthError(EmbyApiError):
    """Authentication-related errors (401, 403)."""
    pass


class EmbyNotFoundError(EmbyApiError):
    """Resource not found (404)."""
    pass


class EmbyServerError(EmbyApiError):
    """Server-side errors (500, 502, 503)."""
    pass


class EmbyApiClient:
    """
    HTTP client for Emby REST API.

    Usage:
        client = EmbyApiClient("http://192.168.1.100:8096")
        token = client.authenticate("username", "password")
        client.set_token(token)
        libraries = client.get_libraries(user_id)
    """

    def __init__(self, server_url: str, token: Optional[str] = None):
        """
        Initialize the Emby API client.

        Args:
            server_url: Base URL of the Emby server (e.g., http://192.168.1.100:8096)
            token: Optional access token for authenticated requests.
        """
        # Normalize server URL - remove trailing slash to avoid double slashes
        self.server_url = server_url.rstrip("/")
        # Ensure it starts with http:// or https://
        if not self.server_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid server URL: {server_url}. Must start with http:// or https://")
        self._token = token

        # Configure session with retry strategy
        self._session = requests.Session()
        self._session.headers.update(EMBY_CLIENT_HEADERS)

        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._logger = get_logger()

    def set_token(self, token: str) -> None:
        """Set the access token for authenticated requests."""
        self._token = token

    @property
    def has_token(self) -> bool:
        """Check if an access token is set."""
        return bool(self._token)

    # ---- Internal HTTP methods ----

    def _headers(self) -> dict[str, str]:
        """Get headers including auth token if available."""
        headers = {}
        if self._token:
            headers["X-Emby-Token"] = self._token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: int = 30,
    ) -> requests.Response:
        """
        Make an HTTP request to the Emby server.

        Args:
            method: HTTP method (GET, POST, HEAD)
            path: API path (e.g., /Users/AuthenticateByName)
            params: Query parameters
            json_data: JSON body for POST requests
            headers: Additional headers
            timeout: Request timeout in seconds

        Returns:
            Response object

        Raises:
            EmbyAuthError: If 401 or 403
            EmbyNotFoundError: If 404
            EmbyServerError: If 5xx
            EmbyApiError: Other errors
        """
        # If path is already a full URL, use it directly
        if path.startswith(("http://", "https://")):
            url = path
        else:
            url = f"{self.server_url}{path}"
        req_headers = {**self._headers(), **(headers or {})}

        self._logger.debug(f"API {method} {path}")

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=req_headers,
                timeout=timeout,
            )
        except requests.exceptions.ConnectionError as e:
            error_msg = str(e).lower()
            if "refused" in error_msg:
                raise EmbyApiError(
                    f"Connection refused: {self.server_url}. Check that the server is running and the address/port is correct.",
                    response=getattr(e, 'response', None),
                )
            if "certificate" in error_msg or "cert" in error_msg:
                raise EmbyApiError(
                    f"SSL certificate error: {e}. Try using http:// instead of https:// or check the certificate.",
                )
            raise EmbyApiError(f"Connection failed: cannot reach {self.server_url}. Check network and server status.")
        except requests.exceptions.Timeout as e:
            raise EmbyApiError(
                f"Request timed out (>{timeout}s): {self.server_url}. Server may be slow or unreachable."
            )
        except requests.exceptions.SSLError as e:
            raise EmbyApiError(
                f"SSL error connecting to {self.server_url}: {e}. "
                "Check certificate or try using http:// instead of https://."
            )
        except requests.exceptions.RequestException as e:
            raise EmbyApiError(f"Request failed: {e}")

        # Handle HTTP errors
        if response.status_code == 401:
            raise EmbyAuthError(
                "Unauthorized: Access token is invalid or expired. Please login again.",
                status_code=401,
                response=response,
            )
        elif response.status_code == 403:
            raise EmbyAuthError(
                "Forbidden: No permission to access this resource. "
                "Check your account permissions on the Emby server.",
                status_code=403,
                response=response,
            )
        elif response.status_code == 404:
            raise EmbyNotFoundError(
                "Resource not found. The item may have been deleted.",
                status_code=404,
                response=response,
            )
        elif response.status_code == 416:
            # Range Not Satisfiable - file may be complete
            self._logger.debug(f"Range not satisfiable for {path}")
        elif response.status_code >= 500:
            raise EmbyServerError(
                f"Server error: {response.status_code}. Please try again later.",
                status_code=response.status_code,
                response=response,
            )
        elif response.status_code >= 400:
            raise EmbyApiError(
                f"API error: {response.status_code}",
                status_code=response.status_code,
                response=response,
            )

        return response

    def _get(self, path: str, **kwargs) -> requests.Response:
        """HTTP GET request."""
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> requests.Response:
        """HTTP POST request."""
        return self._request("POST", path, **kwargs)

    def _head(self, path: str, **kwargs) -> requests.Response:
        """HTTP HEAD request."""
        return self._request("HEAD", path, **kwargs)

    # ---- Authentication API ----

    def authenticate(self, username: str, password: str, timeout: int = 30) -> str:
        """
        Authenticate with the Emby server using username/password.

        Args:
            username: Emby username
            password: Emby password (plain text)
            timeout: Request timeout

        Returns:
            Access token string

        Raises:
            EmbyAuthError: If authentication fails
            EmbyApiError: Other errors
        """
        import hashlib

        # Emby expects SHA1 hash of the password
        password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest().lower()

        payload = {
            "Username": username,
            "Pw": password,
            "Password": password_hash,
        }

        response = self._post(
            "/Users/AuthenticateByName",
            json_data=payload,
            timeout=timeout,
        )

        data = response.json()
        access_token = data.get("AccessToken")
        if not access_token:
            raise EmbyAuthError(
                "Authentication failed: No access token in response. "
                "Check username and password."
            )

        return access_token

    # ---- User API ----

    def get_user(self) -> dict[str, Any]:
        """
        Get current user information.

        Returns:
            User object dict (contains Id, Name, etc.)
        """
        response = self._get("/Users")
        users = response.json()
        if not users:
            raise EmbyApiError("No users found")
        return users[0]

    # ---- Library API ----

    def get_libraries(self, user_id: str) -> list[dict[str, Any]]:
        """
        Get user's media libraries (views).

        Args:
            user_id: Emby user ID

        Returns:
            List of library/view objects
        """
        response = self._get(f"/Users/{user_id}/Views")
        data = response.json()
        return data.get("Items", [])

    # ---- Items/Search API ----

    def search_items(
        self,
        user_id: str,
        query: str,
        parent_id: Optional[str] = None,
        include_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search for media items.

        Args:
            user_id: Emby user ID
            query: Search term
            parent_id: Optional library ID to restrict search
            include_types: Item types to include (default: ["Movie", "Episode"])
            limit: Max results

        Returns:
            List of item objects
        """
        if include_types is None:
            include_types = ["Movie", "Episode"]

        params = {
            "SearchTerm": query,
            "IncludeItemTypes": ",".join(include_types),
            "Limit": limit,
            "Recursive": "true",
        }

        if parent_id:
            params["ParentId"] = parent_id

        response = self._get(f"/Users/{user_id}/Items", params=params)
        data = response.json()
        return data.get("Items", [])

    def get_item(self, user_id: str, item_id: str) -> dict[str, Any]:
        """
        Get detailed information about a media item.

        Args:
            user_id: Emby user ID
            item_id: Media item ID

        Returns:
            Item object dict
        """
        response = self._get(f"/Users/{user_id}/Items/{item_id}")
        return response.json()

    # ---- Playback API ----

    def get_playback_info(self, item_id: str, user_id: str) -> dict[str, Any]:
        """
        Get playback information including MediaSources.

        Args:
            item_id: Media item ID
            user_id: Emby user ID

        Returns:
            PlaybackInfo response dict
        """
        params = {"UserId": user_id}
        response = self._get(f"/Items/{item_id}/PlaybackInfo", params=params)
        return response.json()

    # ---- Download URLs ----

    def get_download_url(self, item_id: str) -> str:
        """
        Get the direct download URL for an item (original file).

        Args:
            item_id: Media item ID

        Returns:
            Full download URL string
        """
        return f"{self.server_url}/Items/{item_id}/Download?api_key={self._token}"

    def get_stream_url(
        self,
        item_id: str,
        media_source_id: str,
        static: bool = True,
    ) -> str:
        """
        Get the Direct Stream URL for a media source.

        Args:
            item_id: Media item ID
            media_source_id: MediaSource ID
            static: True for Direct Stream, False for transcoded stream

        Returns:
            Full stream URL string
        """
        params = (
            f"Static=true&MediaSourceId={media_source_id}&api_key={self._token}"
            if static
            else f"MediaSourceId={media_source_id}&api_key={self._token}"
        )
        return f"{self.server_url}/Videos/{item_id}/stream?{params}"

    # ---- Subtitles API ----

    def get_subtitle_url(self, item_id: str, media_source_id: str, index: int, format: str = "srt") -> str:
        """
        Get the download URL for a subtitle track.

        Args:
            item_id: Emby item ID.
            media_source_id: MediaSource ID.
            index: Subtitle track index.
            format: Subtitle format (srt, ass, ssa, vtt, etc.)

        Returns:
            Full subtitle download URL.
        """
        return (
            f"{self.server_url}/Videos/{item_id}/{media_source_id}/Subtitles/{index}/Stream."
            f"{format}?api_key={self._token}"
        )

    def get_subtitles(self, item_id: str, media_source_id: str) -> list[dict[str, Any]]:
        """
        Get available subtitle tracks for a media source.

        Args:
            item_id: Emby item ID.
            media_source_id: MediaSource ID.

        Returns:
            List of subtitle track dicts.
        """
        try:
            playback_info = self.get_playback_info(item_id, "")
            # MediaSources are embedded in playback info
            for ms in playback_info.get("MediaSources", []):
                if ms.get("Id") == media_source_id:
                    return ms.get("MediaStreams", [])
            return []
        except Exception:
            return []

    def get_item_metadata(self, item_id: str, user_id: str) -> dict[str, Any]:
        """
        Get detailed item metadata including all fields needed for NFO.

        Args:
            item_id: Emby item ID.
            user_id: Emby user ID.

        Returns:
            Item object with full metadata.
        """
        params = {"UserId": user_id}
        return self._get(f"/Users/{user_id}/Items/{item_id}", params=params).json()

    # ---- Series / Season / Episode API ----

    def get_series_seasons(self, series_id: str, user_id: str) -> list[dict[str, Any]]:
        """
        Get all seasons for a series.

        API: /Shows/{series_id}/Seasons?UserId={user_id}

        Args:
            series_id: Emby series (Show) ID.
            user_id: Emby user ID.

        Returns:
            List of season item dicts. Returns [] on empty / error.

        Raises:
            EmbyAuthError: If 401 or 403.
            EmbyNotFoundError: If 404.
        """
        response = self._get(
            f"/Shows/{series_id}/Seasons",
            params={"UserId": user_id},
        )
        return response.json().get("Items", [])

    def get_season_episodes(
        self,
        season_id: str,
        user_id: str,
        series_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get all episodes for a season.

        Preferred (when series_id is available):
          /Shows/{series_id}/Episodes?UserId={user_id}&SeasonId={season_id}
        Fallback:
          /Users/{user_id}/Items?ParentId={season_id}&IncludeItemTypes=Episode

        Results are sorted by IndexNumber.

        Args:
            season_id: Emby season ID.
            user_id: Emby user ID.
            series_id: Optional series (Show) ID for the preferred endpoint.

        Returns:
            List of episode item dicts. Returns [] on empty / error.

        Raises:
            EmbyAuthError: If 401 or 403.
            EmbyNotFoundError: If 404.
        """
        if series_id:
            response = self._get(
                f"/Shows/{series_id}/Episodes",
                params={"UserId": user_id, "SeasonId": season_id},
            )
        else:
            response = self._get(
                f"/Users/{user_id}/Items",
                params={"ParentId": season_id, "IncludeItemTypes": "Episode"},
            )
        episodes = response.json().get("Items", [])
        # Sort by IndexNumber; episodes missing IndexNumber sort last
        episodes.sort(key=lambda e: (
            0 if e.get("IndexNumber") is not None else 1,
            e.get("IndexNumber") or 999999,
        ))
        return episodes

    def get_series_episodes(
        self,
        series_id: str,
        user_id: str,
        season_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Get episodes for a series, optionally filtered by season.

        When *season_id* is provided, returns episodes for that season only.
        Otherwise returns all episodes across all seasons.

        Results are sorted by (SeasonNumber, IndexNumber).

        Args:
            series_id: Emby series (Show) ID.
            user_id: Emby user ID.
            season_id: Optional season ID to filter by.

        Returns:
            List of episode item dicts. Returns [] on empty / error.

        Raises:
            EmbyAuthError: If 401 or 403.
            EmbyNotFoundError: If 404.
        """
        if season_id:
            return self.get_season_episodes(season_id, user_id, series_id)

        response = self._get(
            f"/Shows/{series_id}/Episodes",
            params={"UserId": user_id},
        )
        episodes = response.json().get("Items", [])
        # Sort by ParentIndexNumber then IndexNumber
        episodes.sort(key=lambda e: (
            0 if e.get("ParentIndexNumber") is not None else 1,
            e.get("ParentIndexNumber") or 999999,
            0 if e.get("IndexNumber") is not None else 1,
            e.get("IndexNumber") or 999999,
        ))
        return episodes

    # ---- Utility ----

    def check_download_access(self, item_id: str) -> bool:
        """
        Check if direct download is available by sending a HEAD request.

        Args:
            item_id: Media item ID

        Returns:
            True if download endpoint returns 200/206
        """
        url = self.get_download_url(item_id)
        try:
            response = self._head(url, timeout=10)
            return response.status_code in (200, 206)
        except EmbyAuthError:
            return False
        except Exception:
            return False

    def get_file_size(self, url: str) -> Optional[int]:
        """
        Get file size via HEAD request (checks Content-Length).

        Args:
            url: Download/stream URL

        Returns:
            File size in bytes, or None if unknown
        """
        try:
            response = self._head(url, timeout=10)
            content_length = response.headers.get("Content-Length")
            if content_length:
                return int(content_length)
            return None
        except Exception:
            return None

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
