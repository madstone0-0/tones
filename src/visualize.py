from audio_proc import WAVInfo, generateSpectograph, preprocess
import matplotlib.pyplot as plt
import numpy as np


def visualizeSong(info: WAVInfo):
    data = np.frombuffer(
        info.data, dtype=np.int16 if info.bitsPerSample == 16 else np.int64
    )
    less_points = 10000
    if len(data) > less_points:
        data = data[:: len(data) // less_points]
    duration_ms = len(data) * 1000 / info.sampleFreq
    time_ms = np.linspace(0.0, duration_ms, len(data))
    plt.figure(figsize=(12, 6))
    plt.plot(time_ms, data)
    plt.xlabel("Time [ms]")
    plt.ylabel("Amplitude")
    plt.title("Waveform Visualization")
    plt.grid(True)
    plt.show()


def visualizeStrongestFrequencies(times, freqs):
    plt.figure(figsize=(10, 6))
    plt.scatter(times, freqs, marker="x", color="black")
    plt.xlabel("Time [ms]")
    plt.ylabel("Frequency [Hz]")
    plt.title("Strongest Frequencies")
    plt.yscale("log")  # Use log scale for frequency axis
    plt.ylim(20, 20000)  # Set y-axis limits to human hearing range
    plt.grid(True)


def visualizeSpectograph(freq, times, Zxx, data, overlap, windowSize, sampleFreq):
    # Plot the spectrogram
    plt.figure(figsize=(12, 8))

    if len(data) < 10000000:  # For shorter audio files
        plt.pcolormesh(times, freq, np.abs(Zxx), shading="gouraud")
        plt.title("STFT Magnitude")
        plt.ylabel("Frequency [Hz]")
        plt.xlabel("Time [ms]")
    else:  # For longer audio files
        plt.specgram(
            data,
            Fs=sampleFreq,
            NFFT=windowSize,
            noverlap=overlap,
            xextent=(times[0], times[-1]),
            cmap="viridis",
        )
        plt.title("Spectrogram")
        plt.ylabel("Frequency [Hz]")
        plt.xlabel("Time [ms]")

    plt.colorbar(label="Magnitude")
    return freq, times, Zxx


def visualizeSpectographFromInfo(info: WAVInfo, factor=1, freqRes=10.7):
    windowSize = int(info.sampleFreq / freqRes)
    windowDuration = windowSize / info.sampleFreq

    info = preprocess(info, downmix=True, downsampleFactor=factor)
    freq, times, Zxx, data, overlap = generateSpectograph(info, windowDuration)

    return visualizeSpectograph(
        freq, times, Zxx, data, overlap, windowSize, info.sampleFreq
    )
