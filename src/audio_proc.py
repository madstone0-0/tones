from functools import partial
from dataclasses import dataclass
import numpy as np
from scipy.signal import stft
from scipy.signal import butter, lfilter
from datetime import datetime

type Buffer = bytes


@dataclass
class WAVInfo:
    rif: str = ""
    size: int = 0
    descr: str = ""
    fmt: str = ""
    sectionSize: int = 0
    typeFormat: int = 0
    mono: bool = False
    sampleFreq: int = 0
    bytesSec: int = 0
    blockAlign: int = 0
    bitsPerSample: int = 0
    dataDescr: str = ""
    dataChunkSize: int = 0
    data: Buffer = b""


def littleE(byteList: Buffer) -> int:
    res = 0
    for i in range(len(byteList)):
        res |= byteList[i] << (i * 8)
    return res


def bigE(byteList: Buffer) -> int:
    res = 0
    for i in range(len(byteList)):
        res |= byteList[i] << ((len(byteList) - i - 1) * 8)
    return res


RIFF_SIZE = 4
SIZE_SIZE = 4
DESCR_SIZE = 4
FMT_SIZE = 4
SECTION_SIZE = 4
TYPE_SIZE = 2
MONO_SIZE = 2
SAMPLE_FREQ_SIZE = 4
BYTES_SEC_SIZE = 4
BLOCK_ALIGN_SIZE = 2
BITS_PER_SAMPLE_SIZE = 2
DATA_DESCR_SIZE = 4
DATA_CHUNK_SIZE = 4


@dataclass
class Iterator:
    ptr: int


def getInfo(buffer: Buffer, beg: Iterator, size: int):
    res = buffer[beg.ptr : size + beg.ptr]
    beg.ptr += size
    return res


def getWAVInfo(buffer: Buffer) -> WAVInfo:
    info = WAVInfo()
    beg = Iterator(0)
    gi = partial(getInfo, buffer, beg)

    info.rif = gi(RIFF_SIZE).decode()
    info.size = littleE(gi(SIZE_SIZE))
    info.descr = gi(DESCR_SIZE).decode()
    info.fmt = gi(FMT_SIZE).decode()
    info.sectionSize = littleE(gi(SECTION_SIZE))
    info.typeFormat = littleE(gi(TYPE_SIZE))
    info.mono = littleE(gi(MONO_SIZE)) == 0
    info.sampleFreq = littleE(gi(SAMPLE_FREQ_SIZE))
    info.bytesSec = littleE(gi(BYTES_SEC_SIZE))
    info.blockAlign = littleE(gi(BLOCK_ALIGN_SIZE))
    info.bitsPerSample = littleE(gi(BITS_PER_SAMPLE_SIZE))
    info.dataDescr = gi(DATA_DESCR_SIZE).decode()
    info.dataChunkSize = littleE(gi(DATA_CHUNK_SIZE))

    info.data = gi(len(buffer))

    return info


def quantizeFreq9Bit(freq):
    """
    Quantize frequency to 9-bit representation.

    Args:
    freq (float): Input frequency in Hz

    Returns:
    int: 9-bit quantized value
    """
    minFreq = 20
    maxFreq = 20000
    n_steps = 512

    if freq < minFreq:
        return 0
    if freq > maxFreq:
        return n_steps - 1

    # Calculate log-spaced frequency bins
    freqBins = minFreq * (maxFreq / minFreq) ** (np.arange(n_steps) / (n_steps - 1))

    # Find the nearest bin
    quantized = np.argmin(np.abs(freqBins - freq))

    return quantized


def bytesTo24Bit(data: Buffer):
    # Ensure that the length of the byte_data is divisible by 3
    extraBytes = len(data) % 3
    if extraBytes != 0:
        print(
            f"Warning: Byte data length {len(data)} is not divisible by 3. Trimming {extraBytes} bytes."
        )
        data = data[
            :-extraBytes
        ]  # Trim the extra bytes# Convert the byte data into a NumPy array of 3-byte chunks
    bs = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)

    # Convert to 32-bit integers while preserving sign
    intData = (
        bs[:, 0].astype(np.int32)
        | (bs[:, 1].astype(np.int32) << 8)
        | (bs[:, 2].astype(np.int32) << 16)
    )

    # Handle negative values (24-bit signed integers)
    intData = np.where(intData & 0x800000, intData | ~0xFFFFFF, intData)

    return intData


def generateSpectograph(
    info: WAVInfo, windowDuration=0.1, resolution_hz=10, verbose=False
):
    match info.bitsPerSample:
        case 16:
            dtype = np.int16
        case 32:
            dtype = np.int32
        case 64:
            dtype = np.int64
        case 8:
            dtype = np.int8
        case 24:
            data = bytesTo24Bit(info.data)
        case _:
            raise ValueError(f"Unsupported bits per sample: {info.bitsPerSample}")

    if info.bitsPerSample != 24:
        dtype = np.dtype(dtype).newbyteorder("<")
        # Check if data is a multiple of dtype size
        if len(info.data) % dtype.itemsize != 0:
            print(
                f"Warning: Data length {len(info.data)} is not a multiple of {dtype.itemsize}. Trimming the last few bytes."
            )
            info.data = info.data[: len(info.data) - (len(info.data) % dtype.itemsize)]
        data = np.frombuffer(info.data, dtype=dtype)

    # Window function application of fft to each 0.1 part of the data
    windowSize = int(windowDuration * info.sampleFreq)
    overlap = int(windowSize * 0.5)

    if verbose:
        print(f"""
        Window duration: {windowDuration}
        Window size: {windowSize}
        Overlap: {overlap}""")

    freq, times, Zxx = stft(
        data,
        fs=info.sampleFreq,
        window="hann",
        nperseg=windowSize,
        noverlap=overlap,
        boundary=None,
    )

    if verbose:
        print(f"""
        Number of frequencies: {len(freq)}
        Number of time points: {len(times)}
        Number of Zxx points: {len(Zxx)}
        Shape of Zxx: {Zxx.shape}
        """)
    times = (times * 1000).astype(int)
    # freq = quantizeFreqs(freq, resolution_hz=resolution_hz)
    freq = np.array([quantizeFreq9Bit(f) for f in freq])
    return freq, times, abs(Zxx), data, overlap


def downsample(info: WAVInfo, factor: int, verbose=False) -> WAVInfo:
    if factor <= 1:
        return info

    # Calculate the new sampling frequency
    newSampleFreq = info.sampleFreq // factor

    # Apply lowpass filter before downsampling
    # cutoff = newSampleFreq / 2
    info = lowpassFilter(info, 5000)

    if verbose:
        print(f"Downsampling by factor of {factor}...")

    # Convert data from bytes to numpy array
    data = np.frombuffer(info.data, dtype=np.int16)

    # Downsample the data
    data = data[::factor]

    # Convert back to bytes
    info.data = data.astype(np.int16).tobytes()

    # Update the sample frequency and byte rate
    info.sampleFreq = newSampleFreq
    info.bytesSec = (
        info.sampleFreq * info.bitsPerSample * (1 if info.mono else 2) // 8
    )  # Correctly calculate bytes per second

    if verbose:
        print("Downsampling complete.")
        printInfo(info)
    return info


def downmixToMono(info: WAVInfo, verbose=False) -> WAVInfo:
    if info.mono:
        return info
    if verbose:
        print("Downmixing stereo to mono...")

    if info.bitsPerSample == 16:
        dtype = np.int16
    elif info.bitsPerSample == 32:
        dtype = np.int32
    elif info.bitsPerSample == 64:
        dtype = np.int64
    elif info.bitsPerSample == 8:
        dtype = np.int8
    elif info.bitsPerSample == 24:
        dtype = np.int32
        data = bytesTo24Bit(info.data)
    else:
        raise ValueError(f"Unsupported bits per sample: {info.bitsPerSample}")

    if info.bitsPerSample != 24:
        # Check if data is a multiple of dtype size
        dsize = np.dtype(dtype).itemsize
        if len(info.data) % dsize != 0:
            print(
                f"Warning: Data length {len(info.data)} is not a multiple of {dsize}. Trimming the last few bytes."
            )
            info.data = info.data[: len(info.data) - (len(info.data) % dsize)]
        data = np.frombuffer(info.data, dtype=dtype)

    if len(data) % 2 != 0:
        if verbose:
            print("Warning: Data length is not even, removing the last sample...")
        data = data[:-1]  # Remove the last sample to make it even

    # Downmix stereo to mono
    data = (data[::2] + data[1::2]) // 2
    info.data = data.astype(dtype).tobytes()

    # Update WAVInfo fields for mono
    info.mono = True
    info.bytesSec //= 2
    info.blockAlign //= 2

    if verbose:
        print("Downmixing complete.")
        printInfo(info)
    return info


def lowpassFilter(info: WAVInfo, cutoff: float, verbose=False) -> WAVInfo:
    if verbose:
        print(f"Applying lowpass filter with cutoff frequency of {cutoff} Hz...")

    # Design the Butterworth filter
    nyquist = 0.5 * info.sampleFreq
    if nyquist == 0:
        return info
    normal_cutoff = cutoff / nyquist
    b, a = butter(4, normal_cutoff, btype="low", analog=False)

    # Convert data from bytes to numpy array
    data = np.frombuffer(info.data, dtype=np.int16)

    # Apply the filter
    filtered_data = lfilter(b, a, data)

    # Convert back to 16-bit PCM
    filtered_data = np.clip(
        filtered_data, -32768, 32767
    )  # Ensure values are within valid range
    info.data = filtered_data.astype(np.int16).tobytes()

    if verbose:
        print("Lowpass filter complete.")
        printInfo(info)
    return info


def preprocess(info: WAVInfo, downmix=True, downsampleFactor=1, verbose=False):
    if downmix:
        info = downmixToMono(info, verbose=verbose)
    if downsampleFactor > 1:
        info = downsample(info, downsampleFactor, verbose=verbose)

    return info


def printInfo(info: WAVInfo):
    print(f"""RIFF: {info.rif}
Size: {info.size}
Descr: {info.descr}
Fmt: {info.fmt}
Section size: {info.sectionSize}
Type format: {info.typeFormat}
Mono: {info.mono}
Sample frequency: {info.sampleFreq}
Bytes per second: {info.bytesSec}
Block align: {info.blockAlign}
Bits per sample: {info.bitsPerSample}
Data descr: {info.dataDescr}
Data chunk size: {info.dataChunkSize}
Data size: {len(info.data)}
Length: {datetime.fromtimestamp(len(info.data) / info.bytesSec).strftime("%M:%S")}""")
