import numpy as np


def encodeAddress32Bit(address) -> np.int32:
    anchor, freq, delta = address
    delta = int(delta)
    # anchor is 9 bits, freq is 9 bits, delta is 14 bits
    return (int(anchor) << 23) | (int(freq) << 14) | delta


def decodeAddress32Bit(encoded):
    anchor = (int(encoded) >> 23) & 0x1FF
    freq = (int(encoded) >> 14) & 0x1FF
    delta = int(encoded) & 0x3FFF
    return anchor, freq, delta


def encodeCouple64Bit(couple) -> np.int64:
    anchorTime, songId = couple
    # anchorTime is 32 bits, songId is 32 bits
    return (int(anchorTime) << 32) | songId


def decodeCouple64Bit(encoded):
    anchorTime = (int(encoded) >> 32) & 0xFFFFFFFF
    songId = int(encoded) & 0xFFFFFFFF
    return anchorTime, songId
