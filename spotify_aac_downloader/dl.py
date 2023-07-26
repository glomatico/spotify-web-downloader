import datetime
import functools
import glob
import re
import shutil
import subprocess
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import base62
import requests
from mutagen.mp4 import MP4, MP4Cover
from pywidevine import PSSH, Cdm, Device
from yt_dlp import YoutubeDL


class Dl:
    def __init__(
        self,
        final_path,
        cookies_location,
        temp_path,
        wvd_location,
        premium_quality,
        overwrite,
        lrc_only,
    ):
        self.temp_path = Path(temp_path)
        self.final_path = Path(final_path)
        self.overwrite = overwrite
        if premium_quality:
            self.audio_quality = "MP4_256"
        else:
            self.audio_quality = "MP4_128"
        if not lrc_only:
            wvd_location = glob.glob(wvd_location)
            if not wvd_location:
                raise Exception(".wvd file not found")
            self.cdm = Cdm.from_device(Device.load(wvd_location[0]))
            self.cdm_session = self.cdm.open()
        cookies = MozillaCookieJar(cookies_location)
        cookies.load(ignore_discard=True, ignore_expires=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "app-platform": "WebPlayer",
                "accept": "application/json",
                "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6,zh;q=0.5,ru;q=0.4,es;q=0.3,ja;q=0.2",
                "content-type": "application/json",
                "origin": "https://open.spotify.com",
                "referer": "https://open.spotify.com/",
                "sec-ch-ua": '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            }
        )
        self.session.cookies.update(cookies)
        web_page = self.session.get("https://open.spotify.com/").text
        token = re.search(r'accessToken":"(.*?)"', web_page).group(1)
        self.session.headers.update(
            {
                "authorization": f"Bearer {token}",
            }
        )

    def get_download_queue(self, url):
        uri = url.split("/")[-1].split("?")[0]
        download_queue = []
        if "album" in url:
            download_queue.extend(self.get_album(uri)["tracks"]["items"])
        elif "track" in url:
            download_queue.append(self.get_track(uri))
        elif "playlist" in url:
            download_queue.extend(
                [i["track"] for i in self.get_playlist(uri)["tracks"]["items"]]
            )
        else:
            raise Exception("Not a valid Spotify URL")
        return download_queue

    def uri_to_gid(self, uri):
        return hex(base62.decode(uri, base62.CHARSET_INVERTED))[2:].zfill(32)

    def gid_to_uri(self, gid):
        return base62.encode(int(gid, 16), charset=base62.CHARSET_INVERTED).zfill(22)

    def get_track(self, track_id):
        return self.session.get(f"https://api.spotify.com/v1/tracks/{track_id}").json()

    @functools.lru_cache()
    def get_album(self, album_id):
        album = self.session.get(f"https://api.spotify.com/v1/albums/{album_id}").json()
        album_next_url = album["tracks"]["next"]
        while album_next_url is not None:
            album_next = self.session.get(album_next_url).json()
            album["tracks"]["items"].extend(album_next["items"])
            album_next_url = album_next["next"]
        return album

    def get_playlist(self, playlist_id):
        playlist = self.session.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}"
        ).json()
        playlist_next_url = playlist["tracks"]["next"]
        while playlist_next_url is not None:
            playlist_next = self.session.get(playlist_next_url).json()
            playlist["tracks"]["items"].extend(playlist_next["items"])
            playlist_next_url = playlist_next["next"]
        return playlist

    def get_metadata(self, gid):
        return self.session.get(
            f"https://spclient.wg.spotify.com/metadata/4/track/{gid}?market=from_token"
        ).json()

    def get_file_id(self, metadata):
        audio_files = metadata.get("file")
        # If the main metadata does not directly contain the audio files but the alternative may, try that instead
        if audio_files is None:
            audio_files = metadata["alternative"][0]["file"]
        return next(
            i["file_id"] for i in audio_files if i["format"] == self.audio_quality
        )

    def get_pssh(self, file_id):
        return self.session.get(
            f"https://seektables.scdn.co/seektable/{file_id}.json"
        ).json()["pssh"]

    def get_decryption_key(self, pssh):
        pssh = PSSH(pssh)
        challenge = self.cdm.get_license_challenge(self.cdm_session, pssh)
        license = self.session.post(
            "https://gue1-spclient.spotify.com/widevine-license/v1/audio/license",
            challenge,
        ).content
        self.cdm.parse_license(self.cdm_session, license)
        return next(
            i for i in self.cdm.get_keys(self.cdm_session) if i.type == "CONTENT"
        ).key.hex()

    def get_stream_url(self, file_id):
        return self.session.get(
            f"https://gue1-spclient.spotify.com/storage-resolve/v2/files/audio/interactive/11/{file_id}?version=10000000&product=9&platform=39&alt=json",
        ).json()["cdnurl"][0]

    def get_artist(self, artist_list):
        if len(artist_list) == 1:
            return artist_list[0]["name"]
        return (
            ", ".join(i["name"] for i in artist_list[:-1])
            + f' & {artist_list[-1]["name"]}'
        )

    def get_synced_lyrics_formated_time(self, time):
        formated_time = datetime.datetime.fromtimestamp(time / 1000.0)
        return formated_time.strftime("%M:%S.%f")[:-4]

    def get_lyrics(self, track_id):
        try:
            raw_lyrics = self.session.get(
                f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}"
            ).json()["lyrics"]
        except:
            return None, None
        synced_lyrics = ""
        unsynced_lyrics = ""
        for line in raw_lyrics["lines"]:
            if raw_lyrics["syncType"] == "LINE_SYNCED":
                synced_lyrics += f'[{self.get_synced_lyrics_formated_time(int(line["startTimeMs"]))}]{line["words"]}\n'
            unsynced_lyrics += f'{line["words"]}\n'
        return unsynced_lyrics[:-1], synced_lyrics

    @functools.lru_cache()
    def get_cover(self, url):
        return requests.get(url).content

    def get_tags(self, metadata, unsynced_lyrics):
        album = self.get_album(self.gid_to_uri(metadata["album"]["gid"]))
        copyright = next(i["text"] for i in album["copyrights"] if i["type"] == "P")
        if album["release_date_precision"] == "year":
            release_date = album["release_date"] + "-01-01"
        else:
            release_date = album["release_date"]
        total_tracks = [
            i["track_number"]
            for i in album["tracks"]["items"]
            if i["disc_number"] == metadata["disc_number"]
        ][-1]
        total_discs = album["tracks"]["items"][-1]["disc_number"]
        tags = {
            "\xa9nam": [metadata["name"]],
            "\xa9ART": [self.get_artist(metadata["artist"])],
            "aART": [self.get_artist(metadata["album"]["artist"])],
            "\xa9alb": [metadata["album"]["name"]],
            "trkn": [(metadata["number"], total_tracks)],
            "disk": [(metadata["disc_number"], total_discs)],
            "\xa9day": [f"{release_date}T00:00:00Z"],
            "covr": [
                MP4Cover(
                    self.get_cover(
                        "https://i.scdn.co/image/"
                        + next(
                            i["file_id"]
                            for i in metadata["album"]["cover_group"]["image"]
                            if i["size"] == "LARGE"
                        )
                    )
                )
            ],
            "\xa9cmt": [
                f'https://open.spotify.com/track/{metadata["canonical_uri"].split(":")[-1]}'
            ],
            "cprt": [copyright],
            "rtng": [1] if "explicit" in metadata else [0],
        }
        if unsynced_lyrics is not None:
            tags["\xa9lyr"] = [unsynced_lyrics]
        return tags

    def get_sanizated_string(self, dirty_string, is_folder):
        dirty_string = re.sub(r'[\\/:\*\?"<>\|;]', "_", dirty_string)
        if is_folder:
            dirty_string = dirty_string[:40]
            if dirty_string.endswith("."):
                dirty_string = dirty_string[:-1] + "_"
        else:
            dirty_string = dirty_string[:36]
        return dirty_string.strip()

    def get_encrypted_location(self, track_id):
        return self.temp_path / f"{track_id}_encrypted.mp4"

    def get_fixed_location(self, track_id):
        return self.temp_path / f"{track_id}_fixed.m4a"

    def get_final_location(self, tags):
        if tags["disk"][0][1] > 1:
            file_name = self.get_sanizated_string(
                f'{tags["disk"][0][0]}-{tags["trkn"][0][0]:02d} {tags["©nam"][0]}',
                False,
            )
        else:
            file_name = self.get_sanizated_string(
                f'{tags["trkn"][0][0]:02d} {tags["©nam"][0]}', False
            )
        return (
            self.final_path
            / self.get_sanizated_string(tags["aART"][0], True)
            / self.get_sanizated_string(tags["\xa9alb"][0], True)
            / (file_name + ".m4a")
        )

    def download(self, encrypted_location, stream_url):
        with YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "outtmpl": str(encrypted_location),
                "allow_unplayable_formats": True,
                "fixup": "never",
                "overwrites": self.overwrite,
            }
        ) as ydl:
            ydl.download(stream_url)

    def fixup(self, decryption_key, encrypted_location, fixed_location):
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-decryption_key",
                decryption_key,
                "-i",
                encrypted_location,
                "-movflags",
                "+faststart",
                "-c",
                "copy",
                fixed_location,
            ],
            check=True,
        )

    def make_final(self, fixed_location, final_location, tags):
        file = MP4(fixed_location)
        file.clear()
        file.update(tags)
        file.save()
        shutil.move(fixed_location, final_location)

    def make_lrc(self, final_location, synced_lyrics):
        if synced_lyrics:
            with open(final_location.with_suffix(".lrc"), "w", encoding="utf8") as f:
                f.write(synced_lyrics)

    def cleanup(self):
        if self.temp_path.exists():
            shutil.rmtree(self.temp_path)
