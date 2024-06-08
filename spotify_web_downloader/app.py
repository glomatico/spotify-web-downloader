import dataclasses
import logging
from pathlib import Path

from .constants import X_NOT_FOUND_STRING
from .downloader import Downloader, DownloadManager
from .downloader_episode import DownloaderEpisode
from .downloader_music_video import DownloaderMusicVideo
from .downloader_song import DownloaderSong
from .enums import RemuxMode, DownloadModeSong, DownloadModeVideo
from .models import Lyrics, DownloadQueueItem
from .spotify_api import SpotifyApi


@dataclasses.dataclass
class ExternalUtilities:
    ffmpeg_path: str
    aria2c_path: str
    nm3u8dlre_path: str
    mp4box_path: str
    mp4decrypt_path: str

@dataclasses.dataclass
class ExceptionTracker:
    error_count: int = 0

    def add(self, exc_value: BaseException = None):
        self.error_count += 1

class App:
    def __init__(self,
                 logger: logging.Logger,
                 spotify_api: SpotifyApi,
                 downloader: Downloader,
                 downloader_song: DownloaderSong,
                 downloader_music_video: DownloaderMusicVideo,
                 downloader_episode: DownloaderEpisode,
                 lrc_only: bool,
                 download_music_video: bool,
                 utilities: ExternalUtilities,
                 ):
        self.logger = logger
        self.spotify_api = spotify_api
        self.downloader = downloader
        self.downloader_song = downloader_song
        self.downloader_music_video = downloader_music_video
        self.downloader_episode = downloader_episode
        self.lrc_only = lrc_only
        self.download_music_video = download_music_video
        self.utilities = utilities

    def setup(self, ):
        wvd_path = self.downloader.wvd_path
        remux_mode = self.downloader.remux_mode
        if not self.spotify_api.is_premium:
            self.logger.warning("Free account detected, lyrics will not be downloaded")
        if not self.lrc_only:
            if wvd_path and not wvd_path.exists():
                self.logger.critical(X_NOT_FOUND_STRING.format(".wvd file", wvd_path))
                return
            self.logger.debug("Setting up CDM")
            self.downloader.set_cdm()
            if not self.downloader.ffmpeg_path_full and remux_mode == RemuxMode.FFMPEG:
                self.logger.critical(X_NOT_FOUND_STRING.format("ffmpeg", self.utilities.ffmpeg_path))
                return
            if (
                    self.downloader_song.download_mode == DownloadModeSong.ARIA2C
                    and not self.downloader.aria2c_path_full
            ):
                self.logger.critical(X_NOT_FOUND_STRING.format("aria2c", self.utilities.aria2c_path))
                return
            if (
                    self.downloader_music_video.download_mode == DownloadModeVideo.NM3U8DLRE
                    and not self.downloader.nm3u8dlre_path_full
            ):
                self.logger.critical(X_NOT_FOUND_STRING.format("nm3u8dlre", self.utilities.nm3u8dlre_path))
                return
            if remux_mode == RemuxMode.MP4BOX:
                if not self.downloader.mp4box_path_full:
                    self.logger.critical(X_NOT_FOUND_STRING.format("MP4Box", self.utilities.mp4box_path))
                    return
                if not self.downloader.mp4decrypt_path_full:
                    self.logger.critical(
                        X_NOT_FOUND_STRING.format("mp4decrypt", self.utilities.mp4decrypt_path)
                    )
                    return
            if not self.spotify_api.is_premium and self.downloader_song.premium_quality:
                self.logger.critical("Cannot download in premium quality with a free account")
                return
            if not self.spotify_api.is_premium and self.download_music_video:
                self.logger.critical("Cannot download music videos with a free account")
                return

    def run(self,
            urls: list[str],
            save_cover: bool,
            overwrite: bool,
            read_urls_as_txt: bool,
            no_lrc: bool,
            print_exceptions: bool,
            ):
        error_tracker = ExceptionTracker()
        if read_urls_as_txt:
            urls = [url.strip() for url in Path(urls[0]).read_text().splitlines()]
        for url_index, url in enumerate(urls, start=1):
            url_progress = f"URL {url_index}/{len(urls)}"
            try:
                url_info = self.downloader.get_url_info(url)
                download_queue = self.downloader.get_download_queue(url_info)
            except Exception as e:
                error_tracker.add(e)
                self.logger.error(
                    f'({url_progress}) Failed to check "{url}"',
                    exc_info=print_exceptions,
                )
                continue
            for queue_index, queue_item in enumerate(download_queue, start=1):
                queue_progress = f"Item {queue_index}/{len(download_queue)} from URL {url_index}/{len(urls)}"
                item_name = queue_item.metadata["name"]
                item_type = queue_item.metadata["type"]
                self.logger.info(f'({queue_progress}) Downloading "{item_name}"')

                with DownloadManager(self.logger, self.downloader, print_exceptions, item_name, on_error=error_tracker.add):
                    if item_type == 'track':
                        self.process_track(queue_progress, queue_item, overwrite, no_lrc, save_cover)
                    elif item_type == 'episode':
                        self.process_episode(queue_progress, queue_item, overwrite, save_cover)
                    else:
                        raise ValueError(f"Unsupported item type to download: {item_type}")

        self.logger.info(f"Done ({error_tracker.error_count} error(s))")

    def process_track(
            self,
            queue_progress: str,
            queue_item: DownloadQueueItem,
            overwrite: bool,
            no_lrc: bool,
            save_cover: bool
    ):
        track = queue_item.metadata
        track_id = track["id"]
        item_type = track['type']
        assert item_type == 'track', "Expected item_type to be 'track' for an queue_item in process_track()"
        self.logger.debug("Getting GID metadata")
        gid = self.spotify_api.track_id_to_gid(track_id)
        metadata_gid = self.spotify_api.get_gid_metadata(type_=item_type, gid=gid)
        if self.download_music_video:
            music_video_id = (
                self.downloader_music_video.get_music_video_id_from_song_id(
                    track_id, queue_item.metadata["artists"][0]["id"]
                )
            )
            if not music_video_id:
                self.logger.warning(
                    f"({queue_progress}) No music video alternative found, skipping"
                )
                return
            metadata_gid = self.spotify_api.get_gid_metadata(
                type_=item_type,
                gid=self.spotify_api.track_id_to_gid(music_video_id)
            )
            self.logger.warning(
                f"({queue_progress}) Switching to download music video "
                f"with title \"{metadata_gid['name']}\""
            )
        if not metadata_gid.get("original_video"):
            if metadata_gid.get("has_lyrics") and self.spotify_api.is_premium:
                self.logger.debug("Getting lyrics")
                lyrics = self.downloader_song.get_lyrics(track_id)
            else:
                lyrics = Lyrics()
            self.logger.debug("Getting album metadata")
            album_metadata = self.spotify_api.get_album(
                self.spotify_api.gid_to_track_id(metadata_gid["album"]["gid"])
            )
            self.logger.debug("Getting track credits")
            track_credits = self.spotify_api.get_track_credits(track_id)
            tags = self.downloader_song.get_tags(
                metadata_gid,
                album_metadata,
                track_credits,
                lyrics.unsynced,
            )
            final_path = self.downloader_song.get_final_path(tags)
            lrc_path = self.downloader_song.get_lrc_path(final_path)
            cover_path = self.downloader_song.get_cover_path(final_path)
            cover_url = self.downloader.get_cover_url(metadata_gid, "LARGE")
            if self.lrc_only:
                pass
            elif final_path.exists() and not overwrite:
                self.logger.warning(
                    f'({queue_progress}) Track already exists at "{final_path}", skipping'
                )
            else:
                self.logger.debug("Getting file info")
                file_id = self.downloader_song.get_file_id(metadata_gid)
                if not file_id:
                    self.logger.error(
                        f"({queue_progress}) Track not available on Spotify's "
                        "servers and no alternative found, skipping"
                    )
                    return
                self.logger.debug("Getting PSSH")
                pssh = self.spotify_api.get_pssh(file_id)
                self.logger.debug("Getting decryption key")
                decryption_key = self.downloader_song.get_decryption_key(pssh)
                self.logger.debug("Getting stream URL")
                stream_url = self.spotify_api.get_stream_url(file_id)
                encrypted_path = self.downloader.get_encrypted_path(track_id, ".m4a")
                decrypted_path = self.downloader.get_decrypted_path(track_id, ".m4a")
                self.logger.debug(f'Downloading to "{encrypted_path}"')
                self.downloader_song.download(encrypted_path, stream_url)
                remuxed_path = self.downloader.get_remuxed_path(track_id, ".m4a")
                self.logger.debug(f'Decrypting/Remuxing to "{remuxed_path}"')
                self.downloader_song.remux(
                    encrypted_path,
                    decrypted_path,
                    remuxed_path,
                    decryption_key,
                )
                self.logger.debug("Applying tags")
                self.downloader.apply_tags(remuxed_path, tags, cover_url)
                self.logger.debug(f'Moving to "{final_path}"')
                self.downloader.move_to_final_path(remuxed_path, final_path)
            if no_lrc or not lyrics.synced:
                pass
            elif lrc_path.exists() and not overwrite:
                self.logger.debug(
                    f'Synced lyrics already exists at "{lrc_path}", skipping'
                )
            else:
                self.logger.debug(f'Saving synced lyrics to "{lrc_path}"')
                self.downloader_song.save_lrc(lrc_path, lyrics.synced)
            if self.lrc_only or not save_cover:
                pass
            elif cover_path.exists() and not overwrite:
                self.logger.debug(
                    f'Cover already exists at "{cover_path}", skipping'
                )
            else:
                self.logger.debug(f'Saving cover to "{cover_path}"')
                self.downloader.save_cover(cover_path, cover_url)
        elif not self.spotify_api.is_premium:
            self.logger.error(
                f"({queue_progress}) Cannot download music videos with a free account, skipping"
            )
        elif self.lrc_only:
            self.logger.warning(
                f"({queue_progress}) Music videos are not downloadable with "
                "current settings, skipping"
            )
        else:
            cover_url = self.downloader.get_cover_url(metadata_gid, "XXLARGE")
            self.logger.debug("Getting album metadata")
            album_metadata = self.spotify_api.get_album(
                self.spotify_api.gid_to_track_id(metadata_gid["album"]["gid"])
            )
            self.logger.debug("Getting track credits")
            track_credits = self.spotify_api.get_track_credits(track_id)
            tags = self.downloader_music_video.get_tags(
                metadata_gid,
                album_metadata,
                track_credits,
            )
            final_path = self.downloader_music_video.get_final_path(tags)
            cover_path = self.downloader_music_video.get_cover_path(final_path)
            if final_path.exists() and not overwrite:
                self.logger.warning(
                    f'({queue_progress}) Music video already exists at "{final_path}", skipping'
                )
            else:
                self.logger.debug("Getting video manifest")
                manifest = self.downloader_music_video.get_manifest(metadata_gid)
                stream_info = self.downloader_music_video.get_video_stream_info(
                    manifest
                )
                self.logger.debug("Getting decryption key")
                decryption_key = self.downloader_music_video.get_decryption_key(
                    stream_info.pssh
                )
                m3u8 = self.downloader_music_video.get_m3u8(
                    stream_info.base_url,
                    stream_info.initialization_template_url,
                    stream_info.segment_template_url,
                    stream_info.end_time_millis,
                    stream_info.segment_length,
                    stream_info.profile_id_video,
                    stream_info.profile_id_audio,
                    stream_info.file_type_video,
                    stream_info.file_type_audio,
                )
                m3u8_path_video = self.downloader_music_video.get_m3u8_path(
                    track_id, "video"
                )
                encrypted_path_video = self.downloader.get_encrypted_path(
                    track_id, "_video.ts"
                )
                decrypted_path_video = self.downloader.get_decrypted_path(
                    track_id, "_video.ts"
                )
                self.logger.debug(f'Downloading video to "{encrypted_path_video}"')
                self.downloader_music_video.save_m3u8(m3u8.video, m3u8_path_video)
                self.downloader_music_video.download(
                    m3u8_path_video,
                    encrypted_path_video,
                )
                m3u8_path_audio = self.downloader_music_video.get_m3u8_path(
                    track_id, "audio"
                )
                encrypted_path_audio = self.downloader.get_encrypted_path(
                    track_id, "_audio.ts"
                )
                decrypted_path_audio = self.downloader.get_decrypted_path(
                    track_id, "_audio.ts"
                )
                self.logger.debug(f"Downloading audio to {encrypted_path_audio}")
                self.downloader_music_video.save_m3u8(m3u8.audio, m3u8_path_audio)
                self.downloader_music_video.download(
                    m3u8_path_audio,
                    encrypted_path_audio,
                )
                remuxed_path = self.downloader.get_remuxed_path(track_id, ".m4v")
                self.logger.debug(f'Decrypting/Remuxing to "{remuxed_path}"')
                self.downloader_music_video.remux(
                    decryption_key,
                    encrypted_path_video,
                    encrypted_path_audio,
                    decrypted_path_video,
                    decrypted_path_audio,
                    remuxed_path,
                )
                self.logger.debug("Applying tags")
                self.downloader.apply_tags(remuxed_path, tags, cover_url)
                self.logger.debug(f'Moving to "{final_path}"')
                self.downloader.move_to_final_path(remuxed_path, final_path)
            if save_cover:
                cover_path = self.downloader_music_video.get_cover_path(final_path)
                if cover_path.exists() and not overwrite:
                    self.logger.debug(
                        f'Cover already exists at "{cover_path}", skipping'
                    )
                else:
                    self.logger.debug(f'Saving cover to "{cover_path}"')
                    self.downloader.save_cover(cover_path, cover_url)

    def process_episode(
            self,
            queue_progress: str,
            queue_item: DownloadQueueItem,
            overwrite: bool,
            save_cover: bool
    ):
        episode = queue_item.metadata
        episode_id = episode["id"]
        item_type = episode['type']
        assert item_type == 'episode', "Expected item_type to be 'episode' for an queue_item in process_episode()"
        self.logger.debug("Getting GID metadata")
        gid = self.spotify_api.track_id_to_gid(episode_id)
        metadata_gid = self.spotify_api.get_gid_metadata(type_=item_type, gid=gid)
        if self.download_music_video:
            self.logger.warning(
                f"({queue_progress}) Ignoring download-music-video option for episode downloads "
            )
        if not metadata_gid.get("original_video"):
            self.logger.debug("Getting album metadata")
            show_metadata = self.spotify_api.get_show(
                self.spotify_api.gid_to_track_id(metadata_gid["show"]["gid"])
            )
            self.logger.debug("Getting episode credits")
            tags = self.downloader_episode.get_tags(
                metadata_gid,
                show_metadata,
            )
            final_path = self.downloader_episode.get_final_path(tags)
            cover_path = self.downloader_episode.get_cover_path(final_path)
            cover_url = self.downloader_episode.get_cover_url(metadata_gid, "LARGE")
            if self.lrc_only:
                pass
            elif final_path.exists() and not overwrite:
                self.logger.warning(
                    f'({queue_progress}) Track already exists at "{final_path}", skipping'
                )
            else:
                self.logger.debug("Getting file info")
                file_id = self.downloader_episode.get_file_id(metadata_gid)
                if not file_id:
                    self.logger.error(
                        f"({queue_progress}) Item not available on Spotify's "
                        "servers, skipping"
                    )
                    return
                self.logger.debug("Getting PSSH")
                pssh = self.spotify_api.get_pssh(file_id)
                self.logger.debug("Getting decryption key")
                decryption_key = self.downloader_episode.get_decryption_key(pssh)
                self.logger.debug("Getting stream URL")
                stream_url = self.spotify_api.get_stream_url(file_id)
                encrypted_path = self.downloader.get_encrypted_path(episode_id, ".m4a")
                decrypted_path = self.downloader.get_decrypted_path(episode_id, ".m4a")
                self.logger.debug(f'Downloading to "{encrypted_path}"')
                self.downloader_episode.download(encrypted_path, stream_url)
                remuxed_path = self.downloader.get_remuxed_path(episode_id, ".m4a")
                self.logger.debug(f'Decrypting/Remuxing to "{remuxed_path}"')
                self.downloader_episode.remux(
                    encrypted_path,
                    decrypted_path,
                    remuxed_path,
                    decryption_key,
                )
                self.logger.debug("Applying tags")
                self.downloader.apply_tags(remuxed_path, tags, cover_url)
                self.logger.debug(f'Moving to "{final_path}"')
                self.downloader.move_to_final_path(remuxed_path, final_path)
            if self.lrc_only or not save_cover:
                pass
            elif cover_path.exists() and not overwrite:
                self.logger.debug(
                    f'Cover already exists at "{cover_path}", skipping'
                )
            else:
                self.logger.debug(f'Saving cover to "{cover_path}"')
                self.downloader.save_cover(cover_path, cover_url)
        else:
            self.logger.warning(
                f"({queue_progress}) Music videos are not downloadable for episodes"
            )

