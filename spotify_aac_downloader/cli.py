from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from . import __version__
from .constants import *
from .downloader import Downloader


def write_default_config_file(ctx: click.Context):
    ctx.params["config_location"].parent.mkdir(parents=True, exist_ok=True)
    config_file = {
        param.name: param.default
        for param in ctx.command.params
        if param.name not in EXCLUDED_PARAMS
    }
    with open(ctx.params["config_location"], "w") as f:
        f.write(json.dumps(config_file, indent=4))


def no_config_callback(
    ctx: click.Context, param: click.Parameter, no_config_file: bool
):
    if no_config_file:
        return ctx
    if not ctx.params["config_location"].exists():
        write_default_config_file(ctx)
    with open(ctx.params["config_location"], "r") as f:
        config_file = dict(json.load(f))
    for param in ctx.command.params:
        if (
            config_file.get(param.name) is not None
            and not ctx.get_parameter_source(param.name)
            == click.core.ParameterSource.COMMANDLINE
        ):
            ctx.params[param.name] = param.type_cast_value(ctx, config_file[param.name])
    return ctx


@click.command()
@click.argument(
    "urls",
    nargs=-1,
    type=str,
    required=True,
)
@click.option(
    "--final-path",
    "-f",
    type=Path,
    default="./Spotify",
    help="Path where the downloaded files will be saved.",
)
@click.option(
    "--temp-path",
    "-t",
    type=Path,
    default="./temp",
    help="Path where the temporary files will be saved.",
)
@click.option(
    "--cookies-location",
    "-c",
    type=Path,
    default="./cookies.txt",
    help="Location of the cookies file.",
)
@click.option(
    "--wvd-location",
    "-w",
    type=Path,
    default="./device.wvd",
    help="Location of the .wvd file.",
)
@click.option(
    "--config-location",
    type=Path,
    default=Path.home() / ".spotify-aac-downloader" / "config.json",
    help="Location of the config file.",
)
@click.option(
    "--ffmpeg-location",
    type=str,
    default="ffmpeg",
    help="Location of the FFmpeg binary.",
)
@click.option(
    "--aria2c-location",
    type=str,
    default="aria2c",
    help="Location of the aria2c binary.",
)
@click.option(
    "--template-folder-album",
    type=str,
    default="{album_artist}/{album}",
    help="Template of the album folders as a format string.",
)
@click.option(
    "--template-folder-compilation",
    type=str,
    default="Compilations/{album}",
    help="Template of the compilation album folders as a format string.",
)
@click.option(
    "--template-file-single-disc",
    type=str,
    default="{track:02d} {title}",
    help="Template of the song files for single-disc albums as a format string.",
)
@click.option(
    "--template-file-multi-disc",
    type=str,
    default="{disc}-{track:02d} {title}",
    help="Template of the song files for multi-disc albums as a format string.",
)
@click.option(
    "--download-mode",
    type=click.Choice(["ytdlp", "aria2c"]),
    default="ytdlp",
    help="Download mode.",
)
@click.option(
    "--exclude-tags",
    "-e",
    type=str,
    default=None,
    help="List of tags to exclude from file tagging separated by commas.",
)
@click.option(
    "--truncate",
    type=int,
    default=40,
    help="Maximum length of the file/folder names.",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Log level.",
)
@click.option(
    "--premium-quality",
    "-p",
    is_flag=True,
    help="Download in 256kbps AAC instead of 128kbps AAC.",
)
@click.option(
    "--lrc-only",
    "-l",
    is_flag=True,
    help="Download only the synced lyrics.",
)
@click.option(
    "--no-lrc",
    "-n",
    is_flag=True,
    help="Don't download the synced lyrics.",
)
@click.option(
    "--save-cover",
    "-s",
    is_flag=True,
    help="Save cover as a separate file.",
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    help="Overwrite existing files.",
)
@click.option(
    "--print-exceptions",
    is_flag=True,
    help="Print exceptions.",
)
@click.option(
    "--url-txt",
    "-u",
    is_flag=True,
    help="Read URLs as location of text files containing URLs.",
)
@click.option(
    "--no-config-file",
    "-n",
    is_flag=True,
    callback=no_config_callback,
    help="Don't use the config file.",
)
@click.version_option(__version__, "-v", "--version")
@click.help_option("-h", "--help")
def main(
    urls: tuple[str],
    final_path: Path,
    temp_path: Path,
    cookies_location: Path,
    wvd_location: Path,
    config_location: Path,
    ffmpeg_location: str,
    aria2c_location: str,
    template_folder_album: str,
    template_folder_compilation: str,
    template_file_single_disc: str,
    template_file_multi_disc: str,
    download_mode: str,
    exclude_tags: str,
    truncate: int,
    log_level: str,
    premium_quality: bool,
    lrc_only: bool,
    no_lrc: bool,
    save_cover: bool,
    overwrite: bool,
    print_exceptions: bool,
    url_txt: bool,
    no_config_file: bool,
):
    logging.basicConfig(
        format="[%(levelname)-8s %(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    logger.debug("Starting downloader")
    downloader = Downloader(**locals())
    if not downloader.ffmpeg_location:
        logger.critical(X_NOT_FOUND_STRING.format("FFmpeg", ffmpeg_location))
        return
    if download_mode == "aria2c" and not downloader.aria2c_location:
        logger.critical(X_NOT_FOUND_STRING.format("aria2c", aria2c_location))
        return
    if cookies_location is not None and not cookies_location.exists():
        logger.critical(X_NOT_FOUND_STRING.format("Cookies", cookies_location))
        return
    if not wvd_location.exists() and not lrc_only:
        logger.critical(X_NOT_FOUND_STRING.format(".wvd file", wvd_location))
        return
    if url_txt:
        logger.debug("Reading URLs from text files")
        _urls = []
        for queue_item in urls:
            with open(queue_item, "r") as f:
                _urls.extend(f.read().splitlines())
        urls = tuple(_urls)
    if not lrc_only:
        if not wvd_location.exists():
            logger.critical(X_NOT_FOUND_STRING.format(".wvd file", wvd_location))
            return
        logger.debug("Setting up CDM")
        downloader.setup_cdm()
    logger.debug("Setting up session")
    downloader.setup_session()
    if premium_quality and downloader.is_premium == "false":
        logger.critical("Cannot download in premium quality with a free account")
        return
    download_queue = []
    error_count = 0
    for url_index, url in enumerate(urls, start=1):
        current_url = f"URL {url_index}/{len(urls)}"
        try:
            logger.debug(f'({current_url}) Checking "{url}"')
            download_queue.append(downloader.get_download_queue(url))
        except Exception:
            error_count += 1
            logger.error(
                f'({current_url}) Failed to check "{url}"',
                exc_info=print_exceptions,
            )
    for queue_item_index, queue_item in enumerate(download_queue, start=1):
        for track_index, track in enumerate(queue_item, start=1):
            current_track = f"Track {track_index}/{len(queue_item)} from URL {queue_item_index}/{len(download_queue)}"
            try:
                logger.info(f'({current_track}) Downloading "{track["name"]}"')
                track_id = track["id"]
                logger.debug("Getting metadata")
                gid = downloader.uri_to_gid(track_id)
                metadata = downloader.get_metadata(gid)
                if metadata.get("has_lyrics"):
                    logger.debug("Getting lyrics")
                    lyrics_unsynced, lyrics_synced = downloader.get_lyrics(track_id)
                else:
                    lyrics_unsynced, lyrics_synced = None, None
                tags = downloader.get_tags(metadata, lyrics_unsynced)
                final_location = downloader.get_final_location(tags)
                lrc_location = downloader.get_lrc_location(final_location)
                cover_location = downloader.get_cover_location(final_location)
                cover_url = downloader.get_cover_url(metadata)
                if lrc_only:
                    pass
                elif final_location.exists() and not overwrite:
                    logger.warning(
                        f'({current_track}) Track already exists at "{final_location}", skipping'
                    )
                else:
                    logger.debug("Getting file info")
                    file_id = downloader.get_file_id(metadata)
                    if not file_id:
                        logger.error(
                            f"({current_track}) Track not available on Spotify's "
                            "servers and no alternative found, skipping"
                        )
                        continue
                    logger.debug("Getting PSSH")
                    pssh = downloader.get_pssh(file_id)
                    logger.debug("Getting decryption key")
                    decryption_key = downloader.get_decryption_key(pssh)
                    logger.debug("Getting stream URL")
                    stream_url = downloader.get_stream_url(file_id)
                    encrypted_location = downloader.get_encrypted_location(track_id)
                    logger.debug(f'Downloading to "{encrypted_location}"')
                    if download_mode == "ytdlp":
                        downloader.download_ytdlp(encrypted_location, stream_url)
                    if download_mode == "aria2c":
                        downloader.download_aria2c(encrypted_location, stream_url)
                    fixed_location = downloader.get_fixed_location(track_id)
                    logger.debug(f'Remuxing to "{fixed_location}"')
                    downloader.fixup(decryption_key, encrypted_location, fixed_location)
                    logger.debug("Applying tags")
                    downloader.apply_tags(fixed_location, tags, cover_url)
                    logger.debug(f'Moving to "{final_location}"')
                    downloader.move_to_final_location(fixed_location, final_location)
                if no_lrc or not lyrics_synced:
                    pass
                elif lrc_location.exists() and not overwrite:
                    logger.debug(
                        f'Synced lyrics already exists at "{lrc_location}", skipping'
                    )
                else:
                    logger.debug(f'Saving synced lyrics to "{lrc_location}"')
                    downloader.save_lrc(lrc_location, lyrics_synced)
                if lrc_only or not save_cover:
                    pass
                elif cover_location.exists() and not overwrite:
                    logger.debug(
                        f'Cover already exists at "{cover_location}", skipping'
                    )
                else:
                    logger.debug(f'Saving cover to "{cover_location}"')
                    downloader.save_cover(cover_location, cover_url)
            except Exception:
                error_count += 1
                logger.error(
                    f'({current_track}) Failed to download "{track["name"]}"',
                    exc_info=print_exceptions,
                )
            finally:
                if temp_path.exists():
                    logger.debug(f'Cleaning up "{temp_path}"')
                    downloader.cleanup_temp_path()
    logger.info(f"Done ({error_count} error(s))")
