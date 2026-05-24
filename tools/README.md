# tools/

Standalone Python utilities for preparing data before loading into the app.
Run these directly in a Python script or interactively (Jupyter, REPL).

Activate the project environment first:
```bash
source .venv/bin/activate
```

---

## format_converter — reformat non-standard files

```python
from tools.format_converter import from_delimited, from_excel, rename_columns, save_csv

# Tab-separated file with a non-standard time column name
df, err = from_delimited("run1.tsv", sep="\t", time_col="t_sec")

# Semicolon-separated (common European CSV) with unit scaling (mV → V)
df, err = from_delimited("run2.csv", sep=";", unit_scales={"ch0": 0.001, "ch1": 0.001})

# Excel workbook
df, err = from_excel("results.xlsx", sheet="Test 3", time_col="Time(s)")

# Rename columns after loading
df, err = rename_columns(df, {"ch0": "force", "ch1": "acc_1", "ch2": "acc_2"})

# Save ready for the app
err = save_csv(df, "data/input/run1_converted.csv")
```

> Excel support requires `openpyxl`: `pip install openpyxl`

---

## channel_math — derived channels

```python
from tools.channel_math import add_channel, remove_channel, list_channels

print(list_channels(df))           # ['force', 'acc_1', 'acc_2']

# Difference channel
df, err = add_channel(df, "acc_diff", "acc_1 - acc_2")

# Scale a channel (N → kN)
df, err = add_channel(df, "force_kN", "force * 0.001")

# Average
df, err = add_channel(df, "acc_avg", "(acc_1 + acc_2) / 2")

# Remove the original after deriving
df, err = remove_channel(df, "force")

err = save_csv(df, "data/input/run1_derived.csv")
```

---

## downsample — reduce sample rate

```python
from tools.downsample import downsample

# Integer factor (1024 Hz → 256 Hz, factor = 4) — recommended
df_low, err = downsample(df, target_fs=256.0)

# Non-integer ratio — use FFT resampling
df_low, err = downsample(df, target_fs=100.0, method="resample")

err = save_csv(df_low, "data/input/run1_256Hz.csv")
```

---

## time_sync — align datasets with different start times

```python
from tools.time_sync import sync_and_merge, trim_to_overlap
from core.data_loader import load_csv

df_a, _ = load_csv("sensor_a.csv")   # started at t=0.0 s
df_b, _ = load_csv("sensor_b.csv")   # started at t=2.3 s

# Just trim each to the shared window, keep separate
trimmed, err = trim_to_overlap([df_a, df_b])

# Or trim and merge into one DataFrame on the nearest timestamp
merged, err = sync_and_merge([df_a, df_b], tol_s=5e-4)

err = save_csv(merged, "data/input/run_synced.csv")
```
