#!/usr/bin/env python
# License: MIT Open Source
# Copyright (c) 2016 Joe Linoff
'''
The tool runs ssh or scp as a child process with a connected psuedo
terminal (pty).

It will automatically answer yes to the "Are you sure you want to
continue connecting (yes/no)?" if it comes up.

It will automatically input the password as well which makes it really
useful for scripting.

It acts a lot like the sshpass program but is not very sophisticated.
For a more sophisticated package look at the python pexpect package.

Here is how you might use it.

   $ mkssh.py --password "secret" ssh me@host.com uptime

If you don't specify the password, you will be prompted.
'''
import argparse
import distutils.spawn
import errno
import fcntl
import io
import os
import pty
import resource
import shlex
import signal
import struct
import subprocess
import sys
import termios
import threading
import time


class ChildProcess():
    '''
    Child process object returned from the spawn method.
    '''
    def __init__(self, pid, fd):
        self.m_pid = pid  # childs pid
        self.m_fd = fd  # childs controlling terminal

        # Allow read and write operations on the childs terminal.
        self.m_fd_rds = io.open(fd, 'rb', buffering=0)
        self.m_fd_wrs = io.open(fd, 'wb', buffering=0, closefd=False)
        self.m_file = io.BufferedRWPair(self.m_fd_rds, self.m_fd_wrs)

        # These are set on exit.
        self.m_status = None
        self.m_exit_status = None
        self.m_signal_status = None

    def __del__(self):
        '''
        Destructor.

        Close down the controlling terminal.
        '''
        if self.m_fd > 0:
            os.close(self.m_fd)
            self.m_fd = 0

    def write(self, data, flush=True):
        '''
        Write data to the pipe connected to the child process and
        return the number bytes written.
        '''
        num = 0
        if self.m_file.writable():
            num = self.m_file.write(data.encode('utf-8'))
            if flush:
                self.m_file.flush()
        return num

    def read(self, num=4096):
        '''
        Read characters from the pipe connected to the child process.
        '''
        data = None
        if self.m_file.readable():
            try:
                data = self.m_file.read1(num)
            except (OSError, IOError) as exc:
                if exc.args[0] == errno.EIO:
                    data = str(exc)
                else:
                    raise
        return data

    def readline(self):
        '''
        Read a line of data from the pipe connected to the child
        process.
        '''
        data = None
        if self.m_file.readable():
            try:
                data = self.m_file.readline()
            except (OSError, IOError) as exc:
                if exc.args[0] == errno.EIO:
                    data = str(exc)
                else:
                    raise
        return data

    def kill(self, signum):
        '''
        Kill the process with signal signum.
        '''
        if self.running():
            os.kill(self.m_pid, signum)
            time.sleep(0.200)  # wait 200ms
            self.wait()

    def wait(self):
        '''
        Wait for the process to complete.
        '''
        if self.done() is False:
            while self.done() is False:
                time.sleep(0.100)
        return self.m_exit_status

    def done(self):
        '''
        Check to see of the process is done.

        This is a bit tricky because it may be a zombie
        waiting for the parent to handle the SIGCHLD signal
        generated at exit.
        '''
        if self.m_exit_status is not None:
            return True

        try:
            pid, status = os.waitpid(self.m_pid, os.WNOHANG)
            if pid == 0:
                # check for a zombie state
                path = '/proc/{}/status'.format(self.m_pid)
                if os.path.exists(path):
                    with open(path, 'r') as ifp:
                        for line in ifp.readlines():
                            line.strip()
                            if line.lower().startswith('state:'):
                                state = line.split()[1]
                                return state == 'Z'  # True if zombie
                else:
                    # This is not a linux host.
                    # Try ps -p <pid> -o state
                    cmd = 'ps -p {} -o state'.format(self.m_pid)
                    status, output = ChildProcess.run(cmd, show_output=False)
                    for line in output.split('\n'):
                        line = line.strip()
                        if 'STAT' in line:
                            continue
                        state = line
                        return state == 'Z'
                return False
            else:
                self.m_status = status
                self.m_exit_status = os.WEXITSTATUS(status)
                self.m_signal_status = os.WTERMSIG(status)
                return True
        except (OSError, IOError) as exc:
            if exc.args[0] == errno.EIO:
                return True
            raise

        return False

    @staticmethod
    def run(cmd, show_output=True):
        '''
        Execute a short running shell command with no inputs.
        Capture output and exit status.
        '''
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
            status = 0
        except subprocess.CalledProcessError as obj:
            output = obj.output.decode('ascii')
            status = obj.returncode

        output = output.decode('ascii')  # byte --> char in Python 3
        if show_output:
            sys.stdout.write(output)
            sys.stdout.flush()

        return status, output


def set_console_echo(enable=True):
    '''
    Enable or disable console echo.
    '''
    ifd = pty.STDIN_FILENO
    attr = termios.tcgetattr(ifd)
    if enable:
        # Enable echo.
        attr[3] = attr[3] | termios.ECHO
    else:
        # Disable echo.
        attr[3] = attr[3] & ~termios.ECHO
    termios.tcsetattr(ifd, termios.TCSANOW, attr)


def get_console_echo():
    '''
    True - echo
    False - noecho
    '''
    ifd = pty.STDIN_FILENO
    attr = termios.tcgetattr(ifd)
    enabled = (attr[3] & termios.ECHO) > 0
    return enabled


def get_console_winsize():
    '''
    Get the console winsize.
    '''
    for fdn in [pty.STDIN_FILENO, pty.STDOUT_FILENO]:
        try:
            packed_data = struct.pack('HHHH', 0, 0, 0, 0)
            packed_winsize = fcntl.ioctl(fdn, termios.TIOCGWINSZ, packed_data)
            winsize = struct.unpack('HHHH', packed_winsize)
            return winsize
        except IOError:
            pass
    return None


def set_console_winsize(packed_winsize):
    '''
    Set the console winsize.
    '''
    for fdn in [pty.STDIN_FILENO, pty.STDOUT_FILENO]:
        try:
            fcntl.ioctl(fdn, termios.TIOCSWINSZ, packed_winsize)
            return True
        except IOError:
            pass
    return False


def spawn(cmd, env=[]):
    '''
    Spawn a job in a pseudo-terminal and return the associated
    ChildProcess object.

    The command argument can be a list, a tuple or a string.

    The env argument, if not empty, is passed directly to os.execvp.
    '''
    if isinstance(cmd, (list, tuple)):
        cmdargs = cmd
    else:
        cmdargs = shlex.split(str(cmd))

    # Make sure that the program exists.
    program = distutils.spawn.find_executable(cmdargs[0])
    if program is None:
        # Program could not be found.
        raise Exception('program not found: {}'.format(cmdargs[0]))
    else:
        cmdargs[0] = program  # full path to program

    # Make sure the console window size is set to something
    # reasonable.
    cwinsz = get_console_winsize()
    if cwinsz is None:
        cwinsz = [24, 80, 0, 0]
        packed_cwinsz = struct.pack('HHHH', cwinsz[0],  cwinsz[1],  cwinsz[2],  cwinsz[3])
        set_console_winsize(packed_cwinsz)

    pipe_read, pipe_write = os.pipe()  # open up a pipe to the child process
    pid, fd = pty.fork()
    if pid == pty.CHILD:
        # Function to handle child exception reporting.
        def child_exception_error(exc):
            if hasattr(exc, 'errno'):
                errmsg = 'ERROR: Exception - {}, {!s} - {}'.format(exc.errno, exc, cmd)
            else:
                errmsg = 'ERROR: Exception - {!s} - {}'.format(exc, cmd)
            os.write(pipe_write, errmsg)  # will be read by pipe_read
            os.close(pipe_write)
            os._exit(os.EX_OSERR)

        # Close the read end of the pipe.
        os.close(pipe_read)

        # Close the write end of the pipe when the exec
        # is done.
        fcntl.fcntl(pipe_write, fcntl.F_SETFD, fcntl.FD_CLOEXEC)

        # Do not allow the the child to inherit any open
        # file descriptors. Only leave the pipe_write pipe
        # open for error reporting.
        max_fds = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        os.closerange(3, pipe_write)
        os.closerange(pipe_write + 1, max_fds)

        # Spawn the job.
        try:
            if env is None or len(env) == 0:
                os.execv(program, cmdargs)
            else:
                os.execvp(program, cmdargs, env)
        except OSError as exc:
            child_exception_error(exc)

    else: # parent
        time.sleep(0.050)  # git it 50ms to start
        # pipe read/write are reversed in the parent.
        os.close(pipe_write)
        exec_output = os.read(pipe_read, 8192)
        os.close(pipe_read)
        if len(exec_output):
            raise Exception('subprocess failed: {}'.format(exec_output))

        return ChildProcess(pid, fd)


def define_timeout(secs, proc):
    '''
    Set a timeout.
    '''
    def timeout(secs, proc):
        '''
        Timeout.
        '''
        sys.stderr.write('\nERROR: process {} timed out after {} seconds!\n'.format(proc.m_pid, secs))
        try:
            os.kill(proc.m_pid, signal.SIGKILL)
        except OSError:
            pass
        set_console_echo()
        os._exit(os.EX_OSERR)  # Exit the entire process

    timer = threading.Timer(secs, timeout, [secs, proc])
    timer.start()


def getopts():
    '''
    Get the command line options.
    '''
    base = os.path.basename(sys.argv[0])

    def usage():
        '''usage'''
        usage = '{0} [OPTIONS] [TARGETS]'.format(base)
        return usage

    def epilog():
        '''examples'''
        data = r'''
examples:

  $ # Example 1. Help
  $ {0} -h

  $ # Example 2. uptime, prompt for password
  $ {0} ssh me@host uptime

  $ # Example 3. uptime, pass in password
  $ {0} -p secret ssh me@host uptime

  '''.format(base)
        return data

    #afc = argparse.RawDescriptionHelpFormatter
    afc = argparse.RawTextHelpFormatter
    desc = 'description:%s' % ('\n  '.join(__doc__.split('\n')))
    parser = argparse.ArgumentParser(formatter_class=afc,
                                     description=desc[:-2],
                                     epilog=epilog(),
                                     usage=usage())

    parser.add_argument('-p', '--password',
                        action='store',
                        metavar=('STRING'),
                        help='''plaintext password,
if neither -p or -P is specified, you will be prompted
''')

    parser.add_argument('-P', '--password-file',
                        action='store',
                        metavar=('FILE'),
                        help='''file that contains the password in plain text
if neither -p or -P is specified, you will be prompted
''')

    parser.add_argument('-t', '--timeout',
                        action='store',
                        type=float,
                        default=30,
                        metavar=('SECONDS'),
                        help='timeout in seconds, default=%(default)s')

    parser.add_argument('cmd',
                        metavar=('COMMAND'),
                        nargs=argparse.REMAINDER,
                        help='ssh command, ex. ssh foo@bar.com uptime')

    opts = parser.parse_args()
    return opts


def rcp(proc, pause=0.100):
    '''
    Read from child process.
    '''
    time.sleep(pause)
    data = proc.read()
    if data is None:
        data = ''
    else:
        sys.stdout.write(data.decode('utf-8'))
        sys.stdout.flush()
    return data


def main():
    '''
    Main
    '''
    # Optimized for SSH/SCP
    try:
        opts = getopts()
        proc = spawn(opts.cmd)
        data = rcp(proc)
        define_timeout(opts.timeout, proc)

        # Automatically answer
        #       The authenticity of host '<hostname> (<ip-address>)' can't be established.
        #       RSA key fingerprint is <fingerprint>.
        #       Are you sure you want to continue connecting (yes/no)?
        if b'Are you sure you want to continue connecting' in data:
            proc.write('yes\n')
            data = rcp(proc)
            time.sleep(1)
            del proc
            proc = spawn(opts.cmd)
            data = rcp(proc)

        # Check for the password prompt.
        while b'password:' in data or b'Permission denied' in data:
            password = None
            if opts.password is not None:
                password = opts.password
            elif opts.password_file is not None:
                with open(opts.password_file, 'r') as ifp:
                    password = ifp.read()
            else:
                import getpass
                password = getpass.getpass('')

            proc.write('{}\n'.format(password))
            time.sleep(3)
            data = rcp(proc)


        # Could add other prompt responses here but that is not
        # needed at the moment since I am only doing batch operations.

        # Wait for the process to complete.
        while not proc.done():
            data = rcp(proc)

        # Exit and the childs exit status.
        exit_status = proc.m_exit_status if isinstance(proc.m_exit_status, int) else 1
        os._exit(exit_status)

    except KeyboardInterrupt:
        sys.stderr.write('\n^C interrupt.\n')
        set_console_echo()
        os._exit(os.EX_OSERR)  # Exit the entire process, including threads


if __name__ == '__main__':
    main()
