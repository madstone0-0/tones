from concurrent.futures.process import ProcessPoolExecutor
from pathlib import Path
from typing import Counter
import psycopg as sql

from db_utils import (
    doesToneExist,
    storeTone,
    storeAddressCouple,
    readAddressCoupleFromAddress,
    readTone,
)
from audio_utils import genToneId, getAudioInfo, processAudiofile
from audio_proc import printInfo
from codec import (
    decodeAddress32Bit,
    decodeCouple64Bit,
    encodeAddress32Bit,
)
from multiprocessing import Queue

# from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import as_completed

TARGET_RES = 100
# TARGET_RES = 10.7


def loadFile(db, filename, verbose=False):
    print(f"Loading file: {filename}")
    info = getAudioInfo(filename)
    if verbose:
        printInfo(info)
    path: Path = Path(filename).resolve()

    # Generate max 32bit integer for toneId using the first 32 bits of the hash of the audio data
    toneId = genToneId(info)
    with sql.connect(db) as conn:
        if doesToneExist(conn, toneId):
            return f"Tone {toneId} already exists in database"

        addressCouple = processAudiofile(
            info, db, toneId, verbose=verbose, targetRes=TARGET_RES
        )
        toneName = path.stem
        storeAddressCouple(conn, addressCouple)
        try:
            storeTone(conn, toneId, toneName)
        except Exception as e:
            return f"Error: {e}"
        return f"Stored address-couple pairs in database for tone_id: {toneId}"


def findFiles(foldername: Path, fileQueue: Queue):
    for file in foldername.rglob("*"):
        if file.is_file() and file.suffix in [".wav", ".mp3", ".flac"]:
            print(f"Found: {file}")
            fileQueue.put(file)


def loadFolders(db, foldername, maxWorkers=6, verbose=False):
    fileQueue = Queue()
    findFiles(foldername, fileQueue)
    failed = 0

    with open("error.log", "a+") as f:
        try:
            with ProcessPoolExecutor(max_workers=maxWorkers) as exec:
                # with ThreadPoolExecutor(max_workers=maxWorkers) as exec:
                todo = {}
                while not fileQueue.empty():
                    file = fileQueue.get()
                    future = exec.submit(loadFile, db, str(file), verbose)
                    todo[future] = str(file)
                for job in as_completed(todo):
                    file = todo[job]
                    try:
                        res = job.result()
                        print(res)
                    except (ZeroDivisionError, IndexError) as e:
                        failed += 1
                        f.write(f"Error: {file}\n")
                        f.write(str(e))
                        f.write("\n")
                        f.write("\n")
        except KeyboardInterrupt:
            print("Terminating all processes...")
            exec.shutdown(wait=False)
        finally:
            print(f"Failed: {failed}")


def isMatchingZone(
    couple, decoededCouple, address, decodedAddress, timeFreqTol=(0.1, 0.1)
):
    toneTime, _ = couple
    dbTime, _ = decoededCouple
    _, toneFreq, _ = address
    _, dbFreq, _ = decodedAddress

    if (
        abs(toneTime - dbTime) <= timeFreqTol[0]
        and abs(toneFreq - dbFreq) <= timeFreqTol[1]
    ):
        return True

    return False


def maxTimeCoherentNotes(addressCouple, dbAddressCouple, tolerance=0.1):
    deltas = []

    for address, couple in addressCouple:
        for a, c in dbAddressCouple:
            deltas.append(abs(couple[0] - c[0]))

    deltaCount = Counter(deltas)
    if len(deltaCount.most_common(1)) == 0:
        return None
    else:
        return deltaCount.most_common(1)[0]


def tryCoherency(
    addressCouple,
    foundDB,
    foundTones,
    numTargetZones,
    coeff=0.5,
    verbose=False,
    tol=0.1,
):
    maxCoherency = 0
    bestSong = None
    for id in foundDB:
        maxTime = maxTimeCoherentNotes(addressCouple, foundDB[id], tolerance=tol)
        if not maxTime:
            continue
        if verbose:
            print(f"{foundTones[id]["tone"][1]} : {maxTime}")

        if maxTime[1] > maxCoherency:
            maxCoherency = maxTime[1]
            bestSong = id

    if maxCoherency >= numTargetZones * coeff:
        if verbose:
            print(f"Best match: {foundTones[bestSong]["tone"][1]}")
        return foundTones[bestSong]["tone"][1]
    else:
        if verbose:
            print("No tone met coherency threshold")
        return None


def tryMatchRatios(foundTones, numTargetZones, cutoff, verbose=False):
    filtered = []
    tonesWithMatchRatios = {}
    for id, data in foundTones.items():
        matchRatio = data["common"] / numTargetZones
        tonesWithMatchRatios[id] = (data["tone"][1], matchRatio)
        if matchRatio >= cutoff:
            filtered.append((data["tone"][1], matchRatio))

    if not filtered:
        if verbose:
            print("Tone not found with the given cutoff ouputting top 5 matches")
        top5 = sorted(tonesWithMatchRatios.values(), key=lambda x: x[1], reverse=True)[
            :5
        ]

        if verbose:
            print("Top 5 matches:")
            for tone, matchRatio in top5:
                print(f"{tone}: {matchRatio:.5%}")
        return tuple(top5)

    if verbose:
        for tone, matchRatio in filtered:
            print(f"{tone}: {matchRatio:.2%}")
    return filtered


def searchFile(
    db,
    filename,
    cutoff=0.50,
    verbose=False,
    coherencyTol=0.1,
    coeff=0.5,
    timeFreqTol=(0.1, 0.1),
):
    info = getAudioInfo(filename)

    if verbose:
        printInfo(info)

    addressCouple = processAudiofile(info, db, toneId=0, targetRes=TARGET_RES)
    numTargetZones = len(addressCouple)

    if verbose:
        print(f"Number of target zones: {numTargetZones}")

    foundTones = {}
    foundDB = {}

    # Find the matching couples in the database for all fingerprints
    for address, couple in addressCouple:
        if verbose:
            print(f"Searching for: {address}")
            print(f"Encoded: {address}")

        address = encodeAddress32Bit(address)
        read = readAddressCoupleFromAddress(db, address)
        if not read:
            continue

        address = decodeAddress32Bit(address)

        for a, c in read:
            c = decodeCouple64Bit(c)
            a = decodeAddress32Bit(a)
            id = c[1]
            tone = readTone(db, id)

            if id not in foundTones:
                foundTones[id] = {"tone": tone, "common": 0}
                foundDB[id] = []

            if isMatchingZone(couple, c, address, a, timeFreqTol=timeFreqTol):
                foundTones[id]["common"] += 1
                foundDB[id].append((a, c))

    coherencyRes = tryCoherency(
        addressCouple,
        foundDB,
        foundTones,
        numTargetZones,
        verbose=verbose,
        coeff=coeff,
        tol=coherencyTol,
    )
    if coherencyRes:
        return coherencyRes

    matchRatioRes = tryMatchRatios(foundTones, numTargetZones, cutoff, verbose=verbose)
    if matchRatioRes:
        return matchRatioRes

    return None


def searchFileN(db, filename, cutoff=0.50, n=3):
    results = []
    for i in range(n):
        results += [searchFile(db, filename, cutoff)]

    print("Results:")
    for i, res in enumerate(results):
        print(f"Run {i+1}")
        for tone, matchRatio in res:
            print(f"{tone}: {matchRatio:.2%}")
