"""Entry point.   python main.py            -> launch the GUI
                  python main.py --selftest -> run the validation cases in the terminal
"""
import sys


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        from ev_calculator.validation import format_report, run_all
        cases = run_all()
        print(format_report(cases))
        return 0 if all(c.passed for c in cases) else 1
    from ev_calculator.gui import run
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
