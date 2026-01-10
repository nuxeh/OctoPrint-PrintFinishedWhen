import argparse
import re
import os

# Configuration: List files that contain version strings to update
TARGET_FILES = [
    "pyproject.toml",
    "setup.py",
    "README.md",
    "octoprint_print_finished_when/__init__.py",
]
VERSION_FILE = "VERSION"

def get_current_version():
    """Reads the current version from the VERSION file."""
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w") as f:
            f.write("0.1.0")
        return "0.1.0"
    with open(VERSION_FILE, "r") as f:
        return f.read().strip()

def bump_version(current, part):
    """Increments the specified part of a MAJOR.MINOR.PATCH version string."""
    major, minor, patch = map(int, current.split('.'))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:  # Default to patch
        patch += 1
    return f"{major}.{minor}.{patch}"

def update_files(old_v, new_v):
    """Finds and replaces version strings in a list of files using regex."""
    # Matches typical patterns like version="1.2.3" or __version__ = '1.2.3'
    pattern = re.compile(
        rf'((?:version|__version__|__plugin_version__)\s*=\s*)(["\']){re.escape(old_v)}(["\'])'
    )

    for file_path in TARGET_FILES:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read()

            new_content = pattern.sub(rf'\g<1>{new_v}\g<2>', content)

            with open(file_path, "w") as f:
                f.write(new_content)
            print(f"Updated {file_path}")

def main():
    parser = argparse.ArgumentParser(description="Bump SemVer in project files.")
    parser.add_argument("bump", choices=["major", "minor", "patch"],
                        nargs="?", default="patch", help="Part to increment (default: patch)")
    args = parser.parse_args()

    old_version = get_current_version()
    new_version = bump_version(old_version, args.bump)

    # Update version tracker file
    with open(VERSION_FILE, "w") as f:
        f.write(new_version)

    # Update target files
    update_files(old_version, new_version)
    print(f"Bumped version: {old_version} -> {new_version}")

if __name__ == "__main__":
    main()
