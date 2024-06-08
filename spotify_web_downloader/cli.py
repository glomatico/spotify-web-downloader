from __future__ import annotations

import inspect
import json
import logging
from enum import Enum
from pathlib import Path

import click

from . import __version__
from .app import App, ExternalUtilities
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

    utilities = ExternalUtilities(
        ffmpeg_path=ffmpeg_path,
        aria2c_path=aria2c_path,
        nm3u8dlre_path=nm3u8dlre_path,
        mp4box_path=mp4box_path,
        mp4decrypt_path=mp4decrypt_path
    )

    app = App(
        logger,
        spotify_api,
        downloader,
        downloader_song,
        downloader_music_video,
        lrc_only,
        download_music_video,
        utilities,
    )
    app.setup()

    app.run(
        urls=urls,
        save_cover=save_cover,
        overwrite=overwrite,
        read_urls_as_txt=read_urls_as_txt,
        no_lrc=no_lrc,
        print_exceptions=print_exceptions,
    )
