import sys

import numpy as np

import FitCall as fc


PARAMETER_NAMES = (
    "Abs12",
    "f0",
    "Q0",
    "beta1",
    "beta2",
    "Abs21",
    "Abs22",
    "q22",
)

DEFAULT_GUESS = np.array(
    [8.4e-6, 8.7364e9, 53000.0, 8.0e-2, 1.02, 12.5, 3.3, 0.0],
    dtype=float,
)
DEFAULT_MIN = np.array(
    [5.0e-6, 8.73e9, 48000.0, 1.0e-4, 0.1, 12.0, 3.0, -1.0],
    dtype=float,
)
DEFAULT_MAX = np.array(
    [1.0e-5, 8.75e9, 65000.0, 10.0, 8.0, 13.5, 4.0, 1.0],
    dtype=float,
)

ABS_LIMIT_FRACTIONS = {"Abs12": 0.25, "Abs21": 0.20, "Abs22": 0.15}
for _name, _fraction in ABS_LIMIT_FRACTIONS.items():
    _index = PARAMETER_NAMES.index(_name)
    DEFAULT_MIN[_index] = DEFAULT_GUESS[_index] * (1.0 - _fraction)
    DEFAULT_MAX[_index] = DEFAULT_GUESS[_index] * (1.0 + _fraction)


def default_fit_parameters():
    return (
        DEFAULT_GUESS.copy(),
        PARAMETER_NAMES,
        DEFAULT_MIN.copy(),
        DEFAULT_MAX.copy(),
    )


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 5:
        raise SystemExit(
            "Usage: mainFit.py S12_file S22_file S21_file fmin_hz fmax_hz"
        )

    par_ini, par_name, par_min, par_max = default_fit_parameters()
    fit, _ = fc.fitCall(
        args[0],
        args[1],
        args[2],
        args[3],
        args[4],
        par_ini,
        par_name,
        par_min,
        par_max,
    )

    print(fit.params)
    print(fit.fmin)
    print("Minuit is valid =", fit.valid)
    print(fit.covariance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
