import os
import re

LOG_FILENAME_REGEX = r"^(?P<ts>\d{8}_\d{6})_(?P<thread>.*?)_User_Utterance_Flow_Log_(?P<uid>[a-f0-9]+)_(?P<code>.*)\.dot$"

def list_log_files(directory):
    """
    Returns a list of log file names (not full paths) from the given directory.
    """
    if not os.path.exists(directory):
        return []
    return [f for f in os.listdir(directory) if f.endswith('.dot')]

def list_log_files_grouped(directory):
    """
    Groups log files by code_name and thread_id.
    
    The log filename pattern is expected to be:
       {timestamp}_{thread_id}_User_Utterance_Flow_Log_{unique_msg_id}_{code_name}.dot
       
    Returns a dictionary structured as:
      {
          code_name: {
              thread_id: [ (timestamp, filename), ... sorted descending by timestamp ]
          },
          ...
      }
    """
    groups = {}
    for fname in list_log_files(directory):
        m = re.match(LOG_FILENAME_REGEX, fname)
        if m:
            ts = m.group("ts")
            thread = m.group("thread")
            code = m.group("code")
            groups.setdefault(code, {}).setdefault(thread, []).append((ts, fname))
    # Now sort each list for a given thread in descending order by timestamp
    for code, threads in groups.items():
        for thread, entries in threads.items():
            # sort descending by timestamp string
            threads[thread] = sorted(entries, key=lambda x: x[0], reverse=True)
    return groups

def read_log_file(filepath):
    with open(filepath, 'r') as file:
        return file.read()

def read_dot_file(filepath):
    """
    Reads a Graphviz dot file and returns its content as a string.
    """
    with open(filepath, 'r') as file:
        return file.read()
# import os

# def list_dot_files(directory):
#     """
#     Returns a list of dot file names (not full paths) from the given directory.
#     """
#     if not os.path.exists(directory):
#         return []
#     return [f for f in os.listdir(directory) if f.endswith('.dot')]

# def read_dot_file(filepath):
#     with open(filepath, 'r') as file:
#         return file.read()