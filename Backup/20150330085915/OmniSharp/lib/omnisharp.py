import os
import sublime
import threading
import json
import urllib
import urllib.parse
import urllib.request
import socket
import subprocess
import queue
import traceback
import sys
import signal

from .helpers import get_settings
from .helpers import current_solution_or_folder
from .helpers import current_project_folder
from .helpers import current_solution_or_project_json_folder

from queue import Queue

IS_EXTERNAL_SERVER_ENABLE = False
IS_NT_CONSOLE_VISIBLE = False

launcher_procs = {
}

server_ports = {
}

class WorkerThread(threading.Thread):
    _worker_threads = []
    _worker_queue = Queue()

    def run(self):
        while True:
            url, data, timeout, callback = self._worker_queue.get()
            try:
                proxy = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy)
                response = opener.open(url, data, timeout)
                callback(response.read())
            except:
                traceback.print_exc(file=sys.stdout)
                callback(None)

    @classmethod
    def make_worker_threads(cls, count):
        while len(cls._worker_threads) < count:
            new_worker_thread = cls()
            new_worker_thread.start()
            cls._worker_threads.append(new_worker_thread)

    @classmethod
    def add_work(cls, url, data, timeout, callback):
        cls._worker_queue.put((url, data, timeout, callback))

WorkerThread.make_worker_threads(1)

def urlopen_async(url, callback, data, timeout):
    WorkerThread.add_work(url, data, timeout, callback)

def get_response(view, endpoint, callback, params=None, timeout=None):
    solution_path =  current_solution_or_project_json_folder(view)#current_solution_or_folder(view)

    print('response:', solution_path)
    if solution_path is None or solution_path not in server_ports:
        callback(None)
        return
        
    parameters = {}
    location = view.sel()[0]
    cursor = view.rowcol(location.begin())

    parameters['line'] = str(cursor[0] + 1)
    parameters['column'] = str(cursor[1] + 1)
    parameters['buffer'] = view.substr(sublime.Region(0, view.size()))
    parameters['filename'] = view.file_name()

    if params is not None:
        parameters.update(params)
    if timeout is None:
        timeout = int(get_settings(view, 'omnisharp_response_timeout'))

    host = 'localhost'
    port = server_ports[solution_path]

    httpurl = "http://%s:%s/" % (host, port)

    target = urllib.parse.urljoin(httpurl, endpoint)
    data = urllib.parse.urlencode(parameters).encode('utf-8')
    print('request: %s' % target)
    print('======== request params ======== \n %s' % json.dumps(parameters))

    def urlopen_callback(data):
        print('======== response ========')
        if data is None:
            print(None)
            # traceback.print_stack(file=sys.stdout)
            print('CALLBACK_ERROR')
            callback(None)

            # if solution_path in launcher_procs:
            #     print('TERMINATE_OMNI_SHARP')
            #     launcher_procs[solution_path].terminate();

            #     del launcher_procs[solution_path]
            #     del server_ports[solution_path]

        else:
            jsonStr = data.decode('utf-8')
            print(jsonStr)
            jsonObj = json.loads(jsonStr)
            # traceback.print_stack(file=sys.stdout)
            print('callback data')
            callback(jsonObj)

    urlopen_async(
        target,
        urlopen_callback,
        data,
        timeout)


def get_response_from_empty_httppost(view, endpoint, callback, timeout=None):
    solution_path =  current_solution_or_project_json_folder(view)#current_solution_or_folder(view)

    print(solution_path)
    print(server_ports)
    if solution_path is None or solution_path not in server_ports:
        callback(None)
        return
    parameters = {}
    location = view.sel()[0]
    cursor = view.rowcol(location.begin())

    if timeout is None:
        timeout = int(get_settings(view, 'omnisharp_response_timeout'))

    host = 'localhost'
    port = server_ports[solution_path]

    httpurl = "http://%s:%s/" % (host, port)

    target = urllib.parse.urljoin(httpurl, endpoint)
    data = urllib.parse.urlencode(parameters).encode('utf-8')
    print('request: %s' % target)
    print('======== no request params ======== \n')

    def urlopen_callback(data):
        print('======== response ========')
        if data is None:
            print(None)
            # traceback.print_stack(file=sys.stdout)
            print('callback none')
            callback(None)
        else:
            jsonStr = data.decode('utf-8')
            print(jsonStr)
            jsonObj = json.loads(jsonStr)
            # traceback.print_stack(file=sys.stdout)
            print('callback data')
            callback(jsonObj)

    urlopen_async(
        target,
        urlopen_callback,
        data,
        timeout)


def _available_port():
    if IS_EXTERNAL_SERVER_ENABLE:
        return 2000

    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    return port

def _run_omni_sharp_launcher(solution_path, port, config_file):
    source_file_path = os.path.realpath(__file__)
    source_dir_path = os.path.dirname(source_file_path)
    plugin_dir_path = os.path.dirname(source_dir_path)
    launcher_file_path = os.path.join(plugin_dir_path, 'launchers', 'omni_sharp_launcher.py')
    print('LAUNCH!!!',launcher_file_path)

    if os.name == 'posix':
        args = [
            'python',
            launcher_file_path, 
            '-S', solution_path,
            '-P', str(port),
            '-I', str(os.getpid()),
            '-config', config_file
        ]

        startupinfo = None

    else:
        args = [
            'python',
            launcher_file_path, 
            '-S', solution_path,
            '-P', str(port),
            '-I', str(os.getpid()),
            '-config', config_file
        ]

        if IS_NT_CONSOLE_VISIBLE:
            startupinfo = None
        else:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

    
    new_proc = subprocess.Popen(args, startupinfo=startupinfo)

    try:
        launcher_communication_thread = threading.Thread(
            target=_communicate_omni_sharp_launcher, 
            args=(new_proc, solution_path))

        launcher_communication_thread.start()

    except Exception as e:
        new_proc.terminate()
        raise e

    return new_proc

def _communicate_omni_sharp_launcher(launcher_proc, solution_path):
    print('start_omni_sharp_launcher:%s' % solution_path)
    stdin_data, stderr_data = launcher_proc.communicate()
    if not stderr_data:
        print('exit_omni_sharp_launcher:%s' % solution_path)
        return

    for stderr_line in stderr_data.splitlines():
        print('stop_omni_sharp_launcher:%s error:%s' % (target_name, stderr_line))


def create_omnisharp_server_subprocess(view):
    solution_path = current_solution_or_project_json_folder(view) #current_solution_or_folder(view)
    if solution_path in launcher_procs:
        print("already_bound_solution:%s" % solution_path)
        return

    print("solution_path:%s" % solution_path)

    omni_port = _available_port()
    print('omni_port:%s' % omni_port)
    
    
    config_file = get_settings(view, "omnisharp_server_config_location")

    if IS_EXTERNAL_SERVER_ENABLE:
        launcher_proc = None
        omni_port = 2000
    else:
        try:
            launcher_proc = _run_omni_sharp_launcher(
                solution_path,
                omni_port,
                config_file)
        except Exception as e:
            print('RAISE_OMNI_SHARP_LAUNCHER_EXCEPTION:%s' % repr(e))
            return

    launcher_procs[solution_path] = launcher_proc
    server_ports[solution_path] = omni_port

