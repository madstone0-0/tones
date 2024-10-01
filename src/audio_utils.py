import matplotlib.pyplot as plt
from typing import Dict
import numpy as np
import pyaudio
from collections import deque
from hashlib import sha256
import ffmpeg
from visualize import visualizeStrongestFrequencies, visualizeSong, visualizeSpectograph
from codec import decodeAddress32Bit, decodeCouple64Bit
from audio_proc import WAVInfo, getWAVInfo, generateSpectograph, preprocess


def getAudioInfo(filename: str) -> WAVInfo:
    # if filename.endswith(".wav"):
    #     with open(filename, mode="rb") as f:
    #         return getWAVInfo(f.read())
    try:
        process = (
            ffmpeg.input(filename)
            .output("pipe:", format="wav")
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print("stdout:", e.stdout.decode("utf8"))
        print("stderr:", e.stderr.decode("utf8"))
        raise e
    return getWAVInfo(process[0])


def playWav(info: WAVInfo):
    print("Playing audio (CTRL-C to stop)")
    sound = pyaudio.PyAudio()
    stream = sound.open(
        format=pyaudio.paInt16 if info.bitsPerSample == 16 else pyaudio.paInt8,
        channels=1 if info.mono else 2,
        rate=info.sampleFreq,
        output=True,
    )
    pointer = 0
    try:
        while True:
            if pointer >= len(info.data):
                break
            stream.write(info.data[pointer : pointer + info.bytesSec])
            pointer += info.bytesSec
    except KeyboardInterrupt:
        pass
    stream.close()


def logarithmicSplits(n_bins, n_bands):
    bin_ranges = [
        (0, 10),  # Very Low Sound Band
        (10, 20),  # Low Sound Band
        (20, 40),  # Low-Mid Sound Band
        (40, 80),  # Mid Sound Band
        (80, 160),  # Mid-High Sound Band
        (160, 511),  # High Sound Band
    ]

    bin_ranges = [(start, min(end, n_bins - 1)) for start, end in bin_ranges]

    return bin_ranges


def quantizeFreqs(freqs, resolution_hz=1):
    """
    Quantize frequencies with adaptive resolution.

    Args:
    freqs (array-like): Array of frequencies in Hz
    resolution_hz (float): Base resolution in Hz

    Returns:
    ndarray: Quantized frequencies as a NumPy array
    """
    # Ensure input is a NumPy array
    freqs = np.asarray(freqs)

    # Convert to cents (relative to 1 Hz)
    cents = 1200 * np.log2(freqs)

    # Adaptive quantization: finer for lower frequencies
    quant_factor = np.maximum(1, np.log2(freqs / 440) + 5)
    quant_cents = np.round(cents / (resolution_hz * quant_factor)) * (
        resolution_hz * quant_factor
    )

    # Convert back to Hz
    return np.power(2, quant_cents / 1200)


def extractFrequencies(Zxx, freq, coef=0.5, bands=6, verbose=False):
    binsN = len(Zxx[0])
    ranges = logarithmicSplits(binsN, bands)

    freqs = []
    for bin in Zxx.T:  # Transpose Zxx to iterate over time bins
        strongest = []
        for start, end in ranges:
            band = bin[start : end + 1]
            if len(band) > 0:
                strongestBin = np.max(band)
                strongestFreq = freq[start + np.argmax(band)]
                strongest.append((strongestFreq, strongestBin))

        avg = np.mean([strength for _, strength in strongest])
        keep = [freq for freq, strength in strongest if strength > (avg * coef)]

        # Pad with zeros if necessary
        keep = np.pad(keep, (0, bands - len(keep)), "constant")
        freqs.append(keep)
    freqs = np.array(freqs)

    if verbose:
        print(f"""
        Number of bins: {binsN}
        Number of bands: {bands}
        Shape of freqs: {freqs.shape}""")

    return freqs


def generateTimeFreqOrderRelation(times, Zxx):
    pos = 0
    orderedFreqs: Dict[int, float] = {}
    i = 0
    while i < len(times):
        while i < len(times) - 2 and times[i] == times[i + 1]:
            minFreqPos = np.argmin([Zxx[i], Zxx[i + 1]])
            if minFreqPos == 0:
                orderedFreqs[pos] = Zxx[i]
                pos += 1
                orderedFreqs[pos] = Zxx[i + 1]
            else:
                orderedFreqs[pos] = Zxx[i + 1]
                pos += 1
                orderedFreqs[pos] = Zxx[i]
            pos += 1
            i += 2
        orderedFreqs[pos] = Zxx[i]
        pos += 1
        i += 1
    return orderedFreqs


def createTargetZones(orderedFreqs):
    zones = []
    # To generate target zones in a spectrogram, you need for each time-frequency point to create a group composed
    # of this point and the 4 points after it
    for i in range(len(orderedFreqs) - 4):
        zones.append(tuple(orderedFreqs.values())[i : i + 5])
    return np.array(zones)


def generateAddress(zones, orderedFreqs, times, songId):
    def addressFormula(anchor, freq, anchorTime, freqTime):
        return (anchor, freq, np.abs(anchorTime - freqTime))

    def mapAddressToCouple(anchorTime):
        return (anchorTime, songId)

    addressCouple = []
    freqTimes = list(zip(orderedFreqs.values(), times))
    freqTimesDeque = deque(freqTimes)

    for i, zone in enumerate(zones):
        if i < 3:
            anchorIndex = 0
        else:
            anchorIndex = i - 3

        anchor, anchorTime = freqTimes[anchorIndex]

        # Find the start of the current zone
        while freqTimesDeque and freqTimesDeque[0][0] != zone[0]:
            freqTimesDeque.popleft()

        # Process the zone
        for _ in range(5):  # Each zone has 5 points
            if freqTimesDeque:
                freq, freqTime = freqTimesDeque[0]
                address = addressFormula(anchor, freq, anchorTime, freqTime)
                couple = mapAddressToCouple(anchorTime)
                addressCouple.append((address, couple))
                freqTimesDeque.popleft()
            else:
                break  # End of frequencies

    return addressCouple


def parseAddressCouple(addressCouple):
    addressCouple = [(int(address), int(couple)) for address, couple in addressCouple]
    for address, couple in addressCouple:
        addressDecoded = decodeAddress32Bit(address)
        coupleDecoded = decodeCouple64Bit(couple)
        yield addressDecoded, coupleDecoded


def genToneId(info):
    hash = sha256(info.data).digest()
    return int.from_bytes(hash[:4], "big")


def processAudiofile(
    info: WAVInfo, db, toneId, visualize=False, verbose=False, targetRes=50
):
    if visualize:
        visualizeSong(info)

    info = preprocess(info, downmix=True, downsampleFactor=4, verbose=verbose)
    windowSize = int(info.sampleFreq / targetRes)
    windowDuration = windowSize / info.sampleFreq
    freq, times, Zxx, data, overlap = generateSpectograph(info, windowDuration)

    if visualize:
        visualizeSpectograph(
            freq, times, Zxx, data, overlap, windowSize, info.sampleFreq
        )

    strongest = extractFrequencies(Zxx, freq, verbose=verbose)
    t = []
    for timeIdx, freqComp in enumerate(strongest):
        time = times[timeIdx]
        for freq in freqComp:
            if freq > 0:
                t.append((freq, time))

    table = np.asarray(t)
    times = table[:, 1]
    freqs = table[:, 0]

    if visualize:
        visualizeStrongestFrequencies(times, freqs)
        plt.show()

    orderedFreqs = generateTimeFreqOrderRelation(times, freqs)
    targetZones = createTargetZones(orderedFreqs)
    addressCouple = generateAddress(targetZones, orderedFreqs, times, toneId)
    return addressCouple
