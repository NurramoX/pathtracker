import socket
import sqlite3
import os
import threading
from datetime import datetime
import logging
import sys
import signal
import argparse
from pathtracker.api.commands import Commands
from pathtracker import config
from pathtracker.config import PT_LOG_FORMAT, PT_DB_PRAGMAS, PT_PATHS_DIR, PT_SHARED_PATH, PT_SOCKET


class PathTrackerServer:
    def __init__(self, socket_path=PT_SOCKET, debug=False, db_dir=None):
        config.ensure_paths()
        self.db_dir = db_dir
        self.socket_path = socket_path
        self.db_path = config.get_db_path()
        self.running = True
        self.debug = debug
        self._setup_logging()
        self._setup_db()
        self._setup_socket()
        self._setup_signals()

    def _setup_logging(self):
        self.log = logging.getLogger('PathTracker')
        self.log.setLevel(logging.DEBUG if self.debug else logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(PT_LOG_FORMAT)
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.debug('Logging initialized')

    def _setup_signals(self):
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        self.log.info(f'Received signal {signum}, shutting down...')
        self.running = False
        self.sock.close()
        exitcode = 0
        try:
            os.unlink(self.socket_path)
        except OSError:
            self.log.error(f'Failed to unlink socket {self.socket_path}. Still exiting.')
            exitcode = 1
            pass
        sys.exit(exitcode)

    def _setup_db(self):
        with sqlite3.connect(self.db_path) as conn:
            for pragma in PT_DB_PRAGMAS:
                conn.execute(f'PRAGMA {pragma}')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS paths
                (path TEXT PRIMARY KEY, timestamp TEXT)
            ''')
        self.log.info('Database initialized')

    def _setup_socket(self):
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.socket_path)
        self.log.info(f'Socket bound to {self.socket_path}')

    def _handle_client(self, conn):
        db_conn = sqlite3.connect(self.db_path)
        try:
            with conn.makefile('rwb') as so_file:
                self._process_command(so_file, db_conn)
        finally:
            db_conn.close()
            conn.close()
            self.log.debug('Client disconnected')

    def _process_command(self, so_file, db_conn):
        """Process a single command from the socket file."""
        method = so_file.readline().strip().decode()
        if not method:
            self.log.error('Error handling client: no method was provided')
            return

        try:
            with db_conn:
                # Command pattern using dictionary
                command_handlers = {
                    Commands.PUT: self._handle_put,
                    Commands.GET: self._handle_get
                }

                handler = command_handlers.get(method)
                if handler:
                    handler(so_file, db_conn)
                else:
                    self.log.error(f'Unknown command: {method}')
                    so_file.write(f'error: Unknown command\n'.encode())
                    so_file.flush()

            # Check for bye message
            if so_file.readline().strip() == b'bye':
                return

        except Exception as e:
            self.log.error(f'Error handling client: {e}')
            so_file.write(f'error: Internal server error\n'.encode())
            so_file.flush()

    def _handle_get(self, so_file, db_conn):
        try:
            db_conn.row_factory = sqlite3.Row
            cursor = db_conn.execute('''
                SELECT path, timestamp 
                FROM paths 
                ORDER BY timestamp DESC
            ''')
            rows = cursor.fetchall()

            count = len(rows)
            so_file.write(f'ok: {count}\n'.encode())
            so_file.flush()

            for row in rows:
                so_file.write(f'{row["path"]}\n'.encode())

            so_file.flush()
            self.log.debug(f'Sent {count} paths to client')

        except Exception as e:
            self.log.error(f'Error handling get request: {e}')
            so_file.write(f'error: {str(e)}\n'.encode())
            so_file.flush()

    def _handle_put(self, so_file, db_conn):
        try:
            data = so_file.readline()
            if not data:
                return b'error: empty message\n'

            timestamp_str, path = data.decode().strip().split('|')
            dt = datetime.strptime(timestamp_str, '%d:%m:%y %H:%M:%S')
            timestamp = dt.isoformat()

            db_conn.execute('''
                    INSERT OR REPLACE INTO paths (path, timestamp) 
                    VALUES (?, ?)
                ''', (path, timestamp))

            self.log.debug(f'Inserted entry: {path} at {timestamp}')

            so_file.write("ok\n".encode())
            so_file.flush()

        except Exception as e:
            self.log.error(f'Error handling get request: {e}')
            so_file.write(f'error: {str(e)}\n'.encode())
            so_file.flush()

    def run(self):
        self.sock.listen(5)
        self.log.info('Server started, waiting for connections')
        while self.running:
            try:
                conn, addr = self.sock.accept()
                client_thread = threading.Thread(target=self._handle_client, args=(conn,))
                client_thread.start()
            except socket.error:
                if self.running:
                    self.log.error('Socket accept error')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('-t', '--db-dir',
                        default= PT_PATHS_DIR,
                        help=f'Database directory (defaults to $HOME/{PT_SHARED_PATH})')
    parser.add_argument('-s', '--socket',
                        default=PT_SOCKET,
                        help=f'Unix socket path (defaults to {PT_SOCKET})')
    args = parser.parse_args()

    tracker = PathTrackerServer(
        socket_path=args.socket,
        debug=args.debug,
        db_dir=args.db_dir
    )
    tracker.run()

if __name__ == '__main__':
    main()