from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import sosfilt

from core.preprocess import build_butter_sos, trim_and_filter


def _make_df(fs: float = 1000.0, duration: float = 1.0) -> tuple:
    t = np.arange(0, duration, 1.0 / fs)
    df = pd.DataFrame({"time": t, "ch": np.sin(2 * np.pi * 50 * t)})
    return df, fs


def test_build_butter_sos_lowpass():
    fs = 1000.0
    sos = build_butter_sos("Lowpass", 4, 100.0, fs)
    t = np.linspace(0, 1, int(fs), endpoint=False)
    sig = np.sin(2 * np.pi * 300 * t)
    out = sosfilt(sos, sig)
    assert np.std(out) / np.std(sig) < 0.1  # > 20 dB attenuation


def test_build_butter_sos_highpass():
    fs = 1000.0
    sos = build_butter_sos("Highpass", 4, 200.0, fs)
    t = np.linspace(0, 1, int(fs), endpoint=False)
    sig = np.sin(2 * np.pi * 20 * t)
    out = sosfilt(sos, sig)
    assert np.std(out) / np.std(sig) < 0.1


def test_build_butter_sos_bandpass():
    fs = 1000.0
    sos = build_butter_sos("Bandpass", 4, [80.0, 120.0], fs)
    t = np.linspace(0, 1, int(fs), endpoint=False)
    sig_in = np.sin(2 * np.pi * 100 * t)
    sig_out = np.sin(2 * np.pi * 300 * t)
    assert sosfilt(sos, sig_in).std() > 0.5  # passband passes
    assert sosfilt(sos, sig_out).std() < 0.1  # stopband attenuated


def test_trim_and_filter_no_filter():
    df, fs = _make_df()
    proc = trim_and_filter(df, 0.2, 0.8, "None", 4, None, fs)
    assert proc["time"].min() >= 0.2
    assert proc["time"].max() <= 0.8
    orig = df[(df["time"] >= 0.2) & (df["time"] <= 0.8)]["ch"].reset_index(drop=True)
    np.testing.assert_array_equal(proc["ch"].values, orig.values)


def test_trim_and_filter_trims_time():
    df, fs = _make_df()
    proc = trim_and_filter(df, 0.3, 0.7, "None", 4, None, fs)
    assert proc["time"].min() >= 0.3
    assert proc["time"].max() <= 0.7


def test_trim_and_filter_applies_lowpass():
    df, fs = _make_df(duration=2.0)
    # Original signal is 50 Hz; filter at 20 Hz should attenuate it
    proc = trim_and_filter(df, 0.0, 2.0, "Lowpass", 4, 20.0, fs)
    assert proc["ch"].std() < df["ch"].std() * 0.1
