import json
import logging
import shutil
from pathlib import Path

import click

from . import __version__
from .dl import Dl

EXCLUDED_PARAMS = (
    "urls",
    "config_location",
    "url_txt",
    "no_config_file",
    "version",
    "help",
)


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
    "--ffmpeg-location",
    type=Path,
    default="ffmpeg",
    help="Location of the FFmpeg binary.",
)
@click.option(
    "--config-location",
    type=Path,
    default=Path.home() / ".spotify-aac-downloader" / "config.json",
    help="Config file location.",
)
@click.option(
    "--folder-template-album",
    type=str,
    default="{album_artist}/{album}",
    help="Template of the album folders as a format string.",
)
@click.option(
    "--folder-template-compilation",
    type=str,
    default="Compilations/{album}",
    help="Template of the compilation album folders as a format string.",
)
@click.option(
    "--file-template-single-disc",
    type=str,
    default="{track:02d} {title}",
    help="Template of the song files for single-disc albums as a format string.",
)
@click.option(
    "--file-template-multi-disc",
    type=str,
    default="{disc}-{track:02d} {title}",
    help="Template of the song files for multi-disc albums as a format string.",
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
@click.version_option(__version__)
@click.help_option("-h", "--help")
def main(
    urls: tuple[str],
    final_path: Path,
    temp_path: Path,
    cookies_location: Path,
    wvd_location: Path,
    ffmpeg_location: Path,
    config_location: Path,
    folder_template_album: str,
    folder_template_compilation: str,
    file_template_single_disc: str,
    file_template_multi_disc: str,
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
    if not shutil.which(str(ffmpeg_location)):
        logger.critical(f'FFmpeg not found at "{ffmpeg_location}"')
        return
    if cookies_location is not None and not cookies_location.exists():
        logger.critical(f'Cookies file not found at "{cookies_location}"')
        return
    if not wvd_location.exists() and not lrc_only:
        logger.critical(f'.wvd file not found at "{wvd_location}"')
        return
    if url_txt:
        logger.debug("Reading URLs from text files")
        _urls = []
        for url in urls:
            with open(url, "r") as f:
                _urls.extend(f.read().splitlines())
        urls = tuple(_urls)
    logger.debug("Starting downloader")
    dl = Dl(**locals())
    download_queue = []
    for i, url in enumerate(urls):
        try:
            logger.debug(f'Checking "{url}" (URL {i + 1}/{len(urls)})')
            download_queue.append(dl.get_download_queue(url))
        except Exception:
            logger.error(
                f"Failed to check URL {i + 1}/{len(urls)}", exc_info=print_exceptions
            )
    error_count = 0
    for i, url in enumerate(download_queue):
        for j, track in enumerate(url):
            logger.info(
                f'Downloading "{track["name"]}" (track {j + 1}/{len(url)} from URL {i + 1}/{len(download_queue)})'
            )
            try:
                track_id = track["id"]
                logger.debug(f'Getting metadata for "{track_id}"')
                gid = dl.uri_to_gid(track_id)
                metadata = dl.get_metadata(gid)
                logger.debug("Getting lyrics")
                unsynced_lyrics, synced_lyrics = dl.get_lyrics(track_id)
                if not unsynced_lyrics:
                    logger.debug("No unsynced lyrics found")
                if not synced_lyrics:
                    logger.debug("No synced lyrics found")
                tags = dl.get_tags(metadata, unsynced_lyrics)
                final_location = dl.get_final_location(tags)
                if not lrc_only:
                    if overwrite or not final_location.exists():
                        logger.debug("Getting file info")
                        file_id = dl.get_file_id(metadata)
                        logger.debug("Getting PSSH")
                        pssh = dl.get_pssh(file_id)
                        logger.debug("Getting decryption key")
                        decryption_key = dl.get_decryption_key(pssh)
                        logger.debug("Getting stream URL")
                        stream_url = dl.get_stream_url(file_id)
                        encrypted_location = dl.get_encrypted_location(track_id)
                        logger.debug(f'Downloading to "{encrypted_location}"')
                        dl.download(encrypted_location, stream_url)
                        fixed_location = dl.get_fixed_location(track_id)
                        logger.debug(f'Remuxing to "{fixed_location}"')
                        dl.fixup(decryption_key, encrypted_location, fixed_location)
                        logger.debug("Applying tags")
                        dl.apply_tags(fixed_location, tags)
                        logger.debug(f'Moving to "{final_location}"')
                        dl.move_to_final_location(fixed_location, final_location)
                    else:
                        logger.warning(f'"{final_location}" already exists, skipping')
                if synced_lyrics and not no_lrc:
                    lrc_location = dl.get_lrc_location(final_location)
                    if overwrite or not lrc_location.exists():
                        logger.debug(f'Saving synced lyrics to "{lrc_location}"')
                        dl.make_lrc(lrc_location, synced_lyrics)
                    else:
                        logger.warning(f'"{lrc_location}" already exists, skipping')
                if save_cover and not lrc_only:
                    cover_location = dl.get_cover_location(final_location)
                    if overwrite or not cover_location.exists():
                        logger.debug(f'Saving cover to "{cover_location}"')
                        dl.save_cover(tags, cover_location)
                    else:
                        logger.warning(f'"{cover_location}" already exists, skipping')
            except Exception:
                error_count += 1
                logger.error(
                    f'Failed to download "{track["name"]}" (track {j + 1}/{len(url)} from URL '
                    + f"{i + 1}/{len(download_queue)})",
                    exc_info=print_exceptions,
                )
            finally:
                if temp_path.exists():
                    logger.debug(f'Cleaning up "{temp_path}"')
                    dl.cleanup()
    logger.info(f"Done ({error_count} error(s))")
