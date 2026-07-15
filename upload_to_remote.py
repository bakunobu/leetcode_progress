#!/usr/bin/env python3
"""
Upload the local SQLite database to a remote server via SCP.

Uses the system ``scp`` command (via ``subprocess``) — no extra Python
dependencies required.

Remote connection details are read from ``config.json`` under the ``remote``
key. Example config.json::

    {
        "user_id": "your-leetcode-id",
        "spreadsheet_key": "your-spreadsheet-id",
        "remote": {
            "host": "your-server.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/home/deploy/data/leetcode_stats.db",
            "key_filename": "/home/bakunobu/.ssh/id_rsa"
        }
    }

Usage
-----
    python upload_to_remote.py                          # uses config.json
    python upload_to_remote.py --host myserver.com       # override host
    python upload_to_remote.py --port 2222               # override port
    python upload_to_remote.py --key ~/.ssh/deploy_key   # override key file
"""

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone

# ── Configuration defaults ───────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
LOCAL_DB_PATH = os.path.join(
    PROJECT_DIR, "data", "leetcode_stats.db"
)


def load_config() -> dict:
    """Load and return the full ``config.json`` as a dict."""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"{CONFIG_FILE} not found. Create it with a 'remote' section."
        )
    with open(CONFIG_FILE) as f:
        return json.load(f)


def build_scp_command(
    host: str,
    remote_path: str,
    username: str,
    local_db_path: str,
    port: int = 22,
    key_filename: str | None = None,
    password: str | None = None,
) -> list[str]:
    """Build the SCP command as a list of args.

    Parameters
    ----------
    host : str
        Remote hostname or IP.
    remote_path : str
        Absolute path on the remote server where the file will be written.
    username : str
        SSH username.
    local_db_path : str
        Path to the local SQLite file to upload.
    port : int
        SSH port (default 22).
    key_filename : str | None
        Path to an SSH private key file (e.g. ``~/.ssh/id_rsa``).
        If ``None``, SCP will use whatever SSH-agent or default key is
        available.
    password : str | None
        Password for SSH authentication. Passwords are insecure over
        subprocess (visible in process list). **Prefer key-based auth.**

    Returns
    -------
    list[str]
        SCP command ready for ``subprocess.run()``.
    """
    cmd = ["scp"]

    # Port
    if port != 22:
        cmd.extend(["-P", str(port)])

    # Key file (identity file)
    if key_filename:
        expanded_key = os.path.expanduser(key_filename)
        cmd.extend(["-i", expanded_key])

    # Password via sshpass (optional fallback)
    # NOTE: sshpass must be installed on the system.
    # If you need password auth, consider using paramiko instead.

    # Source: local DB file
    cmd.append(local_db_path)

    # Destination: user@host:path
    dest = f"{username}@{host}:{remote_path}"
    cmd.append(dest)

    return cmd


def test_connection(
    host: str,
    username: str,
    port: int = 22,
    key_filename: str | None = None,
) -> bool:
    """Test SSH connection to the remote host without uploading.

    Uses ``ssh -o ConnectTimeout=5`` to quickly check reachability.
    """
    ssh_cmd = [
        "ssh",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
    ]
    if port != 22:
        ssh_cmd.extend(["-p", str(port)])
    if key_filename:
        ssh_cmd.extend(["-i", os.path.expanduser(key_filename)])
    ssh_cmd.append(f"{username}@{host}")
    ssh_cmd.append("echo OK")

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "OK" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"Connection test failed: {exc}", file=sys.stderr)
        return False


def upload_via_scp(
    host: str,
    remote_path: str,
    username: str,
    local_db_path: str,
    port: int = 22,
    key_filename: str | None = None,
    verbose: bool = True,
) -> bool:
    """Upload the local SQLite DB to a remote server via SCP.

    Uses an **atomic upload pattern**: uploads to a temporary path
    (``remote_path.uploading``), then renames to the final path.
    This prevents corruption if the upload is interrupted.

    .. note::
        The atomic rename requires shell access on the remote server.
        If the rename step fails, the temporary file is left in place
        and printed to stderr.

    Parameters
    ----------
    host : str
        Remote hostname or IP.
    remote_path : str
        Absolute destination path on the remote server.
    username : str
        SSH username.
    local_db_path : str
        Path to the local SQLite database file.
    port : int
        SSH port (default 22).
    key_filename : str | None
        Path to an SSH private key.
    verbose : bool
        If ``True``, print progress to stderr.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure.
    """
    if not os.path.exists(local_db_path):
        print(
            f"Local DB not found: {local_db_path}. Run a sync first.",
            file=sys.stderr,
        )
        return False

    local_size = os.path.getsize(local_db_path)
    if verbose:
        print(
            f"Uploading {local_db_path} ({local_size:,} bytes) "
            f"to {username}@{host}:{remote_path} ...",
            file=sys.stderr,
        )

    # ── Step 1: Upload to a temporary path (atomic write) ──────────
    tmp_remote_path = remote_path + ".uploading"
    scp_cmd = build_scp_command(
        host=host,
        remote_path=tmp_remote_path,
        username=username,
        local_db_path=local_db_path,
        port=port,
        key_filename=key_filename,
    )

    if verbose:
        print(f"  Running: {' '.join(shlex.quote(p) for p in scp_cmd)}", file=sys.stderr)

    try:
        result = subprocess.run(
            scp_cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 min timeout for upload
        )
    except FileNotFoundError:
        print(
            "ERROR: 'scp' command not found. Install OpenSSH client "
            "(apt install openssh-client / brew install openssh).",
            file=sys.stderr,
        )
        return False
    except subprocess.TimeoutExpired:
        print("ERROR: SCP upload timed out after 120 seconds.", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(f"SCP failed (exit code {result.returncode}):", file=sys.stderr)
        if result.stderr:
            print(f"  {result.stderr.strip()}", file=sys.stderr)
        return False

    # ── Step 2: Atomically rename the temp file ────────────────────
    rename_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
    ]
    if port != 22:
        rename_cmd.extend(["-p", str(port)])
    if key_filename:
        rename_cmd.extend(["-i", os.path.expanduser(key_filename)])
    rename_cmd.append(f"{username}@{host}")
    rename_cmd.append(f"mv {shlex.quote(tmp_remote_path)} {shlex.quote(remote_path)}")

    rename_result = subprocess.run(
        rename_cmd,
        capture_output=True,
        text=True,
        timeout=15,
    )

    if rename_result.returncode != 0:
        print(
            f"WARNING: Uploaded to {tmp_remote_path} but rename failed: "
            f"{rename_result.stderr.strip()}",
            file=sys.stderr,
        )
        return False

    # ── Step 3: Verify the remote file exists ──────────────────────
    verify_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
    ]
    if port != 22:
        verify_cmd.extend(["-p", str(port)])
    if key_filename:
        verify_cmd.extend(["-i", os.path.expanduser(key_filename)])
    verify_cmd.append(f"{username}@{host}")
    verify_cmd.append(f"stat -c %s {shlex.quote(remote_path)}")

    verify_result = subprocess.run(
        verify_cmd,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if verify_result.returncode == 0:
        remote_size = verify_result.stdout.strip()
        if verbose:
            print(
                f"Upload complete. Remote file size: {remote_size} bytes.",
                file=sys.stderr,
            )
    else:
        print(
            f"WARNING: Upload command succeeded but could not verify remote file.",
            file=sys.stderr,
        )

    return True


def upload_to_remote(
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    remote_path: str | None = None,
    key_filename: str | None = None,
    local_db_path: str | None = None,
    verbose: bool = True,
) -> bool:
    """Upload the local DB to a remote server via SCP.

    Reads any missing parameters from ``config.json`` under the ``remote`` key.
    CLI arguments take precedence over config file values.

    Parameters
    ----------
    host : str | None
        Remote hostname or IP.
    port : int | None
        SSH port (default 22).
    username : str | None
        SSH username.
    remote_path : str | None
        Absolute path on the remote server.
    key_filename : str | None
        Path to SSH private key file (e.g. ``/home/user/.ssh/id_rsa``).
    local_db_path : str | None
        Path to the local DB file (default: ``data/leetcode_stats.db``).
    verbose : bool
        Print progress to stderr.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure.
    """
    # ── Resolve config ─────────────────────────────────────────────
    config = load_config()
    remote_cfg = config.get("remote", {})

    host = host or remote_cfg.get("host")
    port = port if port is not None else remote_cfg.get("port", 22)
    username = username or remote_cfg.get("username")
    remote_path = remote_path or remote_cfg.get("remote_path")
    key_filename = key_filename or remote_cfg.get("key_filename")
    local_db_path = local_db_path or LOCAL_DB_PATH

    # Validate required fields
    missing = []
    if not host:
        missing.append("host")
    if not username:
        missing.append("username")
    if not remote_path:
        missing.append("remote_path")

    if missing:
        print(
            f"Missing required remote config fields: {', '.join(missing)}. "
            f"Set them in config.json or pass as arguments.",
            file=sys.stderr,
        )
        return False

    return upload_via_scp(
        host=host,
        remote_path=remote_path,
        username=username,
        local_db_path=local_db_path,
        port=port,
        key_filename=key_filename,
        verbose=verbose,
    )


# ── SQL-pipe upload (batch upload via SSH + sqlite3 CLI) ────────────

def generate_insert_sql(
    records: list[dict],
    table_name: str = "daily_stats",
    upsert: bool = False,
    batch_size: int = 100,
) -> str:
    """Generate SQL INSERT statements for a list of records.

    Builds ``INSERT OR IGNORE`` (or ``INSERT OR REPLACE`` if *upsert*) statements
    in batches of *batch_size* records per statement.  Also prepends a
    ``CREATE UNIQUE INDEX IF NOT EXISTS`` statement so that the conflict
    resolution works correctly on the remote.

    Parameters
    ----------
    records : list[dict]
        Records with keys matching ``DailyStats`` columns:
        ``nickname``, ``response_ts``, ``rating``, ``easy``, ``medium``,
        ``hard``, ``total``.
    table_name : str
        Target table name (default ``"daily_stats"``).
    upsert : bool
        If ``True``, use ``INSERT OR REPLACE``; otherwise ``INSERT OR IGNORE``.
    batch_size : int
        Max number of records per ``INSERT`` statement (default 100).

    Returns
    -------
    str
        Complete SQL script ready to pipe into ``sqlite3``.
    """
    if not records:
        return ""

    columns = ["nickname", "response_ts", "rating", "easy", "medium", "hard", "total"]

    # ── Ensure the remote table has a UNIQUE index on response_ts ──
    sql_parts: list[str] = [
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table_name}_response_ts "
        f"ON {table_name}(response_ts);"
    ]

    # ── Batch records into chunks ──────────────────────────────────
    nl = "\n"  # workaround for Python < 3.12 (backslash in f-string expr)
    for chunk_start in range(0, len(records), batch_size):
        chunk = records[chunk_start : chunk_start + batch_size]
        value_rows: list[str] = []

        for record in chunk:
            escaped: list[str] = []
            for col in columns:
                val = record.get(col)
                if val is None:
                    escaped.append("NULL")
                elif isinstance(val, int):
                    escaped.append(str(val))
                elif isinstance(val, float):
                    escaped.append(str(val))
                elif hasattr(val, "isoformat"):  # datetime / date
                    escaped.append(f"'{val.isoformat()}'")
                else:
                    # string — escape single quotes by doubling them
                    escaped.append(f"'{str(val).replace(chr(39), chr(39)+chr(39))}'")
            value_rows.append(f"({', '.join(escaped)})")

        stmt = "INSERT OR REPLACE INTO" if upsert else "INSERT OR IGNORE INTO"
        sql_parts.append(
            f"{stmt} {table_name} "
            f"({', '.join(columns)}){nl}"
            f"VALUES{nl}{f',{nl}'.join(value_rows)};"
        )

    return "\n".join(sql_parts)


def upload_records_via_sql_pipe(
    records: list[dict],
    remote_db_path: str,
    host: str,
    username: str,
    port: int = 22,
    key_filename: str | None = None,
    table_name: str = "daily_stats",
    upsert: bool = False,
    batch_size: int = 100,
    verbose: bool = True,
) -> bool:
    """Upload a list of records to a remote SQLite DB via SSH-piped SQL.

    Generates ``INSERT`` statements from *records* and pipes them into the
    remote server's ``sqlite3`` CLI over SSH.  The remote DB file is created
    automatically by ``sqlite3`` if it does not already exist.

    Parameters
    ----------
    records : list[dict]
        Records with keys matching ``DailyStats`` columns.
    remote_db_path : str
        Absolute path to the SQLite database on the remote server.
    host : str
        Remote hostname or IP.
    username : str
        SSH username.
    port : int
        SSH port (default 22).
    key_filename : str | None
        Path to an SSH private key file.
    table_name : str
        Target table name (default ``"daily_stats"``).
    upsert : bool
        If ``True``, use ``INSERT OR REPLACE``; otherwise ``INSERT OR IGNORE``.
    batch_size : int
        Max records per ``INSERT`` statement (default 100).
    verbose : bool
        Print progress to stderr.

    Returns
    -------
    bool
        ``True`` on success, ``False`` on failure.
    """
    if not records:
        if verbose:
            print("No records to upload.", file=sys.stderr)
        return True

    if verbose:
        print(
            f"Uploading {len(records)} record(s) to {username}@{host}:{remote_db_path} "
            f"via SQL-pipe …",
            file=sys.stderr,
        )

    # ── Generate SQL ───────────────────────────────────────────────
    sql = generate_insert_sql(
        records=records,
        table_name=table_name,
        upsert=upsert,
        batch_size=batch_size,
    )

    # ── Build SSH command ──────────────────────────────────────────
    ssh_cmd = [
        "ssh",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
    ]
    if port != 22:
        ssh_cmd.extend(["-p", str(port)])
    if key_filename:
        ssh_cmd.extend(["-i", os.path.expanduser(key_filename)])

    # The remote command: feed SQL into sqlite3
    remote_cmd = f"sqlite3 {shlex.quote(remote_db_path)}"
    ssh_cmd.append(f"{username}@{host}")
    ssh_cmd.append(remote_cmd)

    if verbose:
        # Show a censored version of the command
        display_cmd = (
            f"ssh {' '.join(shlex.quote(p) for p in ssh_cmd[1:-2])} "
            f"{username}@{host} {remote_cmd}"
        )
        print(f"  Running: {display_cmd}", file=sys.stderr)

    # ── Execute ────────────────────────────────────────────────────
    try:
        proc = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print(
            "ERROR: 'ssh' command not found. Install OpenSSH client.",
            file=sys.stderr,
        )
        return False

    try:
        stdout, stderr = proc.communicate(input=sql, timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        print("ERROR: SSH pipe timed out after 120 seconds.", file=sys.stderr)
        return False

    if proc.returncode != 0:
        print(
            f"SQL-pipe upload failed (exit code {proc.returncode}):",
            file=sys.stderr,
        )
        if stderr:
            # Filter out the SQL from stderr to avoid clutter
            clean_stderr = stderr.strip()
            if clean_stderr:
                print(f"  stderr: {clean_stderr}", file=sys.stderr)
        return False

    if verbose:
        # sqlite3 may print row counts on stdout
        rows_output = stdout.strip()
        if rows_output:
            print(f"  Remote sqlite3 output: {rows_output}", file=sys.stderr)
        print(f"  Successfully uploaded {len(records)} record(s).", file=sys.stderr)

    return True


# ── CLI entry point ──────────────────────────────────────────────────

def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload local SQLite DB to a remote server via SCP.",
    )
    parser.add_argument("--host", help="Remote hostname or IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="SSH port (default: 22)")
    parser.add_argument("--username", help="SSH username (overrides config)")
    parser.add_argument(
        "--remote-path",
        dest="remote_path",
        help="Remote destination path (overrides config)",
    )
    parser.add_argument(
        "--key",
        dest="key_filename",
        help="SSH private key file path (overrides config)",
    )
    parser.add_argument(
        "--db-path",
        dest="local_db_path",
        default=None,
        help="Local DB file path (default: data/leetcode_stats.db)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test SSH connection only, don't upload",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    if args.test:
        config = load_config()
        remote_cfg = config.get("remote", {})
        host = args.host or remote_cfg.get("host")
        username = args.username or remote_cfg.get("username")
        port = args.port if args.port is not None else remote_cfg.get("port", 22)
        key = args.key_filename or remote_cfg.get("key_filename")

        if not host or not username:
            print("Provide --host and --username (or set in config.json) for connection test.")
            return 1

        print(f"Testing connection to {username}@{host}:{port} ...")
        ok = test_connection(host, username, port, key)
        print("Connection:", "OK" if ok else "FAILED")
        return 0 if ok else 1

    success = upload_to_remote(
        host=args.host,
        port=args.port,
        username=args.username,
        remote_path=args.remote_path,
        key_filename=args.key_filename,
        local_db_path=args.local_db_path,
        verbose=not args.quiet,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())