# Create a modal response for the val_cantilever_modes sample to run in SIMO
# Used sbeam model
# This is to help develop the modal analysis program.
# Aim is to take the sbeam results at select nodes and locations and create fake test data.
# The test data is the free response from an impulse, there is noise and there are non-real modes.

import numpy as np
import pandas as pd

# --- Parameters ---
duration = 15
sample_rate = 200
dt = 1 / sample_rate
time = np.arange(0, duration, dt)
noise_level = 0.5   # noise std as fraction of each signal's RMS (0 = no noise)
rng = np.random.default_rng(seed=42)

# --- Mode definitions ---

# Modes for Node 11
modes_Node11 = {
        "Mode1": {
            "id": "Mode 1",
            "freq_Hz": 2.578411E+00,
            "damping_cr": 2.0,
            "amplitude": 2.257334E-02},
        "Mode2": {
            "id": "Mode 2",
            "freq_Hz": 1.615915E+01,
            "damping_cr": 1.5,
            "amplitude": -2.257479E-02},
        "Mode3": {
            "id": "Mode 3",
            "freq_Hz": 4.525610E+01,
            "damping_cr": 1.5,
            "amplitude": -2.258463E-02},
        "ModeNoise": {
            "id": "Mode Noise",
            "freq_Hz": 1.55E+01,
            "damping_cr": 1.0,
            "amplitude": -2.257479E-03}
        }

# Modes for Node 8
modes_Node8 = {
        "Mode1": {
            "id": "Mode 1",
            "freq_Hz": 2.578411E+00,
            "damping_cr": 2.0,
            "amplitude": 1.333805E-02},
        "Mode2": {
            "id": "Mode 2",
            "freq_Hz": 1.615915E+01,
            "damping_cr": 4.0,
            "amplitude": 7.157391E-03},
        "Mode3": {
            "id": "Mode 3",
            "freq_Hz": 4.525610E+01,
            "damping_cr": 1.5,
            "amplitude": 1.484785E-02},
        "ModeNoise": {
            "id": "Mode Noise",
            "freq_Hz": 1.6E+01,
            "damping_cr": 1.0,
            "amplitude": 5.257479E-03}
        }

# Modes for Node 6
modes_Node6 = {
        "Mode1": {
            "id": "Mode 1",
            "freq_Hz": 2.578411E+00,
            "damping_cr": 2.0,
            "amplitude": 7.664172E-03},
        "Mode2": {
            "id": "Mode 2",
            "freq_Hz": 1.615915E+01,
            "damping_cr": 1.0,
            "amplitude": 1.611087E-02},
        "Mode3": {
            "id": "Mode 3",
            "freq_Hz": 4.525610E+01,
            "damping_cr": 1.5,
            "amplitude": -4.448534E-04},
        "ModeNoise": {
            "id": "Mode Noise",
            "freq_Hz": 3.5E+01,
            "damping_cr": 5.0,
            "amplitude": 1.0E-03}
        }

# --- Solver ---

def impulse_response(modes, time):
    """Displacement (m) at a node from unit impulse via modal superposition.

    h(t) = (1/ωd) · exp(−ζωn·t) · sin(ωd·t)   [unit impulse SDOF IRF]
    x(t) = Σ amplitude_i · h_i(t)
    """
    x = np.zeros(len(time))
    for mode in modes.values():
        wn = 2 * np.pi * mode["freq_Hz"]
        zeta = mode["damping_cr"] / 100.0
        wd = wn * np.sqrt(1.0 - zeta ** 2)
        h = (1.0 / wd) * np.exp(-zeta * wn * time) * np.sin(wd * time)
        x += mode["amplitude"] * h
    return x

# --- Compute displacement at each node ---

x_Node11 = impulse_response(modes_Node11, time)
x_Node8  = impulse_response(modes_Node8,  time)
x_Node6  = impulse_response(modes_Node6,  time)

# --- Convert displacement (m) to acceleration (g's) ---
# Double-differentiate numerically then divide by 9.81 m/s²

def disp_to_accel_g(x, dt):
    a_ms2 = np.gradient(np.gradient(x, dt), dt)
    return a_ms2 / 9.81

a_Node11_g = disp_to_accel_g(x_Node11, dt)
a_Node8_g  = disp_to_accel_g(x_Node8,  dt)
a_Node6_g  = disp_to_accel_g(x_Node6,  dt)

# --- Input force: unit impulse (integral = 1 N·s) ---

force = np.zeros(len(time))
force[0] = float(sample_rate)   # 1/dt so ∫F dt = 1 N·s

# --- Add noise ---

def add_noise(signal, level, rng):
    if level <= 0.0:
        return signal
    std = level * np.sqrt(np.mean(signal ** 2))
    return signal + rng.normal(0.0, std, len(signal))

a_Node11_g = add_noise(a_Node11_g, noise_level, rng)
a_Node8_g  = add_noise(a_Node8_g,  noise_level, rng)
a_Node6_g  = add_noise(a_Node6_g,  noise_level, rng)

# --- Output CSV ---

out_path = "data/input/val_cantilever_impulse.csv"

df_out = pd.DataFrame({
    "time":          time,
    "force_N":       force,
    "Node11_accel_g": a_Node11_g,
    "Node8_accel_g":  a_Node8_g,
    "Node6_accel_g":  a_Node6_g,
})

df_out.to_csv(out_path, index=False)
print(f"Saved {len(df_out)} samples to {out_path}")
