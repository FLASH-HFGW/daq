#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime
from optparse import OptionParser

import matplotlib as mpl

mpl.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.titlesize": 10,
    "toolbar": "toolbar2",
})

print("DISPLAY =", os.environ.get("DISPLAY"))

# if os.environ.get("DISPLAY"):
#     os.environ.setdefault("QT_X11_NO_MITSHM", "1")
#     mpl.use("Qt5Agg", force=True)
# else:
#     mpl.use("Agg", force=True)

mpl.rcParams["figure.raise_window"] = False

import matplotlib.pyplot as plt
import numpy as np

import midas
import midas.client


def setup_iq_figure(grid=False):
    fig, axes = plt.subplots(
        2, 2,
        figsize=(14, 9),
        facecolor="#DEDEDE",
        constrained_layout=True,
    )

    ax_iq_time = axes[0, 0]
    ax_sum_time = axes[0, 1]
    ax_q_vs_i = axes[1, 0]
    ax_fft = axes[1, 1]

    ln_i, = ax_iq_time.plot([], [], linewidth=1.0, label="I")
    ln_q, = ax_iq_time.plot([], [], linewidth=1.0, label="Q")

    ln_sum, = ax_sum_time.plot([], [], linewidth=1.0, label="I+Q")

    ln_qi, = ax_q_vs_i.plot([], [], ".", markersize=2)

    ln_fft, = ax_fft.plot([], [], linewidth=1.0)

    ax_iq_time.set_title("I and Q vs time")
    ax_iq_time.set_xlabel("sample")
    ax_iq_time.set_ylabel("voltage [V]")
    ax_iq_time.legend(loc="best")

    ax_sum_time.set_title("I + Q vs time")
    ax_sum_time.set_xlabel("sample")
    ax_sum_time.set_ylabel("voltage [V]")

    ax_q_vs_i.set_title("IQ plane: Q vs I")
    ax_q_vs_i.set_xlabel("I [V]")
    ax_q_vs_i.set_ylabel("Q [V]")
    ax_q_vs_i.set_aspect("equal", adjustable="box")

    ax_fft.set_title("FFT of I + Q")
    ax_fft.set_xlabel("frequency [MHz]")
    ax_fft.set_ylabel("amplitude [V]")
    ax_fft.set_yscale("log")

    if grid:
        for ax in axes.ravel():
            ax.grid(True, alpha=0.3)

    try:
        from PyQt5 import QtCore
        mgr = plt.get_current_fig_manager()
        mgr.window.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
    except Exception:
        pass


    return {
        "fig": fig,
        "ax_iq_time": ax_iq_time,
        "ax_sum_time": ax_sum_time,
        "ax_q_vs_i": ax_q_vs_i,
        "ax_fft": ax_fft,
        "ln_i": ln_i,
        "ln_q": ln_q,
        "ln_sum": ln_sum,
        "ln_qi": ln_qi,
        "ln_fft": ln_fft,
    }


def decode_spec_bank(event, bank_name="SPEC", input_range=5.0, nch=8):
    u = np.asarray(event.banks[bank_name].data, dtype=np.uint16)

    # Bank WORD unsigned 0..65535 reinterpreted as signed int16.
    s = u.view(np.int16)

    nsamp = s.size // nch
    if nsamp <= 0:
        return None

    s = s[:nsamp * nch]
    frames = s.reshape(nsamp, nch)

    # int16 -> volt
    volt = frames.astype(np.float64) * (2.0 * input_range / 65536.0)

    return volt


def compute_fft(x, fs):
    x = np.asarray(x, dtype=np.float64)

    n = x.size
    if n < 2:
        return None, None

    x = x - np.mean(x)

    window = np.hanning(n)
    xw = x * window

    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.fft.rfft(xw)

    norm = np.sum(window) / 2.0
    amp = np.abs(spec) / norm
    amp[0] *= 0.5

    return freq, amp


def set_ylim_from_data(ax, y):
    ymin = float(np.min(y))
    ymax = float(np.max(y))

    if ymax == ymin:
        ymax = ymin + 1e-6

    margin = 0.1 * (ymax - ymin)
    ax.set_ylim(ymin - margin, ymax + margin)


def update_iq_plot(handles, i_data, q_data, fs, hmin, hmax):
    nsamp = min(i_data.size, q_data.size)
    if nsamp < 2:
        return False

    i_data = np.asarray(i_data[:nsamp], dtype=np.float64).copy()
    q_data = np.asarray(q_data[:nsamp], dtype=np.float64).copy()

    iq_sum = i_data + q_data

    smin = max(0, int(hmin))
    emax = min(int(hmax), nsamp)

    if emax <= smin:
        smin = 0
        emax = nsamp

    x = np.arange(smin, emax)

    i_view = i_data[smin:emax]
    q_view = q_data[smin:emax]
    sum_view = iq_sum[smin:emax]

    freq, amp = compute_fft(iq_sum, fs)
    if freq is None:
        return False

    freq_mhz = freq / 1e6

    # 1) I and Q in time
    handles["ln_i"].set_xdata(x)
    handles["ln_i"].set_ydata(i_view)

    handles["ln_q"].set_xdata(x)
    handles["ln_q"].set_ydata(q_view)

    handles["ax_iq_time"].set_xlim(float(x[0]), float(x[-1]))
    set_ylim_from_data(handles["ax_iq_time"], np.concatenate([i_view, q_view]))

    # 2) I + Q in time
    handles["ln_sum"].set_xdata(x)
    handles["ln_sum"].set_ydata(sum_view)

    handles["ax_sum_time"].set_xlim(float(x[0]), float(x[-1]))
    set_ylim_from_data(handles["ax_sum_time"], sum_view)

    # 3) Q vs I
    handles["ln_qi"].set_xdata(i_view)
    handles["ln_qi"].set_ydata(q_view)

    imin = float(np.min(i_view))
    imax = float(np.max(i_view))
    qmin = float(np.min(q_view))
    qmax = float(np.max(q_view))

    xmin = min(imin, qmin)
    xmax = max(imax, qmax)

    if xmax == xmin:
        xmax = xmin + 1e-6

    margin = 0.1 * (xmax - xmin)
    handles["ax_q_vs_i"].set_xlim(xmin - margin, xmax + margin)
    handles["ax_q_vs_i"].set_ylim(xmin - margin, xmax + margin)

    # 4) FFT of I + Q
    handles["ln_fft"].set_xdata(freq_mhz)
    handles["ln_fft"].set_ydata(amp)

    handles["ax_fft"].set_xlim(0.0, fs / 2.0 / 1e6)

    positive = amp[amp > 0]
    if positive.size > 0:
        handles["ax_fft"].set_ylim(
            float(np.min(positive) * 0.5),
            float(np.max(positive) * 2.0),
        )

    return True


def main(
    bank_name="SPEC",
    buffer_name="SYSTEM",
    i_channel=0,
    q_channel=1,
    nch=8,
    fs=5e6,
    input_range=5.0,
    hmin=0,
    hmax=1024,
    grid=False,
    verbose=False,
    update_period=1.0,
    save_png=None,
):
    event_before = 0
    last_update = 0.0

    # client = midas.client.MidasClient("iq_display_fft")
    client = midas.client.MidasClient(f"iq_display_fft_{os.getpid()}")
    buffer_handle = client.open_event_buffer(buffer_name, None, 1000000000)

    request_id = client.register_event_request(
        buffer_handle,
        event_id=-1,
        trigger_mask=-1,
        sampling_type=midas.GET_RECENT,
    )

    try:
        midas.bm_skip_event(buffer_handle)
    except AttributeError:
        pass

    plt.ion()

    handles = setup_iq_figure(grid=grid)
    fig = handles["fig"]

    try:
        fig.show()
    except Exception:
        pass

    print(f"Listening online on MIDAS buffer '{buffer_name}', bank '{bank_name}'")
    print(f"I channel = {i_channel}, Q channel = {q_channel}")
    print(f"fs={fs:g} Hz, input range +/-{input_range:g} V")
    print("IQ display running..., Ctrl-C to stop")

    try:
        while True:
            event = client.receive_event(buffer_handle, async_flag=True)

            if event is None:
                if os.environ.get("DISPLAY"):
                    plt.pause(0.05)
                else:
                    time.sleep(0.05)

                client.communicate(10)
                continue

            if event.header.is_midas_internal_event():
                if verbose:
                    print("Saw a special event")
                continue

            if bank_name not in event.banks:
                continue

            event_number = event.header.serial_number
            event_time = datetime.fromtimestamp(event.header.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            now = time.time()

            if now - last_update >= update_period:
                volt = decode_spec_bank(
                    event,
                    bank_name=bank_name,
                    input_range=input_range,
                    nch=nch,
                )

                if volt is None:
                    continue

                if i_channel < 0 or i_channel >= volt.shape[1]:
                    print(f"\nERROR: I channel {i_channel} outside range 0..{volt.shape[1] - 1}")
                    break

                if q_channel < 0 or q_channel >= volt.shape[1]:
                    print(f"\nERROR: Q channel {q_channel} outside range 0..{volt.shape[1] - 1}")
                    break

                i_data = volt[:, i_channel].copy()
                q_data = volt[:, q_channel].copy()

                updated = update_iq_plot(
                    handles=handles,
                    i_data=i_data,
                    q_data=q_data,
                    fs=fs,
                    hmin=hmin,
                    hmax=hmax,
                )

                if updated:
                    fig.suptitle(
                        f"{bank_name} Event: {event_number:d} at {event_time:s} | "
                        f"I=ch{i_channel}, Q=ch{q_channel}",
                        fontsize=10,
                        y=0.995,
                    )

                    fig.canvas.draw()
                    fig.canvas.flush_events()

                    if save_png:
                        fig.savefig(save_png, dpi=120)

                    last_update = now

                    print(
                        f"Event {event_number} | "
                        f"rate approx {float(event_number - event_before):.2f} Hz | "
                        f"I min/max={np.min(i_data):+.4f}/{np.max(i_data):+.4f} V | "
                        f"Q min/max={np.min(q_data):+.4f}/{np.max(q_data):+.4f} V",
                        end="\r",
                        flush=True,
                    )

                if verbose:
                    print("\n-----------------------")
                    print(
                        event.header.timestamp,
                        event_number,
                        "first raw:",
                        event.banks[bank_name].data[:10],
                    )
                    print(f"> I ch{i_channel}, first 5 samples [V] >", i_data[:5])
                    print(f"> Q ch{q_channel}, first 5 samples [V] >", q_data[:5])

                try:
                    midas.bm_skip_event(buffer_handle)
                except AttributeError:
                    pass

            event_before = event_number

            if os.environ.get("DISPLAY"):
                plt.pause(0.05)
            else:
                time.sleep(0.001)

            client.communicate(10)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        try:
            client.deregister_event_request(buffer_handle, request_id)
        except Exception:
            pass

        try:
            client.disconnect()
        except Exception:
            pass

        print("Bye, bye...")


if __name__ == "__main__":
    parser = OptionParser(usage="usage: %prog [options]")

    parser.add_option(
        "-g", "--grid",
        dest="grid",
        action="store_true",
        default=False,
        help="show grid",
    )

    parser.add_option(
        "-B", "--bank",
        dest="bank_name",
        action="store",
        type="string",
        default="SPEC",
        help="bank name [SPEC]",
    )

    parser.add_option(
        "--buffer",
        dest="buffer_name",
        action="store",
        type="string",
        default="SYSTEM",
        help="MIDAS buffer name [SYSTEM]",
    )

    parser.add_option(
        "--ich",
        dest="i_channel",
        action="store",
        type="int",
        default=0,
        help="I channel [0]",
    )

    parser.add_option(
        "--qch",
        dest="q_channel",
        action="store",
        type="int",
        default=1,
        help="Q channel [1]",
    )

    parser.add_option(
        "-n", "--nch",
        dest="nch",
        action="store",
        type="int",
        default=8,
        help="number of interleaved channels [8]",
    )

    parser.add_option(
        "--fs",
        dest="fs",
        action="store",
        type="float",
        default=5e6,
        help="sampling frequency in Hz [5e6]",
    )

    parser.add_option(
        "-r", "--range",
        dest="input_range",
        action="store",
        type="float",
        default=5.0,
        help="input range in V, assumes +/- range [5.0]",
    )

    parser.add_option(
        "-s", "--hmin",
        dest="hmin",
        action="store",
        type="int",
        default=0,
        help="first sample to display [0]",
    )

    parser.add_option(
        "-e", "--hmax",
        dest="hmax",
        action="store",
        type="int",
        default=1024,
        help="last sample to display [1024]",
    )

    parser.add_option(
        "-u", "--update",
        dest="update_period",
        action="store",
        type="float",
        default=1.0,
        help="plot update period in seconds [1.0]",
    )

    parser.add_option(
        "--save-png",
        dest="save_png",
        action="store",
        type="string",
        default=None,
        help="save plot to PNG file",
    )

    parser.add_option(
        "-v", "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="verbose output",
    )

    options, args = parser.parse_args()

    main(
        bank_name=options.bank_name,
        buffer_name=options.buffer_name,
        i_channel=options.i_channel,
        q_channel=options.q_channel,
        nch=options.nch,
        fs=options.fs,
        input_range=options.input_range,
        hmin=options.hmin,
        hmax=options.hmax,
        grid=options.grid,
        verbose=options.verbose,
        update_period=options.update_period,
        save_png=options.save_png,
    )