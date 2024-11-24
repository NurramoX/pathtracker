import socket
from datetime import datetime
import sys
import argparse
from pathlib import Path

from pathtracker.api.commands import Commands
from pathtracker.config import PT_SOCKET


def handle_put(f):
    message = (Commands.PUT + "\n").encode()
    f.write(message)
    f.flush()

    timestamp = datetime.now().strftime('%d:%m:%y %H:%M:%S')
    path = str(Path.cwd().resolve())


    message = f'{timestamp}|{path}\n'.encode()
    f.write(message)
    f.flush()


    response = f.readline().decode().strip()

    if response == 'ok':
        message = "bye\n".encode()
        f.write(message)
        f.flush()
        return 0
    elif response.startswith('error:'):
        print(response, file=sys.stderr)
        return 1
    else:
        print(f'Unexpected response: {response}', file=sys.stderr)
        return 1



def handle_get(f):
    message = (Commands.GET + "\n").encode()
    f.write(message)
    f.flush()

    response = f.readline().decode().strip()

    if not response.lower().startswith('ok:'):
        if response.startswith('error:'):
            print(response, file=sys.stderr)
        else:
            print(f'Unexpected response: {response}', file=sys.stderr)

        return 1

    n = int(response[4:])

    entries = []
    # Read exactly n lines
    for _ in range(n):
        line = f.readline()
        if not line:  # Check for EOF
            print("Server closed connection unexpectedly", file=sys.stderr)
            return 1
        entries.append(line.decode().strip())
        
    # Send goodbye
    f.write("bye\n".encode())
    f.flush()

    # Print all entries
    for entry in entries:
        print(entry)

    return 0

def handle_command(method):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(PT_SOCKET)
            with sock.makefile('rwb') as f:
                if method == Commands.PUT:
                    return handle_put(f)
                elif method == Commands.GET:
                    return handle_get(f)
                else:
                    print('This should never happen')
                    return 1

    except ConnectionRefusedError:
        print(f'Could not connect to socket {PT_SOCKET}', file=sys.stderr)
        return 1
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

def main():
    parser = argparse.ArgumentParser(
        description='Path tracker client',
        epilog='Either --put or --get must be specified'
    )
    parser.add_argument('-s', '--socket',
                        default=PT_SOCKET,
                        help=f'Unix socket path (defaults to {PT_SOCKET})')

    # Add mutually exclusive group for commands.py
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--put', action='store_true', help='Put current path in database')
    group.add_argument('--get', action='store_true', help='Get paths from database (not yet implemented)')

    args = parser.parse_args()

    command = Commands.GET if args.get else Commands.PUT
    sys.exit(handle_command(command))

if __name__ == '__main__':
    main()