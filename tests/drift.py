import threading
import time
import os
import json
from typing import Optional, Sequence, Any, List, Tuple

import numpy as np
import phobos


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
    archive_path = phobos.archive.new()  # expected to return a directory path
    archive_path = os.fspath(archive_path)
    os.makedirs(archive_path, exist_ok=True)

    data_file = os.path.join(archive_path, "flux_record.npz")
    meta_file = os.path.join(archive_path, "flux_record_meta.json")

    np.savez_compressed(data_file, times=times_rel, fluxes=stacked)
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved data to: {data_file}")
    print(f"Saved metadata to: {meta_file}")


if __name__ == "__main__":
    # Example usage: adjust interval, crop_centers and crop_size as needed.
    main(interval=1.0, crop_centers=None, crop_size=None)