import streamlit as st
from sidebar import create_sidebar
from graphviz_viewer import display_graph

def main():
    st.title("User Utterance Log Reader")
    
    # Create the sidebar for file selection
    selected_file = create_sidebar()

    # Central content area for displaying the Graphviz visualization
    if selected_file:
        display_graph(selected_file)
    else:
        st.write("Please select a dot file from the sidebar to display its visualization.")

if __name__ == "__main__":
    main()