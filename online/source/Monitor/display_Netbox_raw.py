#!/usr/bin/env python3

import os
import sys
import time
from datetime import datetime
from optparse import OptionParser

import matplotlib as mpl

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


def setup_spec_figure(grid=False):
    fig, (ax_time, ax_fft) = plt.subplots(
        2, 1, figsize=(12, 7), facecolor="#DEDEDE"
    )

    (ln_time,) = ax_time.plot([], [], linewidth=1.0)
    (ln_fft,) = ax_fft.plot([], [], linewidth=1.0)

    ax_time.set_title("SPEC channel")
    ax_time.set_xlabel("sample")
    ax_time.set_ylabel("voltage [V]")

    ax_fft.set_title("FFT")
    ax_fft.set_xlabel("frequency [MHz]")
    ax_fft.set_ylabel("amplitude [V]")
    ax_fft.set_yscale("log")

    if grid:
        ax_time.grid(True, alpha=0.3)
        ax_fft.grid(True, alpha=0.3)

    try:
        from PyQt5 import QtCore
        mgr = plt.get_current_fig_manager()
        mgr.window.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
    except Exception:
        pass

    return fig, ax_time, ax_fft, ln_time, ln_fft


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


def compute_fft(ch, fs):
    ch = np.asarray(ch, dtype=np.float64)

    n = ch.size
    if n < 2:
        return None, None

    ch = ch - np.mean(ch)

    window = np.hanning(n)
    yw = ch * window

    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.fft.rfft(yw)

    norm = np.sum(window) / 2.0
    amp = np.abs(spec) / norm
    amp[0] *= 0.5

    return freq, amp


def update_spec_plot(ax_time, ax_fft, ln_time, ln_fft, ch0, fs, hmin, hmax):
    nsamp = ch0.size
    if nsamp < 2:
        return False

    smin = max(0, int(hmin))
    emax = min(int(hmax), nsamp)

    if emax <= smin:
        smin = 0
        emax = nsamp

    x = np.arange(smin, emax)
    y = np.asarray(ch0[smin:emax], dtype=np.float64).copy()

    freq, amp = compute_fft(ch0, fs)
    if freq is None:
        return False

    freq_mhz = freq / 1e6
    amp = np.asarray(amp, dtype=np.float64).copy()

    # Waveform
    ln_time.set_xdata(x)
    ln_time.set_ydata(y)

    if x.size > 1:
        ax_time.set_xlim(float(x[0]), float(x[-1]))
    else:
        ax_time.set_xlim(0.0, 1.0)

    ymin = float(np.min(y))
    ymax = float(np.max(y))

    if ymax == ymin:
        ymax = ymin + 1e-6

    margin = 0.1 * (ymax - ymin)
    ax_time.set_ylim(ymin - margin, ymax + margin)

    # FFT
    ln_fft.set_xdata(freq_mhz)
    ln_fft.set_ydata(amp)

    ax_fft.set_xlim(0.0, fs / 2.0 / 1e6)

    positive = amp[amp > 0]
    if positive.size > 0:
        ax_fft.set_ylim(float(np.min(positive) * 0.5), float(np.max(positive) * 2.0))

    return True


def main(
    bank_name="SPEC",
    buffer_name="SYSTEM",
    channel=0,
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

    client = midas.client.MidasClient("spec_display_fft")
    buffer_handle = client.open_event_buffer(buffer_name, None, 1000000000)

    request_id = client.register_event_request(
        buffer_handle,
        sampling_type=midas.GET_RECENT,
    )

    try:
        midas.bm_skip_event(buffer_handle)
    except AttributeError:
        pass

    plt.ion()

    fig, ax_time, ax_fft, ln_time, ln_fft = setup_spec_figure(grid=grid)

    try:
        fig.show()
    except Exception:
        pass

    print(f"Listening online on MIDAS buffer '{buffer_name}', bank '{bank_name}'")
    print(f"Showing channel {channel}, fs={fs:g} Hz, input range +/-{input_range:g} V")
    print("Events display running..., Ctrl-C to stop")

    try:
        while True:
            # Non-blocking: lascia respirare il loop grafico.
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

            event_number = event.header.serial_number
            event_time = datetime.fromtimestamp(event.header.timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            bank_names = ", ".join(b.name for b in event.banks.values())

            if verbose:
                print(
                    f"Event # {event_number} "
                    f"type ID {event.header.event_id} "
                    f"banks {bank_names}"
                )

            now = time.time()

            # Non aggiornare la GUI a ogni evento: evita di rallentare display/DAQ.
            if now - last_update >= update_period:
                if bank_name in event.banks:
                    volt = decode_spec_bank(
                        event,
                        bank_name=bank_name,
                        input_range=input_range,
                        nch=nch,
                    )

                    if volt is not None:
                        if channel < 0 or channel >= volt.shape[1]:
                            print(
                                f"\nERROR: channel {channel} outside range 0..{volt.shape[1] - 1}"
                            )
                            break

                        ch = volt[:, channel].copy()

                        updated = update_spec_plot(
                            ax_time=ax_time,
                            ax_fft=ax_fft,
                            ln_time=ln_time,
                            ln_fft=ln_fft,
                            ch0=ch,
                            fs=fs,
                            hmin=hmin,
                            hmax=hmax,
                        )

                        if updated:
                            fig.suptitle(
                                f"{bank_name} Event: {event_number:d} at {event_time:s}"
                            )

                            fig.canvas.draw()
                            fig.canvas.flush_events()

                            if save_png:
                                fig.savefig(save_png, dpi=120)

                            last_update = now

                            print(
                                f"Event {event_number} | "
                                f"rate approx {float(event_number - event_before):.2f} Hz | "
                                f"ch{channel}: min={np.min(ch):+.4f} V "
                                f"max={np.max(ch):+.4f} V "
                                f"first={ch[:3]}",
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
                            print(f"> ch{channel}, first 5 samples [V] >", ch[:5])

                else:
                    if verbose:
                        print(
                            f"No {bank_name} bank in event {event_number}, banks: {bank_names}"
                        )

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
        "-c", "--channel",
        dest="channel",
        action="store",
        type="int",
        default=0,
        help="channel to view [0]",
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
        channel=options.channel,
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