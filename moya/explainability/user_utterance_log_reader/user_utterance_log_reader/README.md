# User Utterance Log Reader

This project is a Streamlit application designed to visualize user utterance logs using Graphviz. It allows users to select and view Graphviz dot files, providing an interactive way to explore the relationships and flows within the logs.

## Project Structure

```
user_utterance_log_reader
├── src
│   ├── app.py               # Main entry point of the Streamlit application
│   ├── sidebar.py           # Sidebar functions for file selection
│   ├── graphviz_viewer.py   # Functions to render Graphviz visualizations
│   └── utils
│       └── file_utils.py    # Utility functions for file operations
├── requirements.txt          # Project dependencies
├── README.md                 # Project documentation
└── .streamlit
    └── config.toml          # Streamlit configuration settings
```

## Installation

To set up the project, follow these steps:


1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

To run the Streamlit application, execute the following command in your terminal:
```
streamlit run src/app.py
```

Once the application is running, you can access it in your web browser at `http://localhost:8501`. Use the sidebar to select a Graphviz dot file, and the visualization will be displayed in the central content area.

## Contributing

Contributions are welcome! If you have suggestions for improvements or new features, please open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.