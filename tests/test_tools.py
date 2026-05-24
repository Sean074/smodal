from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(fs: float = 1000.0, duration: float = 1.0, t_offset: float = 0.0) -> pd.DataFrame:
    n = int(fs * duration)
    t = np.arange(n) / fs + t_offset
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "time": t,
            "ch_a": np.sin(2 * np.pi * 10 * t),
            "ch_b": rng.normal(0, 0.1, n),
        }
    )


# ---------------------------------------------------------------------------
# format_converter
# ---------------------------------------------------------------------------


class TestFormatConverter:
    def test_from_delimited_tsv(self, tmp_path):
        from tools.format_converter import from_delimited

        src = tmp_path / "data.tsv"
        src.write_text("t_sec\tch_a\tch_b\n0.0\t1.0\t2.0\n0.001\t1.1\t2.1\n")
        df, err = from_delimited(str(src), sep="\t", time_col="t_sec")

        assert err is None
        assert "time" in df.columns
        assert list(df["time"]) == [0.0, 0.001]

    def test_from_delimited_auto_time_detect(self, tmp_path):
        from tools.format_converter import from_delimited

        src = tmp_path / "data.csv"
        src.write_text("Time,ch_a\n0.0,1.0\n0.001,1.1\n")
        df, err = from_delimited(str(src), sep=",")

        assert err is None
        assert "time" in df.columns

    def test_from_delimited_unit_scales(self, tmp_path):
        from tools.format_converter import from_delimited

        src = tmp_path / "data.csv"
        src.write_text("time,force\n0.0,1000.0\n0.001,2000.0\n")
        df, err = from_delimited(str(src), sep=",", unit_scales={"force": 0.001})

        assert err is None
        assert pytest.approx(df["force"].iloc[0]) == 1.0

    def test_from_delimited_missing_time_col_error(self, tmp_path):
        from tools.format_converter import from_delimited

        src = tmp_path / "data.csv"
        src.write_text("t_sec\tch_a\n0.0\t1.0\n0.001\t1.1\n")
        _, err = from_delimited(str(src), sep="\t", time_col="nonexistent")

        assert err is not None
        assert "nonexistent" in err

    def test_rename_columns(self):
        from tools.format_converter import rename_columns

        df = _make_df()
        df_r, err = rename_columns(df, {"ch_a": "force", "ch_b": "acc_1"})

        assert err is None
        assert "force" in df_r.columns
        assert "acc_1" in df_r.columns
        assert "ch_a" not in df_r.columns

    def test_rename_columns_rejects_time(self):
        from tools.format_converter import rename_columns

        df = _make_df()
        _, err = rename_columns(df, {"time": "t"})

        assert err is not None

    def test_rename_columns_missing_source(self):
        from tools.format_converter import rename_columns

        df = _make_df()
        _, err = rename_columns(df, {"nonexistent": "new"})

        assert err is not None

    def test_save_csv_roundtrip(self, tmp_path):
        from core.data_loader import load_csv
        from tools.format_converter import save_csv

        df = _make_df()
        out = tmp_path / "out.csv"
        err = save_csv(df, str(out))

        assert err is None
        df2, err2 = load_csv(str(out))
        assert err2 is None
        assert list(df2.columns) == list(df.columns)
        assert len(df2) == len(df)


# ---------------------------------------------------------------------------
# channel_math
# ---------------------------------------------------------------------------


class TestChannelMath:
    def test_list_channels(self):
        from tools.channel_math import list_channels

        df = _make_df()
        assert list_channels(df) == ["ch_a", "ch_b"]

    def test_add_channel_difference(self):
        from tools.channel_math import add_channel

        df = _make_df()
        df2, err = add_channel(df, "diff", "ch_a - ch_b")

        assert err is None
        assert "diff" in df2.columns
        np.testing.assert_allclose(df2["diff"].values, df["ch_a"].values - df["ch_b"].values)

    def test_add_channel_scale(self):
        from tools.channel_math import add_channel

        df = _make_df()
        df2, err = add_channel(df, "ch_a_kN", "ch_a * 0.001")

        assert err is None
        np.testing.assert_allclose(df2["ch_a_kN"].values, df["ch_a"].values * 0.001)

    def test_add_channel_does_not_mutate_input(self):
        from tools.channel_math import add_channel

        df = _make_df()
        original_cols = list(df.columns)
        add_channel(df, "diff", "ch_a - ch_b")

        assert list(df.columns) == original_cols

    def test_add_channel_bad_expression(self):
        from tools.channel_math import add_channel

        df = _make_df()
        _, err = add_channel(df, "bad", "nonexistent_col * 2")

        assert err is not None

    def test_add_channel_rejects_time_overwrite(self):
        from tools.channel_math import add_channel

        df = _make_df()
        _, err = add_channel(df, "time", "ch_a")

        assert err is not None

    def test_remove_channel(self):
        from tools.channel_math import remove_channel

        df = _make_df()
        df2, err = remove_channel(df, "ch_b")

        assert err is None
        assert "ch_b" not in df2.columns
        assert "ch_a" in df2.columns

    def test_remove_channel_rejects_time(self):
        from tools.channel_math import remove_channel

        df = _make_df()
        _, err = remove_channel(df, "time")

        assert err is not None

    def test_remove_channel_missing(self):
        from tools.channel_math import remove_channel

        df = _make_df()
        _, err = remove_channel(df, "nonexistent")

        assert err is not None


class TestChannelMathSecurity:
    """Verify that add_channel blocks code-injection expressions."""

    def _df(self):
        return _make_df()

    def _blocked(self, expression):
        from tools.channel_math import add_channel

        df = self._df()
        df_out, err = add_channel(df, "bad", expression)
        assert err is not None, f"Expected error for expression: {expression!r}"
        assert df_out is df or df_out.equals(df)

    def test_blocks_dunder_import(self):
        self._blocked("__import__('os').system('echo hi')")

    def test_blocks_dunder_class(self):
        self._blocked("__class__")

    def test_blocks_import_keyword(self):
        self._blocked("import os")

    def test_blocks_exec(self):
        self._blocked("exec('1')")

    def test_blocks_eval(self):
        self._blocked("eval('1')")

    def test_blocks_open(self):
        self._blocked("open('/etc/passwd')")

    def test_blocks_subprocess(self):
        self._blocked("subprocess.run(['ls'])")

    def test_valid_expression_still_works(self):
        from tools.channel_math import add_channel

        df = _make_df()
        df_out, err = add_channel(df, "diff", "ch_a - ch_b")
        assert err is None
        assert "diff" in df_out.columns


# ---------------------------------------------------------------------------
# downsample
# ---------------------------------------------------------------------------


class TestDownsample:
    def test_decimate_halves_length(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0, duration=1.0)
        df2, err = downsample(df, target_fs=500.0)

        assert err is None
        assert abs(len(df2) - len(df) // 2) <= 2  # allow rounding
        assert df2["time"].is_monotonic_increasing

    def test_decimate_quarter_rate(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0, duration=1.0)
        df2, err = downsample(df, target_fs=250.0)

        assert err is None
        assert abs(len(df2) - len(df) // 4) <= 2

    def test_resample_arbitrary_ratio(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0, duration=1.0)
        df2, err = downsample(df, target_fs=300.0, method="resample")

        assert err is None
        assert len(df2) == 300
        assert df2["time"].is_monotonic_increasing

    def test_rejects_upsample(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0)
        _, err = downsample(df, target_fs=2000.0)

        assert err is not None

    def test_rejects_non_integer_decimate(self):
        from tools.downsample import downsample

        # 1000 / 300 = 3.333 — clearly non-integer, should be rejected
        df = _make_df(fs=1000.0)
        _, err = downsample(df, target_fs=300.0, method="decimate")

        assert err is not None

    def test_unknown_method(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0)
        _, err = downsample(df, target_fs=500.0, method="unknown")

        assert err is not None

    def test_preserves_all_channels(self):
        from tools.downsample import downsample

        df = _make_df(fs=1000.0)
        df2, err = downsample(df, target_fs=500.0)

        assert err is None
        assert set(df2.columns) == set(df.columns)


# ---------------------------------------------------------------------------
# time_sync
# ---------------------------------------------------------------------------


class TestTimeSync:
    def _offset_df(self, t_offset: float, fs: float = 1000.0, duration: float = 1.0) -> pd.DataFrame:
        return _make_df(fs=fs, duration=duration, t_offset=t_offset)

    def test_trim_to_overlap_basic(self):
        from tools.time_sync import trim_to_overlap

        df_a = self._offset_df(0.0)  # 0.0 – 0.999 s
        df_b = self._offset_df(0.3)  # 0.3 – 1.299 s

        trimmed, err = trim_to_overlap([df_a, df_b])

        assert err is None
        assert len(trimmed) == 2
        # Overlap should be 0.3 – 0.999 s
        for df in trimmed:
            assert df["time"].iloc[0] >= 0.3 - 1e-9
            assert df["time"].iloc[-1] <= 0.999 + 1e-9

    def test_trim_to_overlap_no_overlap_error(self):
        from tools.time_sync import trim_to_overlap

        df_a = self._offset_df(0.0, duration=0.5)  # 0.0 – 0.499 s
        df_b = self._offset_df(1.0)  # 1.0 – 1.999 s

        _, err = trim_to_overlap([df_a, df_b])

        assert err is not None

    def test_trim_requires_two_dfs(self):
        from tools.time_sync import trim_to_overlap

        _, err = trim_to_overlap([_make_df()])

        assert err is not None

    def test_sync_and_merge_columns(self):
        from tools.time_sync import sync_and_merge

        df_a = self._offset_df(0.0)
        df_b = self._offset_df(0.3)

        merged, err = sync_and_merge([df_a, df_b], tol_s=2e-3)

        assert err is None
        assert "time" in merged.columns
        # ch_a and ch_b from df_a are present; df_b columns suffixed
        assert "ch_a" in merged.columns
        assert "ch_b" in merged.columns

    def test_sync_and_merge_length_within_overlap(self):
        from tools.time_sync import sync_and_merge

        df_a = self._offset_df(0.0, duration=1.0)
        df_b = self._offset_df(0.3, duration=1.0)

        merged, err = sync_and_merge([df_a, df_b], tol_s=2e-3)

        assert err is None
        # Overlap is ~0.7 s at 1000 Hz → ~700 rows
        assert 650 < len(merged) < 750

    def test_sync_preserves_monotonic_time(self):
        from tools.time_sync import sync_and_merge

        df_a = self._offset_df(0.0)
        df_b = self._offset_df(0.2)

        merged, err = sync_and_merge([df_a, df_b])

        assert err is None
        assert merged["time"].is_monotonic_increasing
