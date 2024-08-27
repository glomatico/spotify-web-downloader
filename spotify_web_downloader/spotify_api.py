from __future__ import annotations

import functools
import json
import re
import time
import typing
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import base62
import requests

from .utils import check_response


class SpotifyApi:
    SPOTIFY_HOME_PAGE_URL = "https://open.spotify.com/"
    CLIENT_VERSION = "1.2.46.25.g7f189073"
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
        cookies_path: Path | None = Path("./cookies.txt"),
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
                "accept": "application/json",
                "accept-language": "en-US",
                "content-type": "application/json",
                "origin": self.SPOTIFY_HOME_PAGE_URL,
                "priority": "u=1, i",
                "referer": self.SPOTIFY_HOME_PAGE_URL,
                "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "spotify-app-version": self.CLIENT_VERSION,
                "app-platform": "WebPlayer",
            }
        )
        home_page = self.get_home_page(self.session.cookies.get("sp_dc"))
        self.session_info = json.loads(
            re.search(
                r'<script id="session" data-testid="session" type="application/json">(.+?)</script>',
                home_page,
            ).group(1)
        )
        self.config_info = json.loads(
            re.search(
                r'<script id="config" data-testid="config" type="application/json">(.+?)</script>',
                home_page,
            ).group(1)
        )
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.session_info['accessToken']}",
            }
        )

    @staticmethod
    def track_id_to_gid(track_id: str) -> str:
        return hex(base62.decode(track_id, base62.CHARSET_INVERTED))[2:].zfill(32)

    @staticmethod
    def gid_to_track_id(gid: str) -> str:
        return base62.encode(int(gid, 16), charset=base62.CHARSET_INVERTED).zfill(22)

    def get_gid_metadata(self, gid: str) -> dict:
        response = self.session.get(self.GID_METADATA_API_URL.format(gid=gid))
        check_response(response)
        return response.json()

    def get_video_manifest(self, gid: str) -> dict:
        response = self.session.get(self.VIDEO_MANIFEST_API_URL.format(gid=gid))
        check_response(response)
        return response.json()

    def get_widevine_license_music(self, challenge: bytes) -> bytes:
        response = self.session.post(
            self.WIDEVINE_LICENSE_API_URL.format(type="audio"),
            challenge,
        )
        check_response(response)
        return response.content

    def get_widevine_license_video(self, challenge: bytes) -> bytes:
        response = self.session.post(
            self.WIDEVINE_LICENSE_API_URL.format(type="video"),
            challenge,
        )
        check_response(response)
        return response.content

    def get_lyrics(self, track_id: str) -> dict | None:
        response = self.session.get(self.LYRICS_API_URL.format(track_id=track_id))
        if response.status_code == 404:
            return None
        check_response(response)
        return response.json()

    def get_pssh(self, file_id: str) -> str:
        response = requests.get(self.PSSH_API_URL.format(file_id=file_id))
        check_response(response)
        return response.json()["pssh"]

    def get_stream_url(self, file_id: str) -> str:
        response = self.session.get(self.STREAM_URL_API_URL.format(file_id=file_id))
        check_response(response)
        return response.json()["cdnurl"][0]

    def get_track(self, track_id: str) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="tracks", track_id=track_id)
        )
        check_response(response)
        return response.json()

    def extend_track_collection(
        self,
        track_collection: dict,
    ) -> typing.Generator[dict, None, None]:
        next_url = track_collection["tracks"]["next"]
        while next_url is not None:
            response = self.session.get(next_url)
            check_response(response)
            extended_collection = response.json()
            yield extended_collection
            next_url = extended_collection["next"]
            time.sleep(self.EXTEND_TRACK_COLLECTION_WAIT_TIME)

    @functools.lru_cache()
    def get_album(
        self,
        album_id: str,
        extend: bool = True,
    ) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="albums", track_id=album_id)
        )
        check_response(response)
        album = response.json()
        if extend:
            album["tracks"]["items"].extend(
                [
                    item
                    for extended_collection in self.extend_track_collection(album)
                    for item in extended_collection["items"]
                ]
            )
        return album

    def get_playlist(
        self,
        playlist_id: str,
        extend: bool = True,
    ) -> dict:
        response = self.session.get(
            self.METADATA_API_URL.format(type="playlists", track_id=playlist_id)
        )
        check_response(response)
        playlist = response.json()
        if extend:
            playlist["tracks"]["items"].extend(
                [
                    item
                    for extended_collection in self.extend_track_collection(playlist)
                    for item in extended_collection["items"]
                ]
            )
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
        check_response(response)
        return response.json()

    def get_track_credits(self, track_id: str) -> dict:
        response = self.session.get(
            self.TRACK_CREDITS_API_URL.format(track_id=track_id)
        )
        check_response(response)
        return response.json()

    @staticmethod
    def get_home_page(sp_dc: str = None) -> str:
        cookies = {"sp_dc": sp_dc} if sp_dc else None
        response = requests.get(
            SpotifyApi.SPOTIFY_HOME_PAGE_URL,
            cookies=cookies,
        )
        check_response(response)
        return response.text
