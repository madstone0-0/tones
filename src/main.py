from sys import argv
from pathlib import Path
import shutil
from db_utils import (
    createDatabase,
    storeTone,
    storeAddressCouple,
    readAddressCoupleFromAddress,
    readTone,
)
from audio_utils import getAudioInfo, processAudiofile
from audio_proc import printInfo
from codec import (
    decodeCouple64Bit,
    encodeAddress32Bit,
)
from collections import Counter


def stressTest(foldername: Path, db):
    shutil.rmtree(db, ignore_errors=True)
    for file in foldername.iterdir():
        if file.is_dir():
            stressTest(file, db)
        if file.is_file() and file.suffix in [".wav", ".mp3", ".flac"]:
            print(file)
            info = getAudioInfo(str(file))
            printInfo(info)
            toneId = processAudiofile(info, db)
            toneName = file.stem
            storeTone(db, toneId, toneName)


def loadFile(db, filename):
    info = getAudioInfo(filename)
    printInfo(info)
    path: Path = Path(filename).resolve()

    toneId, addressCouple = processAudiofile(info, db)
    toneName = path.stem
    storeAddressCouple(db, addressCouple)
    print(f"Stored address-couple pairs in database for tone_id: {toneId}")
    storeTone(db, toneId, toneName)


def loadFolder(db, foldername):
    # TODO Make concurrent
    for file in foldername.iterdir():
        if file.is_dir():
            loadFolder(file, db)
        if file.is_file() and file.suffix in [".wav", ".mp3", ".flac"]:
            print(file)
            info = getAudioInfo(str(file))
            printInfo(info)
            toneId = processAudiofile(info, db)
            toneName = file.stem
            storeTone(db, toneId, toneName)


def searchFile(db, filename):
    info = getAudioInfo(filename)
    printInfo(info)
    toneId, addressCouple = processAudiofile(info, db)
    foundTones = []
    for address, couple in addressCouple:
        address = encodeAddress32Bit(address)

        read = readAddressCoupleFromAddress(db, address)
        if not read:
            continue
        a, c = read[0]
        couple = decodeCouple64Bit(c)
        id = couple[1]
        tone = readTone(db, id)
        foundTones.append(tone)

    for tone in foundTones:
        print(tone)

    # Most common tone
    count = Counter(foundTones)
    common = count.most_common(1)[0][0][1]
    print(common)
    return common


if __name__ == "__main__":
    if len(argv) < 2:
        print("Usage: python sound.py WAV OPTIONS")
        exit(1)

    filename = argv[1]
    mode = argv[2]

    db = "test.db"

    createDatabase(db, "./src/db/schema.sql")

    match mode:
        case "load":
            loadFile(db, filename)
        case "load_folder":
            loadFolder(db, Path(filename))
        case "search":
            searchFile(db, filename)
        case _:
            print("Invalid mode")
            exit(1)
