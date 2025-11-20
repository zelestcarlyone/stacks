#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
import flask.cli
import logging

from pathlib import Path

from stacks.constants import CONFIG_FILE, DEFAULT_CONFIG_FILE, PROJECT_ROOT, LOG_PATH, DOWNLOAD_PATH

# ANSI color codes (Dracula theme)
INFO = "\033[38;2;139;233;253m"       # cyan
WARN = "\033[38;2;255;184;108m"       # orange
GOOD = "\033[38;2;80;250;123m"        # green
PINK = "\033[38;2;255;102;217m"       # pink
PURPLE = "\033[38;2;178;102;255m"     # purple
BG = "\033[48;2;40;42;54m"            # black background
PINKBG = "\033[48;2;255;102;217m"     # pink background
RESET = "\033[0m"                     # reset

def print_logo(version: str):
    """Display the super cool STACKS logo"""
    dashes = '─' * (52 - len(version))
    
    print(f"{BG}{PURPLE} ┌───────────────────────────────────────────────────────────┐ {RESET}")
    print(f"{BG}{PURPLE} │                                                           {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▄████▄ ████████  ▄█▄     ▄████▄  ██    ▄██ ▄████▄     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▀  ▀██   ██    ▄{PINKBG}{PURPLE}▄{BG}▀{PINKBG}▄{BG}{PINK}▄   ██▀  ▀██ ██  ▄██▀ ██▀  ▀██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▄        ██    █{PURPLE}█ █{PINK}█  ██        ██▄██▀   ██▄         {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▀████▄    ██   █{PURPLE}█   █{PINK}█ ██        ████      ▀████▄     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}         ▀██   ██   █{PURPLE}█   █{PINK}█ ██        ██▀██▄        ▀██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}    ██▄  ▄██   ██  █{PURPLE}█     █{PINK}█ ██▄  ▄██ ██  ▀██▄ ██▄  ▄██    {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │{PINK}     ▀████▀    ██  █{PURPLE}▀     ▀{PINK}█  ▀████▀  ██    ▀██ ▀████▀     {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} │                                                           {PURPLE}│ {RESET}")
    print(f"{BG}{PURPLE} └{dashes}╢v{version}╟────┘ {RESET}")
    sys.stdout.flush()  # Force flush before exec
    sys.stdout.flush()

def ensure_directories():
    """Ensure essential directories exist."""
    dirs = [
        Path(CONFIG_FILE).parent,
        Path(LOG_PATH),
        Path(DOWNLOAD_PATH),
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def setup_config(config_path):
    """
    Ensure a config file exists.
    """
    # Use either provided config, or default
    cfg_path = Path(config_path) if config_path else Path(CONFIG_FILE)
    default_cfg = Path(DEFAULT_CONFIG_FILE)

    print("◼ Checking configuration...")
    sys.stdout.flush()

    if not cfg_path.exists():
        print("  No config.yaml found - seeding default.")
        shutil.copy2(default_cfg, cfg_path)
        cfg_path.chmod(0o600)
    else:
        print(f"  Found config.yaml at {cfg_path}")

    return str(cfg_path)


def main():
    parser = argparse.ArgumentParser(description="Start the Stacks server.")
    parser.add_argument(
        "-c", "--config",
        help="Path to an alternative config.yaml file"
    )
    args = parser.parse_args()

    # Set UTF-8 encoding
    os.environ.setdefault("LANG", "C.UTF-8")

    # Read version
    version_file = PROJECT_ROOT / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    print_logo(version)

    # Ensure directories exist
    ensure_directories()

    # Load or create config.yaml
    config_path = setup_config(args.config)

    # Detect password reset request
    if os.environ.get("RESET_ADMIN", "false").lower() == "true":
        print("! RESET_ADMIN=true detected - admin password will be reset!\n")
        sys.stdout.flush()

    # Switch working dir
    os.chdir(PROJECT_ROOT)

    print("◼ Starting Stacks...")
    sys.stdout.flush()

    flask.cli.show_server_banner = lambda *args, **kwargs: None
    logging.getLogger('werkzeug').disabled = True

    from stacks.server.webserver import create_app
    app = create_app(config_path)    
    app.run(host="0.0.0.0", port=7788)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError during startup: {e}", file=sys.stderr)
        sys.exit(1)