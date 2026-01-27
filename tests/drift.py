import threading
import time
import os
import json
from typing import Optional, Sequence, Any, List, Tuple

import numpy as np
import phobos
import matplotlib.pyplot as plt

def _capture_loop(cam: Any,
                  stop_event: threading.Event,
                  interval: float,
                  out_list: List[np.ndarray],
                  times_list: List[float],
                  crop_centers: Optional[Sequence[Tuple[int, int]]] = None,
                  crop_size: Optional[int] = None) -> None:
    """
    Background loop capturing integrated outputs from the camera.

    Parameters
    ----------
    cam : object
        Camera object exposing get_outputs(crop_centers=..., crop_sizes=...).
    stop_event : threading.Event
        Event used to stop the loop.
    interval : float
        Time between captures in seconds.
    out_list : list
        List that will be appended with numpy arrays of outputs.
    times_list : list
        List that will be appended with timestamps (POSIX seconds).
    crop_centers : sequence of tuples, optional
        Crop centers passed to cam.get_outputs if provided.
    crop_size : int, optional
        Crop size passed to cam.get_outputs if provided.
    """
    while not stop_event.is_set():
        t = time.time()
        try:
            if crop_centers is not None or crop_size is not None:
                outputs = cam.get_outputs(crop_centers=crop_centers, crop_sizes=crop_size)
            else:
                outputs = cam.get_outputs()
            outputs_arr = np.asarray(outputs, dtype=float)
        except Exception:
            # on any read error, record NaNs to keep timeline consistent
            outputs_arr = np.full((0,), np.nan)
        out_list.append(outputs_arr)
        times_list.append(t)
        # sleep in small increments to remain responsive to stop_event
        slept = 0.0
        while slept < interval and not stop_event.is_set():
            time.sleep(min(0.1, interval - slept))
            slept += min(0.1, interval - slept)


def main(interval: float = 1.0,
         crop_centers: Optional[Sequence[Tuple[int, int]]] = None,
         crop_size: Optional[int] = None) -> None:
    """
    Record integrated flux on each output every `interval` seconds until the user presses Enter.
    The collected data and metadata are saved in the archive location returned by phobos.archive.new().

    Parameters
    ----------
    interval : float
        Sampling interval in seconds (default 1.0).
    crop_centers : sequence of (int, int), optional
        Crop centers forwarded to camera.get_outputs.
    crop_size : int, optional
        Crop size forwarded to camera.get_outputs.

    Example
    -------
    python3 scripts/record_flux.py
    """
    cam = phobos.Cred3()

    outputs: List[np.ndarray] = []
    timestamps: List[float] = []
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_capture_loop,
        args=(cam, stop_event, interval, outputs, timestamps, crop_centers, crop_size),
        daemon=True
    )
    thread.start()

    try:
        input("Recording... press Enter to stop and archive the data.\n")
    finally:
        stop_event.set()
        thread.join()

    if len(timestamps) == 0:
        print("No samples captured. Exiting.")
        return

    # normalize times to start at zero
    t0 = timestamps[0]
    times_rel = np.array(timestamps) - t0

    # stack outputs into 2D array (n_samples, n_outputs). pad short rows with NaN if needed.
    max_len = max(arr.size for arr in outputs)
    stacked = np.full((len(outputs), max_len), np.nan, dtype=float)
    for i, arr in enumerate(outputs):
        if arr.size > 0:
            stacked[i, : arr.size] = arr

    metadata = {
        "interval": interval,
        "n_samples": len(times_rel),
        "n_outputs": max_len,
        "crop_centers": crop_centers,
        "crop_size": crop_size,
        "record_start_unix": float(t0),
    }

    # get archive folder from phobos
    archive_path = phobos.archive.new(name="Drift Record")  # expected to return a directory path
    archive_path = os.fspath(archive_path)
    os.makedirs(archive_path, exist_ok=True)

    data_file = os.path.join(archive_path, "flux_record.npz")
    meta_file = os.path.join(archive_path, "flux_record_meta.json")

    np.savez_compressed(data_file, times=times_rel, fluxes=stacked)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    plot_flux_timeseries(archive_path=str(archive_path))

    print(f"Saved data to: {data_file}")
    print(f"Saved metadata to: {meta_file}")

def plot_flux_timeseries(times: Optional[np.ndarray] = None,
                         fluxes: Optional[np.ndarray] = None,
                         archive_path: Optional[str] = None,
                         npz_filename: str = "flux_record.npz",
                         n_signals: int = 4,
                         out_filename: str = "flux_timeseries.png",
                         show: bool = True):
    """
    Plot flux time series for the first `n_signals` outputs and their mean.

    This function can either accept `times` and `fluxes` arrays directly, or it can
    load them from an archive directory by providing `archive_path`. When `archive_path`
    is given the function will try to load the NumPy archive named `npz_filename`
    (expected keys: 'times' or 'times_sec', and 'fluxes').

    Parameters
    ----------
    times : Optional[np.ndarray]
        1D array of time stamps (seconds, relative or absolute). If None and
        `archive_path` is provided, times will be loaded from the archive.
    fluxes : Optional[np.ndarray]
        2D array of shape (n_samples, n_outputs) containing integrated fluxes.
        If None and `archive_path` is provided, fluxes will be loaded from the archive.
    archive_path : Optional[str]
        Path to the archive directory containing the numpy data file.
    npz_filename : str, optional
        Name of the .npz file inside the archive (default "flux_record.npz").
    n_signals : int, optional
        Number of individual outputs to plot (default 4). If there are fewer outputs,
        all available outputs are plotted.
    out_filename : str, optional
        Name of the saved figure file inside the archive (default "flux_timeseries.png").
    show : bool, optional
        If True (default), call plt.show() after plotting.

    Returns
    -------
    tuple
        (fig, ax) matplotlib figure and axis objects.

    Examples
    --------
    >>> # Load from archive
    >>> fig, ax = plot_flux_timeseries(archive_path='/data/archive/2025-12-19/001')
    >>> # Or provide arrays directly
    >>> fig, ax = plot_flux_timeseries(times=times_arr, fluxes=flux_arr)
    """
    # If archive_path is provided, try to load data from it
    if archive_path is not None:
        archive_path = os.fspath(archive_path)
        npz_path = os.path.join(archive_path, npz_filename)
        if not os.path.exists(npz_path):
            raise FileNotFoundError(f"Archive file not found: {npz_path}")
        with np.load(npz_path) as data:
            # Accept multiple possible key names for times
            if 'times' in data:
                times = data['times']
            elif 'times_sec' in data:
                times = data['times_sec']
            else:
                raise KeyError(f"No 'times' or 'times_sec' key found in {npz_path}")
            if 'fluxes' in data:
                fluxes = data['fluxes']
            elif 'fluxes' not in data:
                # try alternative key names
                keys = list(data.keys())
                raise KeyError(f"No 'fluxes' key found in {npz_path}. Keys: {keys}")

    if times is None or fluxes is None:
        raise ValueError("times and fluxes must be provided either directly or via archive_path")

    # Validate and normalize inputs
    times = np.asarray(times).ravel()
    fluxes = np.asarray(fluxes, dtype=float)
    if fluxes.ndim == 1:
        fluxes = fluxes[:, None]

    n_outputs = fluxes.shape[1]
    n_plot = min(n_signals, n_outputs)

    # Select outputs to plot (first n_plot)
    indices = list(range(n_plot))

    # Compute mean of plotted outputs (ignore NaNs)
    mean_flux = np.nanmean(fluxes[:, indices], axis=1)

    # Create plot
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for j, idx in enumerate(indices):
        ax.plot(times, fluxes[:, idx], label=f"Output {idx+1}", color=colors[j % len(colors)], alpha=0.85)
    ax.plot(times, mean_flux, label="Mean of plotted outputs", color="k", linewidth=2)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Integrated flux (ADU)")
    ax.set_title("Flux time series")
    ax.grid(True)
    ax.legend(loc="best")
    fig.tight_layout()

    # Save figure into archive if requested or if archive_path provided
    save_dir = archive_path
    if save_dir is None:
        try:
            save_dir = phobos.archive.new()
        except Exception:
            save_dir = None

    if save_dir is not None:
        save_dir = os.fspath(save_dir)
        os.makedirs(save_dir, exist_ok=True)
        out_path = os.path.join(save_dir, out_filename)
        fig.savefig(out_path, dpi=150)
        print(f"Plot saved to: {out_path}")

    if show:
        plt.show()

    return fig, ax


if __name__ == "__main__":
    main(interval=1.0, crop_centers=None, crop_size=None)