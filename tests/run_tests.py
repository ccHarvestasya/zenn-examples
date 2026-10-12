"""Developer checks; run each lesson in a separate process."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    failures = []
    for sample in sorted((ROOT / 'symbol-p2p').iterdir()):
        if not sample.is_dir():
            continue
        tests = ROOT / 'tests' / 'symbol-p2p' / sample.name
        if not tests.is_dir():
            continue
        print(f'Running developer tests {sample.name}', flush=True)
        result = subprocess.run([
            sys.executable, '-m', 'unittest', 'discover', '-s', str(tests), '-v',
        ], cwd=sample)
        if result.returncode:
            failures.append(sample.name)
    if failures:
        print('Failed: ' + ', '.join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
