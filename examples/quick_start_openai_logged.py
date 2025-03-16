"""
Interactive chat example using OpenAI agent with conversation memory.
"""

import os
import json
import datetime
import uuid
from moya.tools.tool_registry import ToolRegistry
from moya.registry.agent_registry import AgentRegistry
from moya.orchestrators.simple_orchestrator import SimpleOrchestrator
from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.memory.file_system_repo import FileSystemRepository
from examples.quick_tools import QuickTools
from moya.tools.base_tool import BaseTool

# Set your user metadata (could be obtained via authentication in a real system)
USER_NAME = "Alice"
USER_ID = "1234"

def setup_agent():
    # Set up memory components
    tool_registry = ToolRegistry()
    # EphemeralMemory.memory_repository = FileSystemRepository(base_path="/Users/kannan/tmp/moya_memory")
    EphemeralMemory.configure_memory_tools(tool_registry)
    tool_registry.register_tool(BaseTool(name="ConversationContext", function=QuickTools.get_conversation_context))

    config = OpenAIAgentConfig(
        agent_name="chat_agent",
        description="An interactive chat agent",
        api_key=os.getenv("OPENAI_API_KEY"),
        model_name="gpt-4o",
        agent_type="ChatAgent",
        tool_registry=tool_registry,
        is_streaming=True,
        system_prompt=("You are an interactive chat agent that can remember previous conversations. "
                       "You have access to tools that helps you to store and retrieve conversation history."
                       "Use the conversation history for your reference in answering any ueser query."
                       "Be Helpful and polite in your responses, and be concise and clear."
                       "Be useful but do not provide any information unless asked.")
    )

    # Create OpenAI agent with memory capabilities
    agent = OpenAIAgent(config)

    # Set up registry and orchestrator
    agent_registry = AgentRegistry()
    agent_registry.register_agent(agent)
    orchestrator = SimpleOrchestrator(
        agent_registry=agent_registry,
        default_agent_name="chat_agent"
    )

    return orchestrator, agent, agent_registry

def format_conversation_context(messages):
    context = "\nPrevious conversation:\n"
    for msg in messages:
        # Access Message object attributes properly using dot notation
        sender = "User" if msg.sender == "user" else "Assistant"
        context += f"{sender}: {msg.content}\n"
    return context

def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
    import os, json, datetime
    # Ensure the target directory exists
    log_dir = os.path.join("moya", "explainability", "utterance_history")
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Build thread_id as {USER_NAME}_{USER_ID}_{timestamp}
    thread_id = f"{USER_NAME}_{USER_ID}_{timestamp}"
    # Construct final filename using the new schema
    filename = f"{timestamp}_{thread_id}_User_Utterance_Flow_Log_{unique_msg_id}_quick_start_openai_logged.dot"
    filepath = os.path.join(log_dir, filename)
    
    with open(filepath, "w") as f:
        json.dump(log_data, f, indent=4)
    print(f"\nLog written to: {filepath}")
    return filepath

def main():
    orchestrator, agent, agent_registry = setup_agent()
    thread_context = json.loads(QuickTools.get_conversation_context())
    thread_id = thread_context["thread_id"]

    print("Welcome to Interactive Chat! (Type 'quit' or 'exit' to end)")
    print("-" * 50)

    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ['quit', 'exit']:
            print("\nGoodbye!")
            break

        # Create a unique ID for this user message
        unique_msg_id = uuid.uuid4().hex

        # Record the user timestamp
        user_timestamp = datetime.datetime.now().isoformat()

        # Store the user message in memory
        EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_input)

        session_summary = EphemeralMemory.get_thread_summary(thread_id)
        enriched_input = f"{session_summary}\nCurrent user message: {user_input}"

        # Build the per-message log data structure with a three-step flow
        message_log = {
            "Message1": {
                "Message Source": "User",
                "Message Destination": "Orchestrator",
                "Message Content": user_input,
                "Tools_Called_by_Message_Source": {}  # placeholder; will update next
            },
            # Step 2: Log delegation from Orchestrator to Agent (using default agent name)
            "Message2": {
                "Message Source": "Orchestrator",
                "Message Destination": "Agent",
                "Message Content": f"Delegated to agent {orchestrator.default_agent_name}",
                "Tools_Called_by_Message_Source": {}  # placeholder; will update next
            }
        }

        # Print Assistant prompt
        print("\nAssistant: ", end="", flush=True)

        # Define callback for streaming responses
        def stream_callback(chunk):
            print(chunk, end="", flush=True)

        # Orchestrator delegates to agent and returns the response
        response = orchestrator.orchestrate(
            thread_id=thread_id,
            user_message=enriched_input,
            stream_callback=stream_callback
        )

        # Store the assistant message in memory
        EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response)
        final_agent_tool_call = {
            "Tool_call_source": "Agent",
            "Tool_call_Destination": "Store",
            "Tool_call_Arguments": f"EphemeralMemory.store_message , thread_id: {thread_id}, sender: assistant, content: {response}",
            "Tool_call_Response": "Success"
        }
        

        # Log the final flow: Agent responds (via Orchestrator) to User
        message_log["Message3"] = {
            "Message Source": "Agent",
            "Message Destination": "User",
            "Message Content": response,
            "Tools_Called_by_Message_Source": {}  # placeholder; will update next
        }

        # Capture tool call logs from the agent (if any)
        tool_calls_log = {}
        idx = 0
        if hasattr(agent, "tool_call_logs"):
            # tool_calls_log = {}
            for i, call in enumerate(agent.tool_call_logs, start=1):
                tool_calls_log[f"ToolCall{i}"] = call
                idx = i+1
            # Clear logs for the next message exchange
            tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
            agent.tool_call_logs = []
        else:
            tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
        
        message_log["Message3"]["Tools_Called_by_Message_Source"] = tool_calls_log

        


        print()

        # Build the complete log data structure for this message exchange
        log_data = {
            "UserMessage": user_input,
            "UserTimestamp": user_timestamp,
            "orchestrator": {
                "type": "SimpleOrchestrator",
                "default_agent_name": orchestrator.default_agent_name
            },
            "AgentRegistry": {},
            "Message_Log": message_log
        }

        # Populate AgentRegistry details from the registry
        for agent_info in agent_registry.list_agents():
            ag = agent_registry.get_agent(agent_info.name)
            tools = {}
            if ag.tool_registry:
                for tool in ag.tool_registry.get_tools():
                    tools[tool.name] = {
                        "tool_name": tool.name,
                        "tool_description": tool.description
                    }
            log_data["AgentRegistry"][agent_info.name] = {
                "agent_name": ag.agent_name,
                "description": ag.description,
                "model_name": ag.llm_config.get("model_name", ""),
                "agent_type": ag.agent_type,
                "system_Prompt": ag.system_prompt,
                "tool_registry": tools
            }
        
        # # Write the log file for this individual user message using the unique message ID
        # write_utterance_flow_log(log_data, unique_msg_id)

        # #         # Write the log file for this individual user message using the unique message ID
        # # write_utterance_flow_log(log_data, unique_msg_id)
        
        # # Optionally: Call the Visualizer to generate a dot file from the log
        # # Construct the log file path from the printed output. Here we assume the same unique filename pattern.
        # log_filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_quick_start_openai_logged.json"
        # log_filepath = os.path.join("moya", "explainability", "utterance_history", log_filename)
        log_filepath = write_utterance_flow_log(log_data, unique_msg_id)
        # Alternatively, if you saved the filepath previously, use it.
        
        # Define a dotfile output path (change as needed)
        dot_filepath = log_filepath.replace(".json", ".dot")
        
        # Call the visualizer script via subprocess
        import subprocess
        subprocess.run([
            "python", 
            "/workspaces/moya/moya/explainability/user_utterance_visualizer/single_agent_openai_visualizer.py", 
            log_filepath, dot_filepath
        ])
        print(f"\nVisualizer dot file generated at: {dot_filepath}")
        
        # Optionally, render a PNG using Graphviz (if installed)
        png_filepath = dot_filepath.replace(".dot", ".png")
        subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
        print(f"Graph image generated at: {png_filepath}")

if __name__ == "__main__":
    main()

# """
# Interactive chat example using OpenAI agent with conversation memory.
# """

# import os
# import json
# import datetime
# import uuid
# from moya.tools.tool_registry import ToolRegistry
# from moya.registry.agent_registry import AgentRegistry
# from moya.orchestrators.simple_orchestrator import SimpleOrchestrator
# from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# from moya.tools.ephemeral_memory import EphemeralMemory
# from moya.memory.file_system_repo import FileSystemRepository
# from examples.quick_tools import QuickTools
# from moya.tools.base_tool import BaseTool

# # Set your user metadata (could be obtained via authentication in a real system)
# USER_NAME = "Alice"
# USER_ID = "1234"

# def setup_agent():
#     # Set up memory components
#     tool_registry = ToolRegistry()
#     # EphemeralMemory.memory_repository = FileSystemRepository(base_path="/Users/kannan/tmp/moya_memory")
#     EphemeralMemory.configure_memory_tools(tool_registry)
#     tool_registry.register_tool(BaseTool(name="ConversationContext", function=QuickTools.get_conversation_context))

#     config = OpenAIAgentConfig(
#         agent_name="chat_agent",
#         description="An interactive chat agent",
#         api_key=os.getenv("OPENAI_API_KEY"),
#         model_name="gpt-4o",
#         agent_type="ChatAgent",
#         tool_registry=tool_registry,
#         is_streaming=True,
#         system_prompt=("You are an interactive chat agent that can remember previous conversations. "
#                        "You have access to tools that helps you to store and retrieve conversation history."
#                        "Use the conversation history for your reference in answering any ueser query."
#                        "Be Helpful and polite in your responses, and be concise and clear."
#                        "Be useful but do not provide any information unless asked.")
#     )

#     # Create OpenAI agent with memory capabilities
#     agent = OpenAIAgent(config)

#     # Set up registry and orchestrator
#     agent_registry = AgentRegistry()
#     agent_registry.register_agent(agent)
#     orchestrator = SimpleOrchestrator(
#         agent_registry=agent_registry,
#         default_agent_name="chat_agent"
#     )

#     return orchestrator, agent, agent_registry

# def format_conversation_context(messages):
#     context = "\nPrevious conversation:\n"
#     for msg in messages:
#         # Access Message object attributes properly using dot notation
#         sender = "User" if msg.sender == "user" else "Assistant"
#         context += f"{sender}: {msg.content}\n"
#     return context

# def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
#     # Ensure the target directory exists
#     log_dir = os.path.join("moya", "explainability", "utterance_history")
#     os.makedirs(log_dir, exist_ok=True)
    
#     # Build a filename using the unique message id and current timestamp
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#     filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{timestamp}_quick_start_openai_logged.json"
#     filepath = os.path.join(log_dir, filename)
    
#     with open(filepath, "w") as f:
#         json.dump(log_data, f, indent=4)
#     print(f"\nLog written to: {filepath}")

# def main():
#     orchestrator, agent, agent_registry = setup_agent()
#     thread_context = json.loads(QuickTools.get_conversation_context())
#     thread_id = thread_context["thread_id"]

#     print("Welcome to Interactive Chat! (Type 'quit' or 'exit' to end)")
#     print("-" * 50)

#     while True:
#         # Get user input
#         user_input = input("\nYou: ").strip()
#         if user_input.lower() in ['quit', 'exit']:
#             print("\nGoodbye!")
#             break

#         # Each user input gets its own unique ID:
#         unique_msg_id = uuid.uuid4().hex

#         # Log the user message and its timestamp
#         user_timestamp = datetime.datetime.now().isoformat()
#         EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_input)
    
#         session_summary = EphemeralMemory.get_thread_summary(thread_id)
#         enriched_input = f"{session_summary}\nCurrent user message: {user_input}"

#         # Print Assistant prompt
#         print("\nAssistant: ", end="", flush=True)

#         # Define callback for streaming
#         def stream_callback(chunk):
#             print(chunk, end="", flush=True)

#         # Get response using stream_callback
#         response = orchestrator.orchestrate(
#             thread_id=thread_id,
#             user_message=enriched_input,
#             stream_callback=stream_callback
#         )

#         EphemeralMemory.store_message(thread_id=thread_id, sender="assistant", content=response)
#         print()

#         # Build the per-message log data structure
#         log_data = {
#             "UserMessage": user_input,
#             "UserTimestamp": user_timestamp,
#             "orchestrator": {
#                 "type": "SimpleOrchestrator",
#                 "default_agent_name": "chat_agent"
#             },
#             "AgentRegistry": {},
#             "Message_Log": {
#                 "Message1": {
#                     "Message Source": "User",
#                     "Message Destination": "Orchestrator",
#                     "Message Content": user_input
#                 },
#                 "Message2": {
#                     "Message Source": "Orchestrator/Assistant",
#                     "Message Destination": "User",
#                     "Message Content": response
#                 }
#             }
#         }

#         # Populate AgentRegistry details from the registry
#         for agent_info in agent_registry.list_agents():
#             # For each registered agent, get its details.
#             # (Assuming the agent instance has the fields as set in OpenAIAgentConfig)
#             ag = agent_registry.get_agent(agent_info.name)
#             tools = {}
#             if ag.tool_registry:
#                 for tool in ag.tool_registry.get_tools():
#                     tools[tool.name] = {
#                         "tool_name": tool.name,
#                         "tool_description": tool.description
#                     }
#             log_data["AgentRegistry"][agent_info.name] = {
#                 "agent_name": ag.agent_name,
#                 "description": ag.description,
#                 "model_name": ag.llm_config.get("model_name", ""),
#                 "agent_type": ag.agent_type,
#                 "system_Prompt": ag.system_prompt,
#                 "tool_registry": tools
#             }
        
#         # Write the log file for this individual user message
#         write_utterance_flow_log(log_data, unique_msg_id)

# if __name__ == "__main__":
#     main()