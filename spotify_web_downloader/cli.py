from __future__ import annotations

import inspect
import json
import logging
from enum import Enum
from pathlib import Path

import click

from . import __version__
from .constants import *
from .downloader import Downloader
from .downloader_music_video import DownloaderMusicVideo
from .downloader_song import DownloaderSong
from .enums import DownloadModeSong, DownloadModeVideo, RemuxMode
from .models import Lyrics
from .spotify_api import SpotifyApi

spotify_api_sig = inspect.signature(SpotifyApi.__init__)
downloader_sig = inspect.signature(Downloader.__init__)
downloader_song_sig = inspect.signature(DownloaderSong.__init__)
downloader_music_video_sig = inspect.signature(DownloaderMusicVideo.__init__)


def get_param_string(param: click.Parameter) -> str:
    if isinstance(param.default, Enum):
        return param.default.value
    elif isinstance(param.default, Path):
        return str(param.default)
    else:
        return param.default


def write_default_config_file(ctx: click.Context) -> None:
    ctx.params["config_path"].parent.mkdir(parents=True, exist_ok=True)
    config_file = {
        param.name: get_param_string(param)
        for param in ctx.command.params
        if param.name not in EXCLUDED_CONFIG_FILE_PARAMS
    }
    ctx.params["config_path"].write_text(json.dumps(config_file, indent=4))


def load_config_file(
    ctx: click.Context,
    param: click.Parameter,
    no_config_file: bool,
) -> click.Context:
    if no_config_file:
        return ctx
    if not ctx.params["config_path"].exists():
        write_default_config_file(ctx)
    config_file = dict(json.loads(ctx.params["config_path"].read_text()))
    for param in ctx.command.params:
        if (
            config_file.get(param.name) is not None
            and not ctx.get_parameter_source(param.name)
            == click.core.ParameterSource.COMMANDLINE
        ):
            ctx.params[param.name] = param.type_cast_value(ctx, config_file[param.name])
    return ctx


@click.command()
@click.help_option("-h", "--help")
@click.version_option(__version__, "-v", "--version")
# CLI specific options
@click.argument(
    "urls",
    nargs=-1,
    type=str,
    required=True,
)
@click.option(
    "--download-music-video",
    is_flag=True,
    help="Attempt to download music videos from songs (can lead to incorrect results).",
)
@click.option(
    "--save-cover",
    "-s",
    is_flag=True,
    help="Save cover as a separate file.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Overwrite existing files.",
)
@click.option(
    "--read-urls-as-txt",
    "-r",
    is_flag=True,
    help="Interpret URLs as paths to text files containing URLs.",
)
@click.option(
    "--lrc-only",
    "-l",
    is_flag=True,
    help="Download only the synced lyrics.",
)
@click.option(
    "--no-lrc",
    is_flag=True,
    help="Don't download the synced lyrics.",
)
@click.option(
    "--config-path",
    type=Path,
    default=Path.home() / ".spotify-web-downloader" / "config.json",
    help="Path to config file.",
)
@click.option(
    "--log-level",
    type=str,
    default="INFO",
    help="Log level.",
)
@click.option(
    "--print-exceptions",
    is_flag=True,
    help="Print exceptions.",
)
# API specific options
@click.option(
    "--cookies-path",
    "-c",
    type=Path,
    default=spotify_api_sig.parameters["cookies_path"].default,
    help="Path to .txt cookies file.",
)
# Downloader specific options
@click.option(
    "--output-path",
    "-o",
    type=Path,
    default=downloader_sig.parameters["output_path"].default,
    help="Path to output directory.",
)
@click.option(
    "--temp-path",
    type=Path,
    default=downloader_sig.parameters["temp_path"].default,
    help="Path to temporary directory.",
)
@click.option(
    "--wvd-path",
    type=Path,
    default=downloader_sig.parameters["wvd_path"].default,
    help="Path to .wvd file.",
)
@click.option(
    "--ffmpeg-path",
    type=str,
    default=downloader_sig.parameters["ffmpeg_path"].default,
    help="Path to FFmpeg binary.",
)
@click.option(
    "--mp4box-path",
    type=str,
    default=downloader_sig.parameters["mp4box_path"].default,
    help="Path to MP4Box binary.",
)
@click.option(
    "--mp4decrypt-path",
    type=str,
    default=downloader_sig.parameters["mp4decrypt_path"].default,
    help="Path to mp4decrypt binary.",
)
@click.option(
    "--aria2c-path",
    type=str,
    default=downloader_sig.parameters["aria2c_path"].default,
    help="Path to aria2c binary.",
)
@click.option(
    "--nm3u8dlre-path",
    type=str,
    default=downloader_sig.parameters["nm3u8dlre_path"].default,
    help="Path to N_m3u8DL-RE binary.",
)
@click.option(
    "--remux-mode",
    type=RemuxMode,
    default=downloader_sig.parameters["remux_mode"].default,
    help="Remux mode.",
)
@click.option(
    "--date-tag-template",
    type=str,
    default=downloader_sig.parameters["date_tag_template"].default,
    help="Date tag template.",
)
@click.option(
    "--exclude-tags",
    type=str,
    default=downloader_sig.parameters["exclude_tags"].default,
    help="Comma-separated tags to exclude.",
)
@click.option(
    "--truncate",
    type=int,
    default=downloader_sig.parameters["truncate"].default,
    help="Maximum length of the file/folder names.",
)
# DownloaderSong specific options
@click.option(
    "--template-folder-album",
    type=str,
    default=downloader_song_sig.parameters["template_folder_album"].default,
    help="Template of the album folders as a format string.",
)
@click.option(
    "--template-folder-compilation",
    type=str,
    default=downloader_song_sig.parameters["template_folder_compilation"].default,
    help="Template of the compilation album folders as a format string.",
)
@click.option(
    "--template-file-single-disc",
    type=str,
    default=downloader_song_sig.parameters["template_file_single_disc"].default,
    help="Template of the song files for single-disc albums as a format string.",
)
@click.option(
    "--template-file-multi-disc",
    type=str,
    default=downloader_song_sig.parameters["template_file_multi_disc"].default,
    help="Template of the song files for multi-disc albums as a format string.",
)
@click.option(
    "--download-mode-song",
    type=DownloadModeSong,
    default=downloader_song_sig.parameters["download_mode"].default,
    help="Download mode for songs.",
)
@click.option(
    "--premium-quality",
    "-p",
    is_flag=True,
    default=downloader_song_sig.parameters["premium_quality"].default,
    help="Download songs in premium quality.",
)
# DownloaderMusicVideo specific options
@click.option(
    "--template-folder-music-video",
    type=str,
    default=downloader_music_video_sig.parameters["template_folder"].default,
    help="Template of the music video folders as a format string.",
)
@click.option(
    "--template-file-music-video",
    type=str,
    default=downloader_music_video_sig.parameters["template_file"].default,
    help="Template of the music video files as a format string.",
)
@click.option(
    "--download-mode-video",
    type=DownloadModeVideo,
    default=downloader_music_video_sig.parameters["download_mode"].default,
    help="Download mode for videos.",
)
# This option should always be last
@click.option(
    "--no-config-file",
    "-n",
    is_flag=True,
    callback=load_config_file,
    help="Do not use a config file.",
)
def main(
    urls: list[str],
    download_music_video: bool,
    save_cover: bool,
    overwrite: bool,
    read_urls_as_txt: bool,
    lrc_only: bool,
    no_lrc: bool,
    config_path: Path,
    log_level: str,
    print_exceptions: bool,
    cookies_path: Path,
    output_path: Path,
    temp_path: Path,
    wvd_path: Path,
    ffmpeg_path: str,
    mp4box_path: str,
    mp4decrypt_path: str,
    aria2c_path: str,
    nm3u8dlre_path: str,
    remux_mode: RemuxMode,
    date_tag_template: str,
    exclude_tags: str,
    truncate: int,
    template_folder_album: str,
    template_folder_compilation: str,
    template_file_single_disc: str,
    template_file_multi_disc: str,
    download_mode_song: DownloadModeSong,
    premium_quality: bool,
    template_folder_music_video: str,
    template_file_music_video: str,
    download_mode_video: DownloadModeVideo,
    no_config_file: bool,
) -> None:
    logging.basicConfig(
        format="[%(levelname)-8s %(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    logger.debug("Starting downloader")
    if not cookies_path.exists():
        logger.critical(X_NOT_FOUND_STRING.format("Cookies file", cookies_path))
        return
    spotify_api = SpotifyApi(cookies_path)
    downloader = Downloader(
        spotify_api,
        output_path,
        temp_path,
        wvd_path,
        ffmpeg_path,
        mp4box_path,
        mp4decrypt_path,
        aria2c_path,
        nm3u8dlre_path,
        remux_mode,
        date_tag_template,
        exclude_tags,
        truncate,
    )
    downloader_song = DownloaderSong(
        downloader,
        template_folder_album,
        template_folder_compilation,
        template_file_single_disc,
        template_file_multi_disc,
        download_mode_song,
        premium_quality,
    )
    downloader_music_video = DownloaderMusicVideo(
        downloader,
        template_folder_music_video,
        template_file_music_video,
        download_mode_video,
    )
    if not spotify_api.is_premium:
        logger.warning("Free account detected, lyrics will not be downloaded")
    if not lrc_only:
        if wvd_path and not wvd_path.exists():
            logger.critical(X_NOT_FOUND_STRING.format(".wvd file", wvd_path))
            return
        logger.debug("Setting up CDM")
        downloader.set_cdm()
        if not downloader.ffmpeg_path_full and remux_mode == RemuxMode.FFMPEG:
            logger.critical(X_NOT_FOUND_STRING.format("ffmpeg", ffmpeg_path))
            return
        if (
            download_mode_song == DownloadModeSong.ARIA2C
            and not downloader.aria2c_path_full
        ):
            logger.critical(X_NOT_FOUND_STRING.format("aria2c", aria2c_path))
            return
        if (
            download_mode_video == DownloadModeVideo.NM3U8DLRE
            and not downloader.nm3u8dlre_path_full
        ):
            logger.critical(X_NOT_FOUND_STRING.format("nm3u8dlre", nm3u8dlre_path))
            return
        if remux_mode == RemuxMode.MP4BOX:
            if not downloader.mp4box_path_full:
                logger.critical(X_NOT_FOUND_STRING.format("MP4Box", mp4box_path))
                return
            if not downloader.mp4decrypt_path_full:
                logger.critical(
                    X_NOT_FOUND_STRING.format("mp4decrypt", mp4decrypt_path)
                )
                return
        if not spotify_api.is_premium and premium_quality:
            logger.critical("Cannot download in premium quality with a free account")
            return
        if not spotify_api.is_premium and download_music_video:
            logger.critical("Cannot download music videos with a free account")
            return
    error_count = 0
    if read_urls_as_txt:
        urls = [url.strip() for url in Path(urls[0]).read_text().splitlines()]
    for url_index, url in enumerate(urls, start=1):
        url_progress = f"URL {url_index}/{len(urls)}"
        try:
            url_info = downloader.get_url_info(url)
            download_queue = downloader.get_download_queue(url_info)
        except Exception as e:
            error_count += 1
            logger.error(
                f'({url_progress}) Failed to check "{url}"',
                exc_info=print_exceptions,
            )
            continue
        for queue_index, queue_item in enumerate(download_queue, start=1):
            queue_progress = f"Track {queue_index}/{len(download_queue)} from URL {url_index}/{len(urls)}"
            track = queue_item.metadata
            try:
                logger.info(f'({queue_progress}) Downloading "{track["name"]}"')
                track_id = track["id"]
                logger.debug("Getting GID metadata")
                gid = spotify_api.track_id_to_gid(track_id)
                metadata_gid = spotify_api.get_gid_metadata(gid)
                if download_music_video:
                    music_video_id = (
                        downloader_music_video.get_music_video_id_from_song_id(
                            track_id, queue_item.metadata["artists"][0]["id"]
                        )
                    )
                    if not music_video_id:
                        logger.warning(
                            f"({queue_progress}) No music video alternative found, skipping"
                        )
                        continue
                    metadata_gid = spotify_api.get_gid_metadata(
                        spotify_api.track_id_to_gid(music_video_id)
                    )
                    logger.warning(
                        f"({queue_progress}) Switching to download music video "
                        f"with title \"{metadata_gid['name']}\""
                    )
                if not metadata_gid.get("original_video"):
                    if metadata_gid.get("has_lyrics") and spotify_api.is_premium:
                        logger.debug("Getting lyrics")
                        lyrics = downloader_song.get_lyrics(track_id)
                    else:
                        lyrics = Lyrics()
                    logger.debug("Getting album metadata")
                    album_metadata = spotify_api.get_album(
                        spotify_api.gid_to_track_id(metadata_gid["album"]["gid"])
                    )
                    logger.debug("Getting track credits")
                    track_credits = spotify_api.get_track_credits(track_id)
                    tags = downloader_song.get_tags(
                        metadata_gid,
                        album_metadata,
                        track_credits,
                        lyrics.unsynced,
                    )
                    final_path = downloader_song.get_final_path(tags)
                    lrc_path = downloader_song.get_lrc_path(final_path)
                    cover_path = downloader_song.get_cover_path(final_path)
                    cover_url = downloader.get_cover_url(metadata_gid, "LARGE")
                    if lrc_only:
                        pass
                    elif final_path.exists() and not overwrite:
                        logger.warning(
                            f'({queue_progress}) Track already exists at "{final_path}", skipping'
                        )
                    else:
                        logger.debug("Getting file info")
                        file_id = downloader_song.get_file_id(metadata_gid)
                        if not file_id:
                            logger.error(
                                f"({queue_progress}) Track not available on Spotify's "
                                "servers and no alternative found, skipping"
                            )
                            continue
                        logger.debug("Getting PSSH")
                        pssh = spotify_api.get_pssh(file_id)
                        logger.debug("Getting decryption key")
                        decryption_key = downloader_song.get_decryption_key(pssh)
                        logger.debug("Getting stream URL")
                        stream_url = spotify_api.get_stream_url(file_id)
                        encrypted_path = downloader.get_encrypted_path(track_id, ".m4a")
                        decrypted_path = downloader.get_decrypted_path(track_id, ".m4a")
                        logger.debug(f'Downloading to "{encrypted_path}"')
                        downloader_song.download(encrypted_path, stream_url)
                        remuxed_path = downloader.get_remuxed_path(track_id, ".m4a")
                        logger.debug(f'Decrypting/Remuxing to "{remuxed_path}"')
                        downloader_song.remux(
                            encrypted_path,
                            decrypted_path,
                            remuxed_path,
                            decryption_key,
                        )
                        logger.debug("Applying tags")
                        downloader.apply_tags(remuxed_path, tags, cover_url)
                        logger.debug(f'Moving to "{final_path}"')
                        downloader.move_to_final_path(remuxed_path, final_path)
                    if no_lrc or not lyrics.synced:
                        pass
                    elif lrc_path.exists() and not overwrite:
                        logger.debug(
                            f'Synced lyrics already exists at "{lrc_path}", skipping'
                        )
                    else:
                        logger.debug(f'Saving synced lyrics to "{lrc_path}"')
                        downloader_song.save_lrc(lrc_path, lyrics.synced)
                    if lrc_only or not save_cover:
                        pass
                    elif cover_path.exists() and not overwrite:
                        logger.debug(
                            f'Cover already exists at "{cover_path}", skipping'
                        )
                    else:
                        logger.debug(f'Saving cover to "{cover_path}"')
                        downloader.save_cover(cover_path, cover_url)
                elif not spotify_api.is_premium:
                    logger.error(
                        f"({queue_progress}) Cannot download music videos with a free account, skipping"
                    )
                elif lrc_only:
                    logger.warn(
                        f"({queue_progress}) Music videos are not downloadable with "
                        "current settings, skipping"
                    )
                else:
                    cover_url = downloader.get_cover_url(metadata_gid, "XXLARGE")
                    logger.debug("Getting album metadata")
                    album_metadata = spotify_api.get_album(
                        spotify_api.gid_to_track_id(metadata_gid["album"]["gid"])
                    )
                    logger.debug("Getting track credits")
                    track_credits = spotify_api.get_track_credits(track_id)
                    tags = downloader_music_video.get_tags(
                        metadata_gid,
                        album_metadata,
                        track_credits,
                    )
                    final_path = downloader_music_video.get_final_path(tags)
                    cover_path = downloader_music_video.get_cover_path(final_path)
                    if final_path.exists() and not overwrite:
                        logger.warning(
                            f'({queue_progress}) Music video already exists at "{final_path}", skipping'
                        )
                    else:
                        logger.debug("Getting video manifest")
                        manifest = downloader_music_video.get_manifest(metadata_gid)
                        stream_info = downloader_music_video.get_video_stream_info(
                            manifest
                        )
                        logger.debug("Getting decryption key")
                        decryption_key = downloader_music_video.get_decryption_key(
                            stream_info.pssh
                        )
                        m3u8 = downloader_music_video.get_m3u8(
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
                        m3u8_path_video = downloader_music_video.get_m3u8_path(
                            track_id, "video"
                        )
                        encrypted_path_video = downloader.get_encrypted_path(
                            track_id, "_video.ts"
                        )
                        decrypted_path_video = downloader.get_decrypted_path(
                            track_id, "_video.ts"
                        )
                        logger.debug(f'Downloading video to "{encrypted_path_video}"')
                        downloader_music_video.save_m3u8(m3u8.video, m3u8_path_video)
                        downloader_music_video.download(
                            m3u8_path_video,
                            encrypted_path_video,
                        )
                        m3u8_path_audio = downloader_music_video.get_m3u8_path(
                            track_id, "audio"
                        )
                        encrypted_path_audio = downloader.get_encrypted_path(
                            track_id, "_audio.ts"
                        )
                        decrypted_path_audio = downloader.get_decrypted_path(
                            track_id, "_audio.ts"
                        )
                        logger.debug(f"Downloading audio to {encrypted_path_audio}")
                        downloader_music_video.save_m3u8(m3u8.audio, m3u8_path_audio)
                        downloader_music_video.download(
                            m3u8_path_audio,
                            encrypted_path_audio,
                        )
                        remuxed_path = downloader.get_remuxed_path(track_id, ".m4v")
                        logger.debug(f'Decrypting/Remuxing to "{remuxed_path}"')
                        downloader_music_video.remux(
                            decryption_key,
                            encrypted_path_video,
                            encrypted_path_audio,
                            decrypted_path_video,
                            decrypted_path_audio,
                            remuxed_path,
                        )
                        logger.debug("Applying tags")
                        downloader.apply_tags(remuxed_path, tags, cover_url)
                        logger.debug(f'Moving to "{final_path}"')
                        downloader.move_to_final_path(remuxed_path, final_path)
                    if save_cover:
                        cover_path = downloader_music_video.get_cover_path(final_path)
                        if cover_path.exists() and not overwrite:
                            logger.debug(
                                f'Cover already exists at "{cover_path}", skipping'
                            )
                        else:
                            logger.debug(f'Saving cover to "{cover_path}"')
                            downloader.save_cover(cover_path, cover_url)
            except Exception as e:
                error_count += 1
                logger.error(
                    f'({queue_progress}) Failed to download "{track["name"]}"',
                    exc_info=print_exceptions,
                )
            finally:
                if temp_path.exists():
                    logger.debug(f'Cleaning up "{temp_path}"')
                    downloader.cleanup_temp_path()
    logger.info(f"Done ({error_count} error(s))")
