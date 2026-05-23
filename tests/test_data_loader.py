from __future__ import annotations

import io

import numpy as np

from core.data_loader import load_csv, compute_sample_rate, compute_summary


def test_load_csv_returns_dataframe(sample_df):
    assert sample_df is not None
    assert len(sample_df) > 1


def test_load_csv_time_column_variants():
    for col in ["TIME", "t", "T"]:
        content = f"{col},ch1\n0.0,1.0\n0.001,2.0\n"
        df, err = load_csv(io.StringIO(content))
        assert err is None, f"Failed for column '{col}': {err}"
        assert "time" in df.columns


def test_load_csv_monotonic_first_column():
    content = "x_pos,ch1\n0.0,1.0\n0.001,2.0\n"
    df, err = load_csv(io.StringIO(content))
    assert err is None
    assert "time" in df.columns


def test_load_csv_returns_error_on_bad_file():
    content = "not_time,ch1\nfoo,bar\nbaz,qux\n"
    df, err = load_csv(io.StringIO(content))
    assert df is None
    assert err is not None


def test_load_csv_error_on_single_row():
    content = "time,ch1\n0.0,1.0\n"
    df, err = load_csv(io.StringIO(content))
    assert df is None
    assert err is not None


def test_compute_sample_rate_accuracy():
    t = np.linspace(0.0, 1.0, 1001)   # 1000 equal intervals → 1000 Hz
    fs = compute_sample_rate(t)
    assert abs(fs - 1000.0) < 0.01


def test_compute_summary_keys(sample_df):
    channels = [c for c in sample_df.columns if c != "time"]
    input_ch, output_chs = channels[0], channels[1:]
    rows = compute_summary(sample_df, input_ch, output_chs)
    assert len(rows) > 0
    required = {"Channel", "Samples", "Sample Rate (Hz)", "Duration (s)", "RMS"}
    for row in rows:
        for key in required:
            assert key in row, f"Key '{key}' missing from summary row"
