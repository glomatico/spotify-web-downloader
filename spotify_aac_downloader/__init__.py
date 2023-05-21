import shutil
import argparse
import traceback

from .spotify_aac_downloader import SpotifyAacDownloader

__version__ = '1.2'


def main():
    for tool in ('ffmpeg'):
        if not shutil.which(tool):
            raise Exception(f'{tool} is not on PATH')
    parser = argparse.ArgumentParser(
        description='Download songs/albums/playlists directly from Spotify in AAC',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'url',
        help='Spotify song/album/playlist URL(s)',
        nargs='*',
    )
    parser.add_argument(
        '-u',
        '--urls-txt',
        help='Read URLs from a text file',
        action='store_true',
    )
    parser.add_argument(
        '-f',
        '--final-path',
        default='./Spotify',
        help='Final Path',
    )
    parser.add_argument(
        '-t',
        '--temp-path',
        default='./temp',
        help='Temp Path',
    )
    parser.add_argument(
        '-c',
        '--cookies-location',
        default='./cookies.txt',
        help='Cookies location',
    )
    parser.add_argument(
        '-w',
        '--wvd-location',
        default='./*.wvd',
        help='.wvd file location (ignored if using -l/--lrc-only)',
    )
    parser.add_argument(
        '-n',
        '--no-lrc',
        action='store_true',
        help="Don't create .lrc files",
    )
    parser.add_argument(
        '-l',
        '--lrc-only',
        action='store_true',
        help='Skip downloading songs and only create .lrc files',
    )
    parser.add_argument(
        '-p',
        '--premium-quality',
        action='store_true',
        help='Download 256kbps AAC instead of 128kbps AAC',
    )
    parser.add_argument(
        '-o',
        '--overwrite',
        action='store_true',
        help='Overwrite existing files',
    )
    parser.add_argument(
        '-e',
        '--print-exceptions',
        action='store_true',
        help='Print execeptions',
    )
    parser.add_argument(
        '-v',
        '--version',
        action='version',
    )
    args = parser.parse_args()
    if args.urls_txt:
        _url = []
        for url_txt in args.url:
            with open(url_txt, 'r', encoding='utf8') as f:
                _url.extend(f.read().splitlines())
        args.url = _url
    dl = SpotifyAacDownloader(
        args.final_path,
        args.cookies_location,
        args.temp_path,
        args.wvd_location,
        args.premium_quality,
        args.overwrite,
        args.no_lrc,
        args.lrc_only,
    )
    download_queue = []
    error_count = 0
    for i, url in enumerate(args.url):
        try:
            download_queue.append(dl.get_download_queue(url.strip()))
        except KeyboardInterrupt:
            exit(1)
        except:
            error_count += 1
            print(f'Failed to check URL {i + 1}/{len(args.url)}')
            if args.print_exceptions:
                traceback.print_exc()
    for i, url in enumerate(download_queue):
        for j, track in enumerate(url):
            print(f'Downloading "{track["name"]}" (track {j + 1}/{len(url)} from URL {i + 1}/{len(download_queue)})')
            try:
                track_id = track['id']
                gid = dl.uri_to_gid(track_id)
                metadata = dl.get_metadata(gid)
                unsynced_lyrics, synced_lyrics = dl.get_lyrics(track_id)
                tags = dl.get_tags(metadata, unsynced_lyrics)
                final_location = dl.get_final_location(tags)
                if args.lrc_only:
                    final_location.parent.mkdir(parents=True, exist_ok=True)
                    dl.make_lrc(final_location, synced_lyrics)
                    continue
                if not args.overwrite and final_location.exists():
                    continue
                file_id = dl.get_file_id(metadata)
                pssh = dl.get_pssh(file_id)
                decryption_key = dl.get_decryption_key(pssh)
                stream_url = dl.get_stream_url(file_id)
                encrypted_location = dl.get_encrypted_location(track_id)
                dl.download(encrypted_location, stream_url)
                fixed_location = dl.get_fixed_location(track_id)
                dl.fixup(decryption_key, encrypted_location, fixed_location)
                final_location.parent.mkdir(parents=True, exist_ok=True)
                dl.make_final(fixed_location, final_location, tags)
                dl.make_lrc(final_location, synced_lyrics)
            except KeyboardInterrupt:
                exit(1)
            except:
                error_count += 1
                print(f'Failed to download "{track["name"]}" (track {j + 1}/{len(url)} from URL {i + 1}/{len(download_queue)})')
                if args.print_exceptions:
                    traceback.print_exc()
            dl.cleanup()
    print(f'Done ({error_count} error(s))')
