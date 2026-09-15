#!/usr/bin/env python3

import json
import math
import os
import re
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-fit")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import FitCall as fc
import midas.client
import numpy as np
from mainFit import ABS_LIMIT_FRACTIONS, PARAMETER_NAMES


FIT_OUTPUT_PATH = "/Equipment/VNA/Fit/Output"
FIT_MODE_PATH = "/Equipment/VNA/Fit/Mode"
FIT_REQUEST_PATH = "/Equipment/VNA/Fit/Request"
FIT_RESULT_PATH = "/Equipment/VNA/Fit/Result"
CALIBRATION_DIR = Path("~/data/calib").expanduser()
PLOT_DIR = Path(__file__).resolve().parents[2] / "custom"
VALID_MODES = {"Mode1": "modo1", "Mode2": "modo2", "Mode3": "modo3"}
EXPECTED_SCATTERING_PARAMETERS = {"S21", "S22", "S12"}


def latest_calibration_files(directory, mode, limit=3):
    try:
        filename_mode = VALID_MODES[mode]
    except KeyError:
        raise ValueError("Modalita di fit non valida: {}".format(mode))

    filename_pattern = re.compile(
        r"^S\d{{2}}[^_]*_{}_.+\.txt$".format(re.escape(filename_mode)),
        re.IGNORECASE,
    )
    files = (
        path
        for path in directory.iterdir()
        if path.is_file() and filename_pattern.match(path.name)
    )
    return sorted(
        files,
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )[:limit]


def scattering_parameter(path):
    match = re.match(r"^(S\d{2})", path.name, re.IGNORECASE)
    if not match:
        raise ValueError("Parametro di scattering non riconosciuto: {}".format(path.name))
    return match.group(1).upper()


def save_scattering_plot(parameter, mode, frequency, magnitude, fit_curve):
    frequency_ghz = frequency / 1e9

    figure, axes = plt.subplots(figsize=(7, 4.5))
    axes.scatter(frequency_ghz, magnitude, color="dimgray", s=3, label="Data")
    axes.plot(frequency_ghz, fit_curve, color="orangered", linewidth=1.2, label="Fit")
    axes.set_title("{} - {}".format(parameter, mode))
    axes.set_xlabel("Frequency [GHz]")
    axes.set_ylabel("|{}|".format(parameter))
    axes.grid(True, alpha=0.3)
    axes.legend(frameon=False)
    figure.tight_layout()

    figure.savefig(str(PLOT_DIR / "{}.pdf".format(parameter)))
    figure.savefig(str(PLOT_DIR / "{}.png".format(parameter)), dpi=160)
    plt.close(figure)


def read_fit_request(client):
    request = json.loads(client.odb_get(FIT_REQUEST_PATH))

    mode = request.get("mode")
    if mode not in VALID_MODES:
        raise ValueError("Modalita di fit non valida: {}".format(mode))

    names = tuple(request.get("parameter_names", ()))
    if names != PARAMETER_NAMES:
        raise ValueError("Ordine dei parametri di fit non valido")

    beta2_index = PARAMETER_NAMES.index("beta2")
    beta2_auto = request.get("beta2_auto") is True
    abs_flags = request.get("abs_auto", {})
    if not isinstance(abs_flags, dict):
        raise ValueError("Configurazione automatica Abs non valida")
    automatic_abs = [
        name for name in ("Abs12", "Abs21", "Abs22")
        if abs_flags.get(name) is True
    ]
    automatic_indices = [PARAMETER_NAMES.index(name) for name in automatic_abs]
    if beta2_auto:
        automatic_indices.append(beta2_index)
    raw_guess = request.get("guess")
    if isinstance(raw_guess, list) and len(raw_guess) == len(PARAMETER_NAMES):
        raw_guess = raw_guess.copy()
        for index in automatic_indices:
            raw_guess[index] = 0.0

    guess = np.asarray(raw_guess, dtype=float)
    minimum = np.asarray(request.get("min"), dtype=float)
    maximum = np.asarray(request.get("max"), dtype=float)
    expected_shape = (len(PARAMETER_NAMES),)

    if guess.shape != expected_shape or minimum.shape != expected_shape or maximum.shape != expected_shape:
        raise ValueError("Guess, min e max devono contenere 8 valori")
    automatic_limits = {"min": [], "max": []}
    for side, values in (("min", minimum), ("max", maximum)):
        for name in ABS_LIMIT_FRACTIONS:
            index = PARAMETER_NAMES.index(name)
            if request[side][index] is None:
                automatic_limits[side].append(index)
                values[index] = 0.0  # Resolved after calculating the initial Abs.
    if not (np.all(np.isfinite(guess)) and np.all(np.isfinite(minimum)) and np.all(np.isfinite(maximum))):
        raise ValueError("I parametri di fit devono essere numeri finiti")
    invalid_limits = minimum >= maximum
    deferred_indices = automatic_limits["min"] + automatic_limits["max"]
    invalid_limits[deferred_indices] = False
    if np.any(invalid_limits):
        raise ValueError("Ogni valore Min deve essere minore del corrispondente Max")
    guess_outside_limits = (guess < minimum) | (guess > maximum)
    guess_outside_limits[automatic_indices] = False
    guess_outside_limits[deferred_indices] = False
    if np.any(guess_outside_limits):
        raise ValueError("Ogni Guess Val deve essere compreso tra Min e Max")

    fmin_value = request.get("fmin_hz")
    fmax_value = request.get("fmax_hz")
    if fmin_value is None and fmax_value is None:
        fmin_hz = None
        fmax_hz = None
    elif fmin_value is None or fmax_value is None:
        raise ValueError("fmin e fmax devono essere entrambi automatici o manuali")
    else:
        fmin_hz = float(fmin_value)
        fmax_hz = float(fmax_value)
        if (
            not math.isfinite(fmin_hz)
            or not math.isfinite(fmax_hz)
            or fmin_hz >= fmax_hz
        ):
            raise ValueError("Il range di frequenza S22 non e valido")

    return mode, fmin_hz, fmax_hz, guess, minimum, maximum, beta2_auto, automatic_abs, automatic_limits


def frequency_endpoints(path):
    frequency = np.atleast_1d(np.genfromtxt(path, usecols=(0,)))
    if frequency.size < 2:
        raise ValueError("Il file {} deve contenere almeno due frequenze".format(path.name))

    fmin_hz = float(frequency[0])
    fmax_hz = float(frequency[-1])
    if not math.isfinite(fmin_hz) or not math.isfinite(fmax_hz) or fmin_hz >= fmax_hz:
        raise ValueError(
            "Prima e ultima frequenza non valide nel file {}".format(path.name)
        )

    return fmin_hz, fmax_hz


def estimate_loaded_q(path):
    frequency, real, imaginary = np.genfromtxt(
        path,
        unpack=True,
        usecols=(0, 1, 2),
    )
    frequency = np.atleast_1d(frequency)
    magnitude = np.hypot(np.atleast_1d(real), np.atleast_1d(imaginary))

    finite = np.isfinite(frequency) & np.isfinite(magnitude)
    frequency = frequency[finite]
    magnitude = magnitude[finite]
    if frequency.size < 3:
        raise ValueError(
            "Il file {} non contiene abbastanza dati per calcolare QL".format(
                path.name
            )
        )

    order = np.argsort(frequency)
    frequency = frequency[order]
    magnitude = magnitude[order]
    peak_index = int(np.argmax(magnitude))
    if peak_index == 0 or peak_index == frequency.size - 1:
        raise ValueError(
            "Il picco S21 e sul bordo del file {}; QL non calcolabile".format(
                path.name
            )
        )

    half_power = magnitude[peak_index] / math.sqrt(2.0)
    left_candidates = np.flatnonzero(magnitude[:peak_index] <= half_power)
    right_candidates = np.flatnonzero(magnitude[peak_index + 1 :] <= half_power)
    if left_candidates.size == 0 or right_candidates.size == 0:
        raise ValueError(
            "Il file {} non contiene entrambi i punti a -3 dB".format(path.name)
        )

    left_index = int(left_candidates[-1])
    right_index = int(peak_index + 1 + right_candidates[0])

    def interpolate_crossing(first_index, second_index):
        first_value = magnitude[first_index]
        second_value = magnitude[second_index]
        if second_value == first_value:
            return 0.5 * (
                frequency[first_index] + frequency[second_index]
            )
        fraction = (half_power - first_value) / (second_value - first_value)
        return frequency[first_index] + fraction * (
            frequency[second_index] - frequency[first_index]
        )

    left_frequency = interpolate_crossing(left_index, left_index + 1)
    right_frequency = interpolate_crossing(right_index - 1, right_index)
    bandwidth = right_frequency - left_frequency
    resonance_frequency = frequency[peak_index]
    loaded_q = resonance_frequency / bandwidth

    if not math.isfinite(loaded_q) or loaded_q <= 0:
        raise ValueError("QL calcolato non valido dal file {}".format(path.name))

    return loaded_q


def estimate_initial_abs(files_by_parameter, initial_beta2, automatic_abs):
    initial_abs = {}
    transmission_factor = None
    if any(name in automatic_abs for name in ("Abs12", "Abs21")):
        if not math.isfinite(initial_beta2) or initial_beta2 <= 0:
            raise ValueError("Il Guess beta2 deve essere positivo per calcolare Abs12/Abs21")
        # Use the requested fixed beta1 for the amplitude estimate only.
        beta1 = 0.08
        transmission_factor = (
            2.0 * math.sqrt(beta1 * initial_beta2) / (1.0 + beta1 + initial_beta2)
        )

    for name in automatic_abs:
        parameter = "S" + name[3:]
        path = files_by_parameter[parameter]
        data = np.genfromtxt(path, usecols=(0, 1, 2), ndmin=2)
        if data.shape[0] == 0 or not np.all(np.isfinite(data)):
            raise ValueError("Dati assenti o non finiti nel file {}".format(path.name))
        magnitude = np.hypot(data[:, 1], data[:, 2])
        # S22 uses the first frequency sample in the file, as for fmin.
        value = magnitude[0] if parameter == "S22" else np.max(magnitude) / transmission_factor
        if not math.isfinite(value) or value <= 0:
            raise ValueError("{} automatico non valido dal file {}".format(name, path.name))
        initial_abs[name] = float(value)

    return initial_abs


def resolve_abs_limits(guess, minimum, maximum, automatic_limits):
    limits = {}
    for name, fraction in ABS_LIMIT_FRACTIONS.items():
        index = PARAMETER_NAMES.index(name)
        value = guess[index]
        if index in automatic_limits["min"]:
            minimum[index] = value * (1.0 - fraction)
        if index in automatic_limits["max"]:
            maximum[index] = value * (1.0 + fraction)
        if (
            not np.all(np.isfinite([value, minimum[index], maximum[index]]))
            or minimum[index] >= maximum[index]
            or not minimum[index] <= value <= maximum[index]
        ):
            raise ValueError(
                "{}: Guess {:.6g} incompatibile con Min {:.6g} e Max {:.6g}; "
                "modificare i limiti nella tabella".format(
                    name, value, minimum[index], maximum[index]
                )
            )
        limits[name] = {"min": float(minimum[index]), "max": float(maximum[index])}
    return limits


def finite_float(value):
    value = float(value)
    return value if math.isfinite(value) else None


def format_correlation_matrix(matrix):
    rows = [[""] + list(PARAMETER_NAMES)]
    for name, values in zip(PARAMETER_NAMES, matrix):
        rows.append([name] + [format(float(value), "#.2g") for value in values])
    widths = [max(len(cell) for cell in column) for column in zip(*rows)]
    return "\n".join(
        "  ".join(cell.rjust(width) for cell, width in zip(row, widths))
        for row in rows
    )


def fit_result_as_json(fit, fmin_hz, fmax_hz, loaded_q, initial_beta2, initial_abs):
    parameters = []
    for index, name in enumerate(PARAMETER_NAMES):
        parameters.append(
            {
                "name": name,
                "value": finite_float(fit.values[index]),
                "error": finite_float(fit.errors[index]),
            }
        )

    return {
        "ok": True,
        "valid": bool(fit.valid),
        "fval": finite_float(fit.fval),
        "reduced_chi2": finite_float(fit.fmin.reduced_chi2),
        "fmin_hz": finite_float(fmin_hz),
        "fmax_hz": finite_float(fmax_hz),
        "loaded_q": finite_float(loaded_q) if loaded_q is not None else None,
        "initial_beta2": finite_float(initial_beta2),
        "initial_abs": initial_abs,
        "minuit_report": {
            "fmin": str(fit.fmin),
            "valid": "Minuit is valid = {}".format(fit.valid),
            "correlation": (
                format_correlation_matrix(fit.covariance.correlation())
                if fit.covariance is not None
                else "Matrice di correlazione non disponibile."
            ),
        },
        "parameters": parameters,
    }


def main():
    # This is a short-lived MIDAS client, not a MIDAS frontend.
    with midas.client.MidasClient("Fit script") as client:
        try:
            (
                mode,
                fmin_hz,
                fmax_hz,
                guess,
                minimum,
                maximum,
                beta2_auto,
                automatic_abs,
                automatic_limits,
            ) = read_fit_request(client)
            latest_files = latest_calibration_files(CALIBRATION_DIR, mode)

            if len(latest_files) < 3:
                raise RuntimeError(
                    "Trovati solo {} file di calibrazione per {} in {}".format(
                        len(latest_files), mode, CALIBRATION_DIR
                    )
                )

            files_by_parameter = {
                scattering_parameter(path): path for path in latest_files
            }
            if set(files_by_parameter) != EXPECTED_SCATTERING_PARAMETERS:
                raise RuntimeError(
                    "Attesi i parametri {}, trovati {}".format(
                        sorted(EXPECTED_SCATTERING_PARAMETERS),
                        sorted(files_by_parameter),
                    )
                )

            if fmin_hz is None:
                fmin_hz, fmax_hz = frequency_endpoints(
                    files_by_parameter["S22"]
                )

            loaded_q = None
            beta2_index = PARAMETER_NAMES.index("beta2")
            if beta2_auto:
                loaded_q = estimate_loaded_q(files_by_parameter["S21"])
                q0_index = PARAMETER_NAMES.index("Q0")
                guess[beta2_index] = guess[q0_index] / loaded_q - 1.0
                if (
                    not math.isfinite(guess[beta2_index])
                    or guess[beta2_index] < minimum[beta2_index]
                    or guess[beta2_index] > maximum[beta2_index]
                ):
                    raise ValueError(
                        "beta2 automatico ({:.6g}) fuori dai limiti [{:.6g}, {:.6g}]".format(
                            guess[beta2_index],
                            minimum[beta2_index],
                            maximum[beta2_index],
                        )
                    )

            initial_beta2 = guess[beta2_index]
            calculated_abs = estimate_initial_abs(
                files_by_parameter, initial_beta2, automatic_abs
            )
            for name, value in calculated_abs.items():
                index = PARAMETER_NAMES.index(name)
                guess[index] = value
            initial_abs_limits = resolve_abs_limits(
                guess, minimum, maximum, automatic_limits
            )
            initial_abs = {
                name: float(guess[PARAMETER_NAMES.index(name)])
                for name in ("Abs12", "Abs21", "Abs22")
            }

            fit, datasets = fc.fitCall(
                str(files_by_parameter["S12"]),
                str(files_by_parameter["S22"]),
                str(files_by_parameter["S21"]),
                fmin_hz,
                fmax_hz,
                guess,
                PARAMETER_NAMES,
                minimum,
                maximum,
            )

            for parameter, (frequency, magnitude, fit_curve) in datasets.items():
                save_scattering_plot(
                    parameter, mode, frequency, magnitude, fit_curve
                )

            result = fit_result_as_json(
                fit,
                fmin_hz,
                fmax_hz,
                loaded_q,
                initial_beta2,
                initial_abs,
            )
            output = "\n".join(path.name for path in latest_files)
            result["initial_abs_limits"] = initial_abs_limits
            client.odb_set(FIT_RESULT_PATH, json.dumps(result))
            # Output is the completion marker read by fit.html, so write it last.
            client.odb_set(FIT_OUTPUT_PATH, output)

        except Exception as error:
            error_message = "Fit fallito: {}".format(error)
            client.odb_set(
                FIT_RESULT_PATH,
                json.dumps({"ok": False, "error": str(error)}),
            )
            client.odb_set(FIT_OUTPUT_PATH, error_message)
            raise

    print(output)


if __name__ == "__main__":
    main()
