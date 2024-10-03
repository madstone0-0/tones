from pathlib import Path
import signal
from typing import Iterable
from argparse import ArgumentParser
from db_utils import createDatabase
from search_load import searchFile, loadFile, loadFolders


if __name__ == "__main__":

    def handleInt(sig, frame):
        print("Exiting...")
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, handleInt)

    parser = ArgumentParser(
        prog="tones", description="CLI for tone adding and searching"
    )

    parser.add_argument(
        "--mode",
        metavar="mode",
        required=True,
        type=str,
        help="Mode of operation: load, load_folder, search",
    )

    parser.add_argument(
        "--filename",
        metavar="filename",
        required=True,
        type=str,
        help="Filename or foldername to load or search",
    )

    parser.add_argument(
        "--verbose",
        default=False,
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--overwrite",
        default=False,
        action="store_true",
        help="Overwrite existing db",
    )

    args = parser.parse_args()
    mode = args.mode
    filename = args.filename
    v = args.verbose
    overwrite = args.overwrite

    db = "dbname=tones user=mads"

    res = None

    match mode:
        case "load":
            loadFile(db, filename, verbose=v)
        case "load_folder":
            if overwrite:
                print("Overwriting database")
                createDatabase(db, "./src/db/schema.sql")
            loadFolders(db, Path(filename), verbose=v, maxWorkers=5)
        case "search":
            res = searchFile(db, filename, verbose=v)
        case _:
            print("Invalid mode")
            exit(1)

    if res is not None:
        if isinstance(res, Iterable):
            print("Found tones:")
            for item in res:
                print(item[0])
        else:
            print(f"Tone: {res}")
