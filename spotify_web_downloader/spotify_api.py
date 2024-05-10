from __future__ import annotations

import functools
import json
import re
import time
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import base62
import requests


class SpotifyApi:
    SPOTIFY_HOME_PAGE_URL = "https://open.spotify.com/"
    GID_METADATA_API_URL = (
        "https://spclient.wg.spotify.com/metadata/4/track/{gid}?market=from_token"
    )
    VIDEO_MANIFEST_API_URL = "https://gue1-spclient.spotify.com/manifests/v7/json/sources/{gid}/options/supports_drm"
    WIDEVINE_LICENSE_API_URL = (
        "https://gue1-spclient.spotify.com/widevine-license/v1/{type}/license"
    )
    LYRICS_API_URL = "https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}"
    PSSH_API_URL = "https://seektables.scdn.co/seektable/{file_id}.json"
    STREAM_URL_API_URL = (
        "https://gue1-spclient.spotify.com/storage-resolve/v2/files/audio/interactive/11/"
        "{file_id}?version=10000000&product=9&platform=39&alt=json"
    )
    METADATA_API_URL = "https://api.spotify.com/v1/{type}/{track_id}"
    PATHFINDER_API_URL = "https://api-partner.spotify.com/pathfinder/v1/query"
    TRACK_CREDITS_API_URL = "https://spclient.wg.spotify.com/track-credits-view/v0/experimental/{track_id}/credits"
    EXTEND_TRACK_COLLECTION_WAIT_TIME = 0.5

    def __init__(
        self,
        cookies_path: Path = Path("./cookies.txt"),
    ):
        self.cookies_path = cookies_path
        self._setup_session()

    def _setup_session(self):
        self.session = requests.Session()
        if self.cookies_path:
            cookies = MozillaCookieJar(self.cookies_path)
            cookies.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies.update(cookies)
        self.session.headers.update(
            {
                "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
                "accept-language": "en-US",
                "sec-ch-ua-mobile": "?0",
                "app-platform": "WebPlayer",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "accept": "application/json",
                "Referer": self.SPOTIFY_HOME_PAGE_URL,
                "spotify-app-version": "1.2.35.284.g56aba07f",
                "sec-ch-ua-platform": '"Windows"',
            }
        )
        home_page = self.session.get(self.SPOTIFY_HOME_PAGE_URL).text
        token = re.search(r'accessToken":"(.*?)"', home_page).group(1)
        self.is_premium = re.search(r'isPremium":(.*?),', home_page).group(1) == "true"
        self.session.headers.update(
            {
                "authorization": f"Bearer {token}",
            }
        )

    @staticmethod
    def _check_response(response: requests.Response):
        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise Exception(
                f"Request failed with status code {response.status_code}: {response.text}"
            )

    @staticmethod
    def track_id_to_gid(track_id: str) -> str:
        return hex(base62.decode(track_id, base62.CHARSET_INVERTED))[2:].zfill(32)

    @staticmethod
    def gid_to_track_id(gid: str) -> str:
        return base62.encode(int(gid, 16), charset=base62.CHARSET_INVERTED).zfill(22)

    def get_gid_metadata(self, gid: str) -> dict:
        response = self.session.get(self.GID_METADATA_API_URL.format(gid=gid))
        self._check_response(response)
        return response.json()

    def get_video_manifest(self, gid: str) -> dict:
        response = self.session.get(self.VIDEO_MANIFEST_API_URL.format(gid=gid))
        self._check_response(response)
        return response.json()

    def get_widevine_license_music(self, challenge: bytes) -> bytes:
        response = self.session.post(
            self.WIDEVINE_LICENSE_API_URL.format(type="audio"),
            challenge,
        )
        self._check_response(response)
        return response.content

    def get_widevine_license_video(self, challenge: bytes) -> bytes:
        response = self.session.post(
            self.WIDEVINE_LICENSE_API_URL.format(type="video"),
            challenge,
        )
        self._check_response(response)
        return response.content

    def get_lyrics(self, track_id: str) -> dict | None:
        response = self.session.get(self.LYRICS_API_URL.format(track_id=track_id))
        if response.status_code == 404:
            return None
        self._check_response(response)
        return response.json()

    def get_pssh(self, file_id: str) -> str:
        response = requests.get(self.PSSH_API_URL.format(file_id=file_id))
        self._check_response(response)
        return response.json()["pssh"]

    def get_stream_url(self, file_id: str) -> str:
        response = self.session.get(self.STREAM_URL_API_URL.format(file_id=file_id))
        self._check_response(response)
        return response.json()["cdnurl"][0]

    def get_track(self, track_id: str) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="tracks", track_id=track_id)
        )
        self._check_response(response)
        return response.json()

    def extend_track_collection(self, track_collection: dict) -> dict:
        next_url = track_collection["tracks"]["next"]
        while next_url is not None:
            response = self.session.get(next_url)
            self._check_response(response)
            next_tracks = response.json()
            track_collection["tracks"]["items"].extend(next_tracks["items"])
            next_url = next_tracks["next"]
            time.sleep(self.EXTEND_TRACK_COLLECTION_WAIT_TIME)
        return track_collection

    @functools.lru_cache()
    def get_album(
        self,
        album_id: str,
        extend: bool = True,
    ) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="albums", track_id=album_id)
        )
        self._check_response(response)
        album = response.json()
        if extend:
            album = self.extend_track_collection(album)
        return album

    def get_playlist(
        self,
        playlist_id: str,
        extend: bool = True,
    ) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="playlists", track_id=playlist_id)
        )
        self._check_response(response)
        playlist = response.json()
        if extend:
            playlist = self.extend_track_collection(playlist)
        return playlist

    def get_now_playing_view(self, track_id: str, artist_id: str) -> dict:
        response = self.session.get(
            self.PATHFINDER_API_URL,
            params={
                "operationName": "queryNpvArtist",
                "variables": json.dumps(
                    {
                        "artistUri": f"spotify:artist:{artist_id}",
                        "trackUri": f"spotify:track:{track_id}",
                        "enableCredits": True,
                        "enableRelatedVideos": True,
                    }
                ),
                "extensions": json.dumps(
                    {
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "4ec4ae302c609a517cab6b8868f601cd3457c751c570ab12e988723cc036284f",
                        }
                    }
                ),
            },
        )
        self._check_response(response)
        return response.json()

    def get_track_credits(self, track_id: str) -> dict:
        response = self.session.get(
            self.TRACK_CREDITS_API_URL.format(track_id=track_id)
        )
        self._check_response(response)
        return response.json()
