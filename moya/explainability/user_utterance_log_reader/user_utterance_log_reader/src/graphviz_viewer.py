import os
import streamlit as st
import graphviz
import re
from utils.file_utils import read_dot_file

def parse_dot_filename(filename):
    """
    Expected filename pattern:
      {timestamp}_{thread}_User_Utterance_Flow_Log_{uid}_{code}.dot
      
      Where:
        timestamp:  YYYYMMDD_HHMMSS
        thread:     {USER_NAME}_{USER_ID}_{timestamp}
        uid:        unique message id
        code:       code name (e.g., quick_start_multiagent_logged)
    
    Returns a dictionary with keys: ts, thread, uid, code.
    """
    pattern = r"^(?P<ts>\d{8}_\d{6})_(?P<thread>\w+_\w+_\d{8}_\d{6})_User_Utterance_Flow_Log_(?P<uid>[a-f0-9]+)_(?P<code>.+)\.dot$"
    m = re.match(pattern, filename)
    if m:
        return m.groupdict()
    else:
        return {}

def render_graphviz(dot_file_path):
    dot_source = read_dot_file(dot_file_path)
    # Create a graphviz Source object
    graph = graphviz.Source(dot_source)
    return graph

def display_graph(dot_file_path):
    base_filename = os.path.basename(dot_file_path)
    file_info = parse_dot_filename(base_filename)
    
    # Prepare the metadata for display
    if file_info:
        # Create Code_filename using the code value with .dot appended.
        code_filename = f"{file_info['code']}.dot"
        metadata = {
            "Code_filename": code_filename,
            "Thread ID": file_info["thread"],
            "Timestamp": file_info["ts"],
            "User Message ID": file_info["uid"],
            "Visualization type": "Utterance_Flow_Log"
        }
    else:
        metadata = {"Info": "Filename pattern does not match expected format."}
    
    # Display a subheader and table in the main area.
    st.subheader("Visualization for:")
    st.table(metadata)
    
    # Render and display the Graphviz visualization.
    graph = render_graphviz(dot_file_path)
    st.graphviz_chart(graph.source)

# import os
# import streamlit as st
# import graphviz
# from utils.file_utils import read_dot_file

# def render_graphviz(dot_file_path):
#     dot_source = read_dot_file(dot_file_path)
#     # Create a graphviz Source object
#     graph = graphviz.Source(dot_source)
#     return graph

# def display_graph(dot_file_path):
#     # Show the name of the dot file in the header
#     st.subheader(f"Visualization for: {os.path.basename(dot_file_path)}")
#     graph = render_graphviz(dot_file_path)
#     # st.graphviz_chart accepts a string source.
#     st.graphviz_chart(graph.source)