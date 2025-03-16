import streamlit as st
import os
from utils.file_utils import list_log_files_grouped

def create_sidebar():
    st.sidebar.header("Log Files Grouped by Code and Thread")
    # Directory containing your log files
    log_directory = "/workspaces/moya/moya/explainability/utterance_history"
    
    groups = list_log_files_grouped(log_directory)
    if not groups:
        st.sidebar.write("No log files found.")
        return None
    
    # Select code_name
    code_names = sorted(groups.keys())
    selected_code = st.sidebar.selectbox("Select Code Name", code_names)
    
    # Select thread_id for the chosen code
    threads = groups[selected_code]
    thread_ids = sorted(threads.keys())
    selected_thread = st.sidebar.selectbox(f"Select Thread for {selected_code}", thread_ids)
    
    # List files for that thread. Each entry is (timestamp, filename)
    entries = threads[selected_thread]
    # Create a mapping for display; here we display the filename (or you could show the timestamp)
    file_options = {f"{ts} - {fname}": fname for ts, fname in entries}
    selected_display = st.sidebar.selectbox("Select Log File", list(file_options.keys()))
    
    # Return the full path to the selected log file
    selected_file = file_options[selected_display]
    return os.path.join(log_directory, selected_file)

# import streamlit as st
# from utils.file_utils import list_dot_files

# import streamlit as st
# import os
# from utils.file_utils import list_dot_files

# def create_sidebar():
#     st.sidebar.header("Dot Files List")
#     # Specify the directory containing your dot files
#     dot_directory = "/workspaces/moya/moya/explainability/utterance_history"
#     # List dot file names (not full paths)
#     dot_files = list_dot_files(dot_directory)
#     if dot_files:
#         # Let user select one file via its name
#         selected_file_name = st.sidebar.selectbox("Select a dot file", dot_files)
#         # Return the full path
#         return os.path.join(dot_directory, selected_file_name)
#     else:
#         st.sidebar.write("No dot files found.")
#         return None

# def list_dot_files(directory):
#     return [f for f in os.listdir(directory) if f.endswith('.dot')]

# def display_sidebar(dot_files):
#     st.sidebar.title("Graphviz Dot Files")
#     selected_file = st.sidebar.selectbox("Select a dot file to visualize:", dot_files)
#     return selected_file