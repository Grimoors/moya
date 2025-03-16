import re
import os
import json
import datetime
import uuid
import subprocess

from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
from moya.classifiers.llm_classifier import LLMClassifier
from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
from moya.registry.agent_registry import AgentRegistry
from moya.tools.ephemeral_memory import EphemeralMemory
from moya.tools.tool_registry import ToolRegistry

# Set your user metadata (could be obtained via authentication in a real system)
USER_NAME = "Alice"
USER_ID = "1234"

def setup_memory_components():
    """Set up memory components for the agents."""
    tool_registry = ToolRegistry()
    EphemeralMemory.configure_memory_tools(tool_registry)
    return tool_registry

def create_english_agent(tool_registry):
    """Create an English-speaking OpenAI agent."""
    agent_config = OpenAIAgentConfig(
        agent_name="english_agent",
        agent_type="ChatAgent",
        description="English language specialist",
        system_prompt=(
            "You are a helpful AI assistant that always responds in English. "
            "You should be polite, informative, and maintain a professional tone."
        ),
        llm_config={'temperature': 0.7},
        model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    return OpenAIAgent(config=agent_config)

def create_spanish_agent(tool_registry) -> OpenAIAgent:
    """Create a Spanish-speaking OpenAI agent."""
    agent_config = OpenAIAgentConfig(
        agent_name="spanish_agent",
        agent_type="ChatAgent",
        description="Spanish language specialist that provides responses only in Spanish",
        system_prompt=(
            "Eres un asistente de IA servicial que siempre responde en español. "
            "Debes ser educado, informativo y mantener un tono profesional. "
            "Si te piden hablar en otro idioma, declina cortésmente y continúa en español."
        ),
        llm_config={'temperature': 0.7},
        model_name="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    return OpenAIAgent(config=agent_config)

def create_remote_agent(tool_registry) -> RemoteAgent:
    """Create a remote agent for joke-related queries."""
    return RemoteAgent(
        config=RemoteAgentConfig(
            agent_name="joke_agent",
            agent_type="RemoteAgent",
            description="Remote agent specialized in telling jokes",
            base_url="http://localhost:8000",
            verify_ssl=True,
            auth_token="your-secret-token-here",
            tool_registry=tool_registry,
        )
    )

def create_classifier_agent() -> OpenAIAgent:
    """Create a classifier agent for language and task detection."""
    system_prompt = (
        "You are a classifier. Your job is to determine the best agent based on the user's message:\n"
        "1. If the message requests or implies a need for a joke, return 'joke_agent'\n"
        "2. If the message is in English or requests English response, return 'english_agent'\n"
        "3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'\n"
        "4. For any other language requests, return null\n\n"
        "Analyze both the language and intent of the message and return only the agent name as specified."
    )
    agent_config = OpenAIAgentConfig(
        agent_name="classifier",
        agent_type="AgentClassifier",
        description="Language and task classifier for routing messages",
        tool_registry=None,
        model_name="gpt-4o",
        system_prompt=system_prompt,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    return OpenAIAgent(config=agent_config)

def setup_orchestrator():
    """Set up the multi-agent orchestrator with all components."""
    tool_registry = setup_memory_components()
    english_agent = create_english_agent(tool_registry)
    spanish_agent = create_spanish_agent(tool_registry)
    joke_agent = create_remote_agent(tool_registry)
    classifier_agent = create_classifier_agent()
    registry = AgentRegistry()
    registry.register_agent(english_agent)
    registry.register_agent(spanish_agent)
    registry.register_agent(joke_agent)
    classifier = LLMClassifier(classifier_agent, default_agent="english_agent")
    orchestrator = MultiAgentOrchestrator(
        agent_registry=registry,
        classifier=classifier,
        default_agent_name=None
    )
    return orchestrator

def call_store_tool(thread_id, sender, content, agent):
    """Call the Store tool via the tool registry and return a log entry."""
    store_tool = None
    if agent.tool_registry:
        store_tool = agent.tool_registry.get_tool("Store")
    if store_tool:
        result = store_tool.function(thread_id=thread_id, sender=sender, content=content)
        tool_call_log = {
            "Tool_call_source": agent.agent_name,
            "Tool_call_Destination": store_tool.name,
            "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
            "Tool_call_Response": result
        }
    else:
        result = EphemeralMemory.store_message(thread_id=thread_id, sender=sender, content=content)
        tool_call_log = {
            "Tool_call_source": agent.agent_name,
            "Tool_call_Destination": "Store",
            "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
            "Tool_call_Response": result
        }
    return tool_call_log

def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
    """Write the log file for a single user query and return the filepath."""
    import os, json, datetime
    # from moya.examples.quick_start_multiagent_logged import USER_NAME, USER_ID  # adjust import as necessary
    
    log_dir = os.path.join("moya", "explainability", "utterance_history")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    thread_id = f"{USER_NAME}_{USER_ID}_{timestamp}"
    filename = f"{timestamp}_{thread_id}_User_Utterance_Flow_Log_{unique_msg_id}_quick_start_multiagent_logged.json"
    filepath = os.path.join(log_dir, filename)
    with open(filepath, "w") as f:
        json.dump(log_data, f, indent=4)
    print(f"\nLog written to: {filepath}")
    return filepath

def main():
    orchestrator = setup_orchestrator()
    thread_id = "single_query_thread"
    print("Starting multi-agent chat logging (type 'exit' to quit)")
    print("Enter your query and see the logging flow (User → Orchestrator → Agent → Tools → User).")
    print("-" * 50)
    while True:
        user_message = input("\nYou: ").strip()
        if user_message.lower() == 'exit':
            print("\nGoodbye!")
            break

        unique_msg_id = uuid.uuid4().hex
        user_timestamp = datetime.datetime.now().isoformat()

        # ----- Conversation History Pull -----
        # Store the user message first
        EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
        # Retrieve conversation history (summary) for this thread
        session_summary = EphemeralMemory.get_thread_summary(thread_id)
        # Build enriched input including the conversation history
        enriched_input = f"{session_summary}\nCurrent user message: {user_message}"
        # ---------------------------------------

        # Log Message1: User -> Orchestrator (include the enriched input)
        message_log = {
            "Message1": {
                "Message Source": "User",
                "Message Destination": "Orchestrator",
                "Message Content": enriched_input,
                "Tools_Called_by_Message_Source": {}
            }
        }

        def stream_callback(chunk):
            print(chunk, end="", flush=True)

        agents = orchestrator.agent_registry.list_agents()
        if not agents:
            print("\nNo agents available!")
            continue
        selected_agent = orchestrator.agent_registry.get_agent(agents[0].name)

        # Call the orchestrator with the enriched input (conversation history + current message)
        response = orchestrator.orchestrate(
            thread_id=thread_id,
            user_message=enriched_input,
            stream_callback=stream_callback
        )
        print()  # newline after response

        # Detect agent tag if present and update selected_agent (using agent_name)
        pattern = r'^\[(.*?)\]\s*(.*)'
        match = re.match(pattern, response)
        if match:
            used_agent_name = match.group(1)
            cleaned_response = match.group(2)
            for agent in agents:
                if getattr(agent, "name", None) == used_agent_name:
                    selected_agent = agent
                    break
            response = cleaned_response

        # Log Message2: Orchestrator -> Selected Agent
        message_log["Message2"] = {
            "Message Source": "Orchestrator",
            "Message Destination": selected_agent.name,
            "Message Content": f"Delegated to agent {selected_agent.name}",
            "Tools_Called_by_Message_Source": {}
        }

        final_agent_tool_call = {
            "Tool_call_source": selected_agent.name,
            "Tool_call_Destination": "Store",
            "Tool_call_Arguments": f"thread_id: {thread_id}, sender: assistant, content: {response}",
            "Tool_call_Response": "Success"
        }

        tool_calls_log = {}
        idx = 1
        if hasattr(selected_agent, "tool_call_logs"):
            for call in selected_agent.tool_call_logs:
                tool_calls_log[f"ToolCall{idx}"] = call
                idx += 1
            tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
            selected_agent.tool_call_logs = []
        else:
            tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call

        # Log Message3: Agent (and tool calls) -> User
        message_log["Message3"] = {
            "Message Source": selected_agent.name,
            "Message Destination": "User",
            "Message Content": response,
            "Tools_Called_by_Message_Source": tool_calls_log
        }

        log_data = {
            "UserMessage": user_message,
            "UserTimestamp": user_timestamp,
            "orchestrator": {
                "type": "MultiAgentOrchestrator",
                "default_agent_name": orchestrator.classifier.default_agent
            },
            "AgentRegistry": {},
            "Message_Log": message_log
        }

        for agent_info in orchestrator.agent_registry.list_agents():
            ag = orchestrator.agent_registry.get_agent(agent_info.name)
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
        
        log_filepath = write_utterance_flow_log(log_data, unique_msg_id)
        dot_filepath = log_filepath.replace(".json", ".dot")
        subprocess.run([
            "python", 
            "/workspaces/moya/moya/explainability/user_utterance_visualizer/multi_agent_openai_visualizer.py", 
            log_filepath, dot_filepath
        ])
        print(f"\nVisualizer dot file generated at: {dot_filepath}")
        png_filepath = dot_filepath.replace(".dot", ".png")
        subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
        print(f"Graph image generated at: {png_filepath}")

if __name__ == "__main__":
    main()

# import re
# import os
# import json
# import datetime
# import uuid
# import subprocess

# from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
# from moya.classifiers.llm_classifier import LLMClassifier
# from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
# from moya.registry.agent_registry import AgentRegistry
# from moya.tools.ephemeral_memory import EphemeralMemory
# from moya.tools.tool_registry import ToolRegistry

# # Set your user metadata (could be obtained via authentication in a real system)
# USER_NAME = "Alice"
# USER_ID = "1234"


# def setup_memory_components():
#     """Set up memory components for the agents."""
#     tool_registry = ToolRegistry()
#     EphemeralMemory.configure_memory_tools(tool_registry)
#     return tool_registry


# def create_english_agent(tool_registry):
#     """Create an English-speaking OpenAI agent."""
#     agent_config = OpenAIAgentConfig(
#         agent_name="english_agent",
#         agent_type="ChatAgent",
#         description="English language specialist",
#         system_prompt=(
#             "You are a helpful AI assistant that always responds in English. "
#             "You should be polite, informative, and maintain a professional tone."
#         ),
#         llm_config={'temperature': 0.7},
#         model_name="gpt-4o",
#         api_key=os.getenv("OPENAI_API_KEY")
#     )
#     return OpenAIAgent(config=agent_config)


# def create_spanish_agent(tool_registry) -> OpenAIAgent:
#     """Create a Spanish-speaking OpenAI agent."""
#     agent_config = OpenAIAgentConfig(
#         agent_name="spanish_agent",
#         agent_type="ChatAgent",
#         description="Spanish language specialist that provides responses only in Spanish",
#         system_prompt=(
#             "Eres un asistente de IA servicial que siempre responde en español. "
#             "Debes ser educado, informativo y mantener un tono profesional. "
#             "Si te piden hablar en otro idioma, declina cortésmente y continúa en español."
#         ),
#         llm_config={'temperature': 0.7},
#         model_name="gpt-4o",
#         api_key=os.getenv("OPENAI_API_KEY")
#     )
#     return OpenAIAgent(config=agent_config)


# def create_remote_agent(tool_registry) -> RemoteAgent:
#     """Create a remote agent for joke-related queries."""
#     return RemoteAgent(
#         config=RemoteAgentConfig(
#             agent_name="joke_agent",
#             agent_type="RemoteAgent",
#             description="Remote agent specialized in telling jokes",
#             base_url="http://localhost:8000",
#             verify_ssl=True,
#             auth_token="your-secret-token-here",
#             tool_registry=tool_registry,
#         )
#     )


# def create_classifier_agent() -> OpenAIAgent:
#     """Create a classifier agent for language and task detection."""
#     system_prompt = (
#         "You are a classifier. Your job is to determine the best agent based on the user's message:\n"
#         "1. If the message requests or implies a need for a joke, return 'joke_agent'\n"
#         "2. If the message is in English or requests English response, return 'english_agent'\n"
#         "3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'\n"
#         "4. For any other language requests, return null\n\n"
#         "Analyze both the language and intent of the message and return only the agent name as specified."
#     )

#     agent_config = OpenAIAgentConfig(
#         agent_name="classifier",
#         agent_type="AgentClassifier",
#         description="Language and task classifier for routing messages",
#         tool_registry=None,
#         model_name="gpt-4o",
#         system_prompt=system_prompt,
#         api_key=os.getenv("OPENAI_API_KEY")
#     )
#     return OpenAIAgent(config=agent_config)


# def setup_orchestrator():
#     """Set up the multi-agent orchestrator with all components."""
#     tool_registry = setup_memory_components()

#     # Create agents
#     english_agent = create_english_agent(tool_registry)
#     spanish_agent = create_spanish_agent(tool_registry)
#     joke_agent = create_remote_agent(tool_registry)
#     classifier_agent = create_classifier_agent()

#     # Set up agent registry
#     registry = AgentRegistry()
#     registry.register_agent(english_agent)
#     registry.register_agent(spanish_agent)
#     registry.register_agent(joke_agent)

#     # Create and configure the classifier
#     classifier = LLMClassifier(classifier_agent, default_agent="english_agent")

#     # Create the orchestrator
#     orchestrator = MultiAgentOrchestrator(
#         agent_registry=registry,
#         classifier=classifier,
#         default_agent_name=None
#     )

#     return orchestrator


# def call_store_tool(thread_id, sender, content, agent):
#     """
#     Call the Store tool via the tool registry rather than calling EphemeralMemory.store_message directly.
#     This function also returns a log entry with the correct tool name.
#     """
#     store_tool = None
#     if agent.tool_registry:
#         store_tool = agent.tool_registry.get_tool("Store")
#     if store_tool:
#         result = store_tool.function(thread_id=thread_id, sender=sender, content=content)
#         tool_call_log = {
#             "Tool_call_source": agent.agent_name,
#             "Tool_call_Destination": store_tool.name,
#             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
#             "Tool_call_Response": result
#         }
#     else:
#         result = EphemeralMemory.store_message(thread_id=thread_id, sender=sender, content=content)
#         tool_call_log = {
#             "Tool_call_source": agent.agent_name,
#             "Tool_call_Destination": "Store",
#             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
#             "Tool_call_Response": result
#         }
#     return tool_call_log


# def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
#     """Write the log file for a single user query and return the filepath."""
#     log_dir = os.path.join("moya", "explainability", "utterance_history")
#     os.makedirs(log_dir, exist_ok=True)
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#     filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{timestamp}_quick_start_multiagent_logged.json"
#     filepath = os.path.join(log_dir, filename)
#     with open(filepath, "w") as f:
#         json.dump(log_data, f, indent=4)
#     print(f"\nLog written to: {filepath}")
#     return filepath


# def main():
#     orchestrator = setup_orchestrator()
#     thread_context = json.loads(QuickTools.get_conversation_context())
#     thread_id = "single_query_thread"

#     print("Starting multi-agent chat logging (type 'exit' to quit)")
#     print("Enter your query and see the logging flow.")
#     print("-" * 50)

#     while True:
#         user_message = input("\nYou: ").strip()
#         if user_message.lower() == 'exit':
#             print("\nGoodbye!")
#             break

#         # Generate a unique ID for this log
#         unique_msg_id = uuid.uuid4().hex
#         user_timestamp = datetime.datetime.now().isoformat()

#         # Store the user message in memory
#         EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)

#         # Retrieve conversation history (summary) for this thread
#         session_summary = EphemeralMemory.get_thread_summary(thread_id)
#         # Build enriched input including the conversation history
#         enriched_input = f"{session_summary}\nCurrent user message: {user_message}"
#         # ---------------------------------------

#         # Log Message1: User -> Orchestrator
#         message_log = {
#             "Message1": {
#                 "Message Source": "User",
#                 "Message Destination": "Orchestrator",
#                 "Message Content": enriched_input,
#                 "Tools_Called_by_Message_Source": {}
#             }
#         }

#         def stream_callback(chunk):
#             print(chunk, end="", flush=True)

#         # Select an agent: use the first available by default.
#         agents = orchestrator.agent_registry.list_agents()
#         if not agents:
#             print("\nNo agents available!")
#             continue
#         selected_agent = orchestrator.agent_registry.get_agent(agents[0].name)

#         # --- New code to detect and adjust agent selection ---
#         # If the response begins with an agent tag in the format "[agent_name] ..."
#         # we want to update selected_agent to the corresponding agent object.
#         response = orchestrator.orchestrate(
#             thread_id=thread_id,
#             user_message=enriched_input,
#             stream_callback=stream_callback
#         )
#         print()  # newline after response

#         pattern = r'^\[(.*?)\]\s*(.*)'
#         match = re.match(pattern, response)
#         if match:
#             used_agent_name = match.group(1)
#             cleaned_response = match.group(2)
#             for agent in agents:
#                 if getattr(agent, "name", None) == used_agent_name:
#                     selected_agent = agent
#                     break
#             response = cleaned_response  # update response without the tag
#         # --- End new code ---

#         # Log Message2: Orchestrator -> Selected Agent
#         message_log["Message2"] = {
#             "Message Source": "Orchestrator",
#             "Message Destination": selected_agent.name,
#             "Message Content": f"Delegated to agent {selected_agent.name}",
#             "Tools_Called_by_Message_Source": {}
#         }

#         # Instead of calling store_message directly, we'll later add the tool call log.
#         final_agent_tool_call = {
#             "Tool_call_source": selected_agent.name,
#             "Tool_call_Destination": "Store",
#             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: assistant, content: {response}",
#             "Tool_call_Response": "Success"
#         }

#         tool_calls_log = {}
#         idx = 1
#         if hasattr(selected_agent, "tool_call_logs"):
#             for call in selected_agent.tool_call_logs:
#                 tool_calls_log[f"ToolCall{idx}"] = call
#                 idx += 1
#             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
#             selected_agent.tool_call_logs = []
#         else:
#             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call

#         # Log Message3: Agent (and any tool calls) -> User
#         message_log["Message3"] = {
#             "Message Source": selected_agent.name,
#             "Message Destination": "User",
#             "Message Content": response,
#             "Tools_Called_by_Message_Source": tool_calls_log
#         }

#         log_data = {
#             "UserMessage": user_message,
#             "UserTimestamp": user_timestamp,
#             "orchestrator": {
#                 "type": "MultiAgentOrchestrator",
#                 "default_agent_name": orchestrator.classifier.default_agent
#             },
#             "AgentRegistry": {},
#             "Message_Log": message_log
#         }

#         for agent_info in orchestrator.agent_registry.list_agents():
#             ag = orchestrator.agent_registry.get_agent(agent_info.name)
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

#         log_filepath = write_utterance_flow_log(log_data, unique_msg_id)
#         dot_filepath = log_filepath.replace(".json", ".dot")
#         subprocess.run([
#             "python", 
#             "/workspaces/moya/moya/explainability/user_utterance_visualizer/multi_agent_openai_visualizer.py", 
#             log_filepath, dot_filepath
#         ])
#         print(f"\nVisualizer dot file generated at: {dot_filepath}")
#         png_filepath = dot_filepath.replace(".dot", ".png")
#         subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
#         print(f"Graph image generated at: {png_filepath}")


# if __name__ == "__main__":
#     main()


# # import re
# # import os
# # import json
# # import datetime
# # import uuid
# # import subprocess

# # from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# # from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
# # from moya.classifiers.llm_classifier import LLMClassifier
# # from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
# # from moya.registry.agent_registry import AgentRegistry
# # from moya.tools.ephemeral_memory import EphemeralMemory
# # from moya.tools.tool_registry import ToolRegistry

# # # Set your user metadata (could be obtained via authentication in a real system)
# # USER_NAME = "Alice"
# # USER_ID = "1234"


# # def setup_memory_components():
# #     """Set up memory components for the agents."""
# #     tool_registry = ToolRegistry()
# #     EphemeralMemory.configure_memory_tools(tool_registry)
# #     return tool_registry


# # def create_english_agent(tool_registry):
# #     """Create an English-speaking OpenAI agent."""
# #     agent_config = OpenAIAgentConfig(
# #         agent_name="english_agent",
# #         agent_type="ChatAgent",
# #         description="English language specialist",
# #         system_prompt=(
# #             "You are a helpful AI assistant that always responds in English. "
# #             "You should be polite, informative, and maintain a professional tone."
# #         ),
# #         llm_config={'temperature': 0.7},
# #         model_name="gpt-4o",
# #         api_key=os.getenv("OPENAI_API_KEY")
# #     )
# #     return OpenAIAgent(config=agent_config)


# # def create_spanish_agent(tool_registry) -> OpenAIAgent:
# #     """Create a Spanish-speaking OpenAI agent."""
# #     agent_config = OpenAIAgentConfig(
# #         agent_name="spanish_agent",
# #         agent_type="ChatAgent",
# #         description="Spanish language specialist that provides responses only in Spanish",
# #         system_prompt=(
# #             "Eres un asistente de IA servicial que siempre responde en español. "
# #             "Debes ser educado, informativo y mantener un tono profesional. "
# #             "Si te piden hablar en otro idioma, declina cortésmente y continúa en español."
# #         ),
# #         llm_config={'temperature': 0.7},
# #         model_name="gpt-4o",
# #         api_key=os.getenv("OPENAI_API_KEY")
# #     )
# #     return OpenAIAgent(config=agent_config)


# # def create_remote_agent(tool_registry) -> RemoteAgent:
# #     """Create a remote agent for joke-related queries."""
# #     return RemoteAgent(
# #         config=RemoteAgentConfig(
# #             agent_name="joke_agent",
# #             agent_type="RemoteAgent",
# #             description="Remote agent specialized in telling jokes",
# #             base_url="http://localhost:8000",
# #             verify_ssl=True,
# #             auth_token="your-secret-token-here",
# #             tool_registry=tool_registry,
# #         )
# #     )


# # def create_classifier_agent() -> OpenAIAgent:
# #     """Create a classifier agent for language and task detection."""
# #     system_prompt = (
# #         "You are a classifier. Your job is to determine the best agent based on the user's message:\n"
# #         "1. If the message requests or implies a need for a joke, return 'joke_agent'\n"
# #         "2. If the message is in English or requests English response, return 'english_agent'\n"
# #         "3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'\n"
# #         "4. For any other language requests, return null\n\n"
# #         "Analyze both the language and intent of the message and return only the agent name as specified."
# #     )

# #     agent_config = OpenAIAgentConfig(
# #         agent_name="classifier",
# #         agent_type="AgentClassifier",
# #         description="Language and task classifier for routing messages",
# #         tool_registry=None,
# #         model_name="gpt-4o",
# #         system_prompt=system_prompt,
# #         api_key=os.getenv("OPENAI_API_KEY")
# #     )
# #     return OpenAIAgent(config=agent_config)


# # def setup_orchestrator():
# #     """Set up the multi-agent orchestrator with all components."""
# #     tool_registry = setup_memory_components()

# #     # Create agents
# #     english_agent = create_english_agent(tool_registry)
# #     spanish_agent = create_spanish_agent(tool_registry)
# #     joke_agent = create_remote_agent(tool_registry)
# #     classifier_agent = create_classifier_agent()

# #     # Set up agent registry
# #     registry = AgentRegistry()
# #     registry.register_agent(english_agent)
# #     registry.register_agent(spanish_agent)
# #     registry.register_agent(joke_agent)

# #     # Create and configure the classifier
# #     classifier = LLMClassifier(classifier_agent, default_agent="english_agent")

# #     # Create the orchestrator
# #     orchestrator = MultiAgentOrchestrator(
# #         agent_registry=registry,
# #         classifier=classifier,
# #         default_agent_name=None
# #     )

# #     return orchestrator


# # def call_store_tool(thread_id, sender, content, agent):
# #     """
# #     Call the Store tool via the tool registry rather than calling EphemeralMemory.store_message directly.
# #     This function also returns a log entry with the correct tool name.
# #     """
# #     store_tool = None
# #     if agent.tool_registry:
# #         # Try to retrieve the tool named "Store"
# #         store_tool = agent.tool_registry.get_tool("Store")
# #     if store_tool:
# #         result = store_tool.function(thread_id=thread_id, sender=sender, content=content)
# #         tool_call_log = {
# #             "Tool_call_source": agent.agent_name,
# #             "Tool_call_Destination": store_tool.name,
# #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
# #             "Tool_call_Response": result
# #         }
# #     else:
# #         # Fall back to direct call if not found; update destination to "Store"
# #         result = EphemeralMemory.store_message(thread_id=thread_id, sender=sender, content=content)
# #         tool_call_log = {
# #             "Tool_call_source": agent.agent_name,
# #             "Tool_call_Destination": "Store",
# #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
# #             "Tool_call_Response": result
# #         }
# #     return tool_call_log


# # def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
# #     """Write the log file for a single user query and return the filepath."""
# #     log_dir = os.path.join("moya", "explainability", "utterance_history")
# #     os.makedirs(log_dir, exist_ok=True)
# #     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# #     filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{timestamp}_quick_start_multiagent_logged.json"
# #     filepath = os.path.join(log_dir, filename)
# #     with open(filepath, "w") as f:
# #         json.dump(log_data, f, indent=4)
# #     print(f"\nLog written to: {filepath}")
# #     return filepath


# # def main():
# #     orchestrator = setup_orchestrator()
# #     thread_id = "single_query_thread"

# #     print("Starting multi-agent chat logging (type 'exit' to quit)")
# #     print("Enter your query and see the logging flow (User → Orchestrator → Agent → Tools → User).")
# #     print("-" * 50)

# #     while True:
# #         user_message = input("\nYou: ").strip()
# #         if user_message.lower() == 'exit':
# #             print("\nGoodbye!")
# #             break

# #         # Generate a unique ID for this log
# #         unique_msg_id = uuid.uuid4().hex
# #         user_timestamp = datetime.datetime.now().isoformat()

# #         # Log Message1: User -> Orchestrator
# #         message_log = {
# #             "Message1": {
# #                 "Message Source": "User",
# #                 "Message Destination": "Orchestrator",
# #                 "Message Content": user_message,
# #                 "Tools_Called_by_Message_Source": {}
# #             }
# #         }

# #         def stream_callback(chunk):
# #             print(chunk, end="", flush=True)

# #         # For simplicity, we do not include conversation history.
# #         # The orchestrator selects an agent. Here we use the first available agent.
# #         agents = orchestrator.agent_registry.list_agents()
# #         if not agents:
# #             print("\nNo agents available!")
# #             continue
# #         # Initially select the first agent (this may be overridden)
# #         selected_agent = orchestrator.agent_registry.get_agent(agents[0].name)

# #         # Note: enriched_input here is simply the raw user query since we are not building on conversation history.
# #         response = orchestrator.orchestrate(
# #             thread_id=thread_id,
# #             user_message=user_message,
# #             stream_callback=stream_callback
# #         )
# #         print()  # newline after response

# #         # --- New code to detect and adjust agent selection ---
# #         # If the response begins with an agent tag in the format "[agent_name] ..."
# #         pattern = r'^\[(.*?)\]\s*(.*)'
# #         match = re.match(pattern, response)
# #         if match:
# #             used_agent_name = match.group(1)
# #             cleaned_response = match.group(2)
# #             # Check if any agent in the registry matches the tag.
# #             if any(agent.name == used_agent_name for agent in agents):
# #                 selected_agent = used_agent_name
# #             response = cleaned_response  # update response without the tag
# #         # --- End new code ---

# #         # Log Message2: Orchestrator -> Selected Agent
# #         message_log["Message2"] = {
# #             "Message Source": "Orchestrator",
# #             "Message Destination": selected_agent,
# #             "Message Content": f"Delegated to agent {selected_agent}",
# #             "Tools_Called_by_Message_Source": {}
# #         }

# #         # Call the orchestrator (which may call tools within the agent)
# #         print("\nAssistant: ", end="", flush=True)

        
# #         # # Note: enriched_input here is simply the raw user query since we are not building on conversation history.
# #         # response = orchestrator.orchestrate(
# #         #     thread_id=thread_id,
# #         #     user_message=user_message,
# #         #     stream_callback=stream_callback
# #         # )
# #         # print()  # newline after response


# #         final_agent_tool_call = {
# #             "Tool_call_source": selected_agent,
# #             "Tool_call_Destination": "Store",
# #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: assistant, content: {response}",
# #             "Tool_call_Response": "Success"
# #         }

# #         tool_calls_log = {}
# #         idx = 1
# #         if hasattr(selected_agent, "tool_call_logs"):
# #             for call in selected_agent.tool_call_logs:
# #                 tool_calls_log[f"ToolCall{idx}"] = call
# #                 idx += 1
# #             # Append the final store tool call at the end
# #             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
# #             # Clear the agent's tool logs after capturing
# #             selected_agent.tool_call_logs = []
# #         else:
# #             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call

# #         # Log Message3: Agent (and any tool calls) -> User
# #         message_log["Message3"] = {
# #             "Message Source": selected_agent,
# #             "Message Destination": "User",
# #             "Message Content": response,
# #             "Tools_Called_by_Message_Source": tool_calls_log
# #         }

# #         # Build the complete log data structure for this single query
# #         log_data = {
# #             "UserMessage": user_message,
# #             "UserTimestamp": user_timestamp,
# #             "orchestrator": {
# #                 "type": "MultiAgentOrchestrator",
# #                 "default_agent_name": orchestrator.classifier.default_agent
# #             },
# #             "AgentRegistry": {},
# #             "Message_Log": message_log
# #         }

# #         # Populate AgentRegistry details for each registered agent.
# #         for agent_info in orchestrator.agent_registry.list_agents():
# #             ag = orchestrator.agent_registry.get_agent(agent_info.name)
# #             tools = {}
# #             if ag.tool_registry:
# #                 for tool in ag.tool_registry.get_tools():
# #                     tools[tool.name] = {
# #                         "tool_name": tool.name,
# #                         "tool_description": tool.description
# #                     }
# #             log_data["AgentRegistry"][agent_info.name] = {
# #                 "agent_name": ag.agent_name,
# #                 "description": ag.description,
# #                 "model_name": ag.llm_config.get("model_name", ""),
# #                 "agent_type": ag.agent_type,
# #                 "system_Prompt": ag.system_prompt,
# #                 "tool_registry": tools
# #             }

# #         # Write the log for this single query.
# #         log_filepath = write_utterance_flow_log(log_data, unique_msg_id)

# #         # Optionally: Call the visualizer to generate DOT and PNG outputs.
# #         dot_filepath = log_filepath.replace(".json", ".dot")
# #         subprocess.run([
# #             "python",
# #             "/workspaces/moya/moya/explainability/user_utterance_visualizer/single_agent_openai_visualizer.py",
# #             log_filepath, dot_filepath
# #         ])
# #         print(f"\nVisualizer dot file generated at: {dot_filepath}")
# #         png_filepath = dot_filepath.replace(".dot", ".png")
# #         subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
# #         print(f"Graph image generated at: {png_filepath}")


# # if __name__ == "__main__":
# #     main()


# # # import os
# # # import json
# # # import datetime
# # # import uuid
# # # import subprocess

# # # from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# # # from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
# # # from moya.classifiers.llm_classifier import LLMClassifier
# # # from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
# # # from moya.registry.agent_registry import AgentRegistry
# # # from moya.tools.ephemeral_memory import EphemeralMemory
# # # from moya.tools.tool_registry import ToolRegistry

# # # # Set your user metadata (could be obtained via authentication in a real system)
# # # USER_NAME = "Alice"
# # # USER_ID = "1234"


# # # def setup_memory_components():
# # #     """Set up memory components for the agents."""
# # #     tool_registry = ToolRegistry()
# # #     EphemeralMemory.configure_memory_tools(tool_registry)
# # #     return tool_registry


# # # def create_english_agent(tool_registry):
# # #     """Create an English-speaking OpenAI agent."""
# # #     agent_config = OpenAIAgentConfig(
# # #         agent_name="english_agent",
# # #         agent_type="ChatAgent",
# # #         description="English language specialist",
# # #         system_prompt=(
# # #             "You are a helpful AI assistant that always responds in English. "
# # #             "You should be polite, informative, and maintain a professional tone."
# # #         ),
# # #         llm_config={'temperature': 0.7},
# # #         model_name="gpt-4o",
# # #         api_key=os.getenv("OPENAI_API_KEY")
# # #     )
# # #     return OpenAIAgent(config=agent_config)


# # # def create_spanish_agent(tool_registry) -> OpenAIAgent:
# # #     """Create a Spanish-speaking OpenAI agent."""
# # #     agent_config = OpenAIAgentConfig(
# # #         agent_name="spanish_agent",
# # #         agent_type="ChatAgent",
# # #         description="Spanish language specialist that provides responses only in Spanish",
# # #         system_prompt=(
# # #             "Eres un asistente de IA servicial que siempre responde en español. "
# # #             "Debes ser educado, informativo y mantener un tono profesional. "
# # #             "Si te piden hablar en otro idioma, declina cortésmente y continúa en español."
# # #         ),
# # #         llm_config={'temperature': 0.7},
# # #         model_name="gpt-4o",
# # #         api_key=os.getenv("OPENAI_API_KEY")
# # #     )
# # #     return OpenAIAgent(config=agent_config)


# # # def create_remote_agent(tool_registry) -> RemoteAgent:
# # #     """Create a remote agent for joke-related queries."""
# # #     return RemoteAgent(
# # #         config=RemoteAgentConfig(
# # #             agent_name="joke_agent",
# # #             agent_type="RemoteAgent",
# # #             description="Remote agent specialized in telling jokes",
# # #             base_url="http://localhost:8000",
# # #             verify_ssl=True,
# # #             auth_token="your-secret-token-here",
# # #             tool_registry=tool_registry,
# # #         )
# # #     )


# # # def create_classifier_agent() -> OpenAIAgent:
# # #     """Create a classifier agent for language and task detection."""
# # #     system_prompt = (
# # #         "You are a classifier. Your job is to determine the best agent based on the user's message:\n"
# # #         "1. If the message requests or implies a need for a joke, return 'joke_agent'\n"
# # #         "2. If the message is in English or requests English response, return 'english_agent'\n"
# # #         "3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'\n"
# # #         "4. For any other language requests, return null\n\n"
# # #         "Analyze both the language and intent of the message and return only the agent name as specified."
# # #     )

# # #     agent_config = OpenAIAgentConfig(
# # #         agent_name="classifier",
# # #         agent_type="AgentClassifier",
# # #         description="Language and task classifier for routing messages",
# # #         tool_registry=None,
# # #         model_name="gpt-4o",
# # #         system_prompt=system_prompt,
# # #         api_key=os.getenv("OPENAI_API_KEY")
# # #     )
# # #     return OpenAIAgent(config=agent_config)


# # # def setup_orchestrator():
# # #     """Set up the multi-agent orchestrator with all components."""
# # #     tool_registry = setup_memory_components()

# # #     # Create agents
# # #     english_agent = create_english_agent(tool_registry)
# # #     spanish_agent = create_spanish_agent(tool_registry)
# # #     joke_agent = create_remote_agent(tool_registry)
# # #     classifier_agent = create_classifier_agent()

# # #     # Set up agent registry
# # #     registry = AgentRegistry()
# # #     registry.register_agent(english_agent)
# # #     registry.register_agent(spanish_agent)
# # #     registry.register_agent(joke_agent)

# # #     # Create and configure the classifier
# # #     classifier = LLMClassifier(classifier_agent, default_agent="english_agent")

# # #     # Create the orchestrator
# # #     orchestrator = MultiAgentOrchestrator(
# # #         agent_registry=registry,
# # #         classifier=classifier,
# # #         default_agent_name=None
# # #     )

# # #     return orchestrator

# # # def call_store_tool(thread_id, sender, content, agent):
# # #     """
# # #     Call the Store tool via the tool registry rather than calling EphemeralMemory.store_message directly.
# # #     This function also returns a log entry with the correct tool name.
# # #     """
# # #     store_tool = None
# # #     if agent.tool_registry:
# # #         # Try to retrieve the tool named "Store"
# # #         store_tool = agent.tool_registry.get_tool("Store")
# # #     if store_tool:
# # #         result = store_tool.function(thread_id=thread_id, sender=sender, content=content)
# # #         tool_call_log = {
# # #             "Tool_call_source": agent.agent_name,
# # #             "Tool_call_Destination": store_tool.name,
# # #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
# # #             "Tool_call_Response": result
# # #         }
# # #     else:
# # #         # Fall back to direct call if not found; update destination to "Store"
# # #         result = EphemeralMemory.store_message(thread_id=thread_id, sender=sender, content=content)
# # #         tool_call_log = {
# # #             "Tool_call_source": agent.agent_name,
# # #             "Tool_call_Destination": "Store",
# # #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: {sender}, content: {content}",
# # #             "Tool_call_Response": result
# # #         }
# # #     return tool_call_log

# # # def write_utterance_flow_log(log_data: dict, unique_msg_id: str):
# # #     """Write the log file for a single user query and return the filepath."""
# # #     log_dir = os.path.join("moya", "explainability", "utterance_history")
# # #     os.makedirs(log_dir, exist_ok=True)
# # #     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# # #     filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{timestamp}_quick_start_multiagent_logged.json"
# # #     filepath = os.path.join(log_dir, filename)
# # #     with open(filepath, "w") as f:
# # #         json.dump(log_data, f, indent=4)
# # #     print(f"\nLog written to: {filepath}")
# # #     return filepath


# # # def main():
# # #     orchestrator = setup_orchestrator()
# # #     thread_id = "single_query_thread"

# # #     print("Starting multi-agent chat logging (type 'exit' to quit)")
# # #     print("Enter your query and see the logging flow (User → Orchestrator → Agent → Tools → User).")
# # #     print("-" * 50)

# # #     while True:
# # #         user_message = input("\nYou: ").strip()
# # #         if user_message.lower() == 'exit':
# # #             print("\nGoodbye!")
# # #             break

# # #         # Generate a unique ID for this log
# # #         unique_msg_id = uuid.uuid4().hex
# # #         user_timestamp = datetime.datetime.now().isoformat()

# # #         # Log Message1: User -> Orchestrator
# # #         message_log = {
# # #             "Message1": {
# # #                 "Message Source": "User",
# # #                 "Message Destination": "Orchestrator",
# # #                 "Message Content": user_message,
# # #                 "Tools_Called_by_Message_Source": {}
# # #             }
# # #         }

# # #         # For simplicity, we do not include conversation history.
# # #         # The orchestrator selects an agent. Here we use the first available agent.
# # #         agents = orchestrator.agent_registry.list_agents()
# # #         if not agents:
# # #             print("\nNo agents available!")
# # #             continue
# # #         selected_agent = orchestrator.agent_registry.get_agent(agents[0].name)

# # #         # Log Message2: Orchestrator -> Selected Agent
# # #         message_log["Message2"] = {
# # #             "Message Source": "Orchestrator",
# # #             "Message Destination": selected_agent.name,
# # #             "Message Content": f"Delegated to agent {selected_agent.name}",
# # #             "Tools_Called_by_Message_Source": {}
# # #         }

# # #         # Call the orchestrator (which may call tools within the agent)
# # #         print("\nAssistant: ", end="", flush=True)

# # #         def stream_callback(chunk):
# # #             print(chunk, end="", flush=True)

# # #         # Note: enriched_input here is simply the raw user query since we are not building on conversation history.
# # #         response = orchestrator.orchestrate(
# # #             thread_id=thread_id,
# # #             user_message=user_message,
# # #             stream_callback=stream_callback
# # #         )
# # #         print()  # newline after response

# # #         final_agent_tool_call = {
# # #             "Tool_call_source": selected_agent.name,
# # #             "Tool_call_Destination": "Store",
# # #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: assistant, content: {response}",
# # #             "Tool_call_Response": "Success"
# # #         }

# # #         # store_log = call_store_tool(thread_id, "assistant", response, selected_agent)
# # #         tool_calls_log = {}
# # #         idx = 1
# # #         # tool_calls_log[f"ToolCall{idx}"] = store_log
# # #         # idx += 1
# # #         if hasattr(selected_agent, "tool_call_logs"):
# # #             for call in selected_agent.tool_call_logs:
# # #                 tool_calls_log[f"ToolCall{idx}"] = call
# # #                 idx += 1
# # #             # Append the final store tool call at the end
# # #             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call
# # #             # Clear the agent's tool logs after capturing
# # #             selected_agent.tool_call_logs = []
# # #         else:
# # #             tool_calls_log[f"ToolCall{idx}"] = final_agent_tool_call

# # #         # Log Message3: Agent (and any tool calls) -> User
# # #         message_log["Message3"] = {
# # #             "Message Source": selected_agent.name,
# # #             "Message Destination": "User",
# # #             "Message Content": response,
# # #             "Tools_Called_by_Message_Source": tool_calls_log
# # #         }

# # #         # Build the complete log data structure for this single query
# # #         log_data = {
# # #             "UserMessage": user_message,
# # #             "UserTimestamp": user_timestamp,
# # #             "orchestrator": {
# # #                 "type": "MultiAgentOrchestrator",
# # #                 "default_agent_name": orchestrator.classifier.default_agent
# # #             },
# # #             "AgentRegistry": {},
# # #             "Message_Log": message_log
# # #         }

# # #         # Populate AgentRegistry details for each registered agent.
# # #         for agent_info in orchestrator.agent_registry.list_agents():
# # #             ag = orchestrator.agent_registry.get_agent(agent_info.name)
# # #             tools = {}
# # #             if ag.tool_registry:
# # #                 for tool in ag.tool_registry.get_tools():
# # #                     tools[tool.name] = {
# # #                         "tool_name": tool.name,
# # #                         "tool_description": tool.description
# # #                     }
# # #             log_data["AgentRegistry"][agent_info.name] = {
# # #                 "agent_name": ag.agent_name,
# # #                 "description": ag.description,
# # #                 "model_name": ag.llm_config.get("model_name", ""),
# # #                 "agent_type": ag.agent_type,
# # #                 "system_Prompt": ag.system_prompt,
# # #                 "tool_registry": tools
# # #             }

# # #         # Write the log for this single query.
# # #         log_filepath = write_utterance_flow_log(log_data, unique_msg_id)

# # #         # Optionally: Call the visualizer to generate DOT and PNG outputs.
# # #         dot_filepath = log_filepath.replace(".json", ".dot")
# # #         subprocess.run([
# # #             "python",
# # #             "/workspaces/moya/moya/explainability/user_utterance_visualizer/single_agent_openai_visualizer.py",
# # #             log_filepath, dot_filepath
# # #         ])
# # #         print(f"\nVisualizer dot file generated at: {dot_filepath}")
# # #         png_filepath = dot_filepath.replace(".dot", ".png")
# # #         subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
# # #         print(f"Graph image generated at: {png_filepath}")

# # # if __name__ == "__main__":
# # #     main()


# # # # import os
# # # # import json
# # # # import datetime
# # # # import uuid
# # # # import subprocess

# # # # # (Assume other functions like write_utterance_flow_log are defined as in quick_start_openai_logged.py)


# # # # import os
# # # # from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# # # # from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
# # # # from moya.classifiers.llm_classifier import LLMClassifier
# # # # from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
# # # # from moya.registry.agent_registry import AgentRegistry
# # # # from moya.tools.ephemeral_memory import EphemeralMemory
# # # # from moya.memory.in_memory_repository import InMemoryRepository
# # # # from moya.tools.tool_registry import ToolRegistry


# # # # def setup_memory_components():
# # # #     """Set up memory components for the agents."""
# # # #     tool_registry = ToolRegistry()
# # # #     EphemeralMemory.configure_memory_tools(tool_registry)
# # # #     return tool_registry


# # # # def create_english_agent(tool_registry):
# # # #     """Create an English-speaking OpenAI agent."""
# # # #     agent_config = OpenAIAgentConfig(
# # # #         agent_name="english_agent",
# # # #         agent_type="ChatAgent",
# # # #         description="English language specialist",
# # # #         system_prompt="""You are a helpful AI assistant that always responds in English.
# # # #         You should be polite, informative, and maintain a professional tone.""",
# # # #         llm_config={
# # # #             'temperature': 0.7,
# # # #         },
# # # #         model_name="gpt-4o",
# # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # #     )

# # # #     return OpenAIAgent(config=agent_config)


# # # # def create_spanish_agent(tool_registry) -> OpenAIAgent:
# # # #     """Create a Spanish-speaking OpenAI agent."""
# # # #     agent_config = OpenAIAgentConfig(
# # # #         agent_name="spanish_agent",
# # # #         agent_type="ChatAgent",
# # # #         description="Spanish language specialist that provides responses only in Spanish",
# # # #         system_prompt="""Eres un asistente de IA servicial que siempre responde en español.
# # # #         Debes ser educado, informativo y mantener un tono profesional.
# # # #         Si te piden hablar en otro idioma, declina cortésmente y continúa en español.""",
# # # #         llm_config={
# # # #             'temperature': 0.7
# # # #         },
# # # #         model_name="gpt-4o",
# # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # #     )

# # # #     return OpenAIAgent(config=agent_config)



# # # # def create_remote_agent(tool_registry) -> RemoteAgent:
# # # #     """Create a remote agent for joke-related queries."""
# # # #     return RemoteAgent(
# # # #         config =RemoteAgentConfig(
# # # #             agent_name="joke_agent",
# # # #             agent_type="RemoteAgent",
# # # #             description="Remote agent specialized in telling jokes",
# # # #             base_url="http://localhost:8000",
# # # #             verify_ssl=True,
# # # #             auth_token="your-secret-token-here",
# # # #             tool_registry=tool_registry,
# # # #         )
# # # #     )



# # # # def create_classifier_agent() -> OpenAIAgent:
# # # #     """Create a classifier agent for language and task detection."""

# # # #     system_prompt="""You are a classifier. Your job is to determine the best agent based on the user's message:
# # # #         1. If the message requests or implies a need for a joke, return 'joke_agent'
# # # #         2. If the message is in English or requests English response, return 'english_agent'
# # # #         3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'
# # # #         4. For any other language requests, return null
        
# # # #         Analyze both the language and intent of the message.
# # # #         Return only the agent name as specified above."""

# # # #     agent_config = OpenAIAgentConfig(
# # # #         agent_name="classifier",
# # # #         agent_type="AgentClassifier",
# # # #         description="Language and task classifier for routing messages",
# # # #         tool_registry=None,
# # # #         model_name="gpt-4o",    
# # # #         system_prompt=system_prompt,
# # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # #     )

# # # #     return OpenAIAgent(config=agent_config)



# # # # def setup_orchestrator():
# # # #     """Set up the multi-agent orchestrator with all components."""
# # # #     # Set up shared components
# # # #     tool_registry = setup_memory_components()

# # # #     # Create agents
# # # #     english_agent = create_english_agent(tool_registry)
# # # #     spanish_agent = create_spanish_agent(tool_registry)
# # # #     joke_agent = create_remote_agent(tool_registry)
# # # #     classifier_agent = create_classifier_agent()

# # # #     # Set up agent registry
# # # #     registry = AgentRegistry()
# # # #     registry.register_agent(english_agent)
# # # #     registry.register_agent(spanish_agent)
# # # #     registry.register_agent(joke_agent)

# # # #     # Create and configure the classifier
# # # #     classifier = LLMClassifier(classifier_agent, default_agent="english_agent")

# # # #     # Create the orchestrator
# # # #     orchestrator = MultiAgentOrchestrator(
# # # #         agent_registry=registry,
# # # #         classifier=classifier,
# # # #         default_agent_name=None
# # # #     )

# # # #     return orchestrator


# # # # def format_conversation_context(messages):
# # # #     """Format conversation history for context."""
# # # #     context = "\nPrevious conversation:\n"
# # # #     for msg in messages:
# # # #         sender = "User" if msg.sender == "user" else "Assistant"
# # # #         context += f"{sender}: {msg.content}\n"
# # # #     return context


# # # # def main():
# # # #     # Set up the orchestrator and all components
# # # #     orchestrator = setup_orchestrator()
# # # #     thread_id = "test_conversation"
# # # #     conversation_log = []  # Accumulate iteration logs
    
# # # #     print("Starting multi-agent chat (type 'exit' to quit)")
# # # #     print("You can chat in English or Spanish, or request responses in either language.")
# # # #     print("-" * 50)

# # # #     def stream_callback(chunk):
# # # #         print(chunk, end="", flush=True)

# # # #     # Optional: start the conversation log with an initial system message
# # # #     EphemeralMemory.store_message(thread_id=thread_id, sender="system", content=f"thread ID: {thread_id}")

# # # #     while True:
# # # #         user_message = input("\nYou: ").strip()
# # # #         if user_message.lower() == 'exit':
# # # #             print("\nGoodbye!")
# # # #             break

# # # #         agents = orchestrator.agent_registry.list_agents()
# # # #         if not agents:
# # # #             print("\nNo agents available!")
# # # #             continue

# # # #         # Choose a target agent – here we use the first as a simple mechanism.
# # # #         last_agent = orchestrator.agent_registry.get_agent(agents[0].name)

# # # #         # Store user message
# # # #         EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message)
# # # #         session_summary = EphemeralMemory.get_thread_summary(thread_id)
# # # #         enriched_input = f"{session_summary}\nCurrent user message: {user_message}"
        
# # # #         # Build the iteration log as a dictionary.
# # # #         iteration_log = {}
# # # #         # Message1: User -> Orchestrator
# # # #         iteration_log["Message1"] = {
# # # #             "Message Source": "User",
# # # #             "Message Destination": "Orchestrator",
# # # #             "Message Content": user_message,
# # # #             "Tools_Called_by_Message_Source": {}
# # # #         }
# # # #         # Message2: Orchestrator -> Agent
# # # #         iteration_log["Message2"] = {
# # # #             "Message Source": "Orchestrator",
# # # #             "Message Destination": last_agent.agent_name,
# # # #             "Message Content": f"Delegated to agent {last_agent.agent_name}",
# # # #             "Tools_Called_by_Message_Source": {}
# # # #         }

# # # #         # Get agent response
# # # #         print("\nAssistant: ", end="", flush=True)
# # # #         response = orchestrator.orchestrate(
# # # #             thread_id=thread_id,
# # # #             user_message=enriched_input,
# # # #             stream_callback=stream_callback
# # # #         )
# # # #         print()  # New line after response
        
# # # #         # Store agent response
# # # #         EphemeralMemory.store_message(thread_id=thread_id, sender="system", content=response)
        
# # # #         # For Message3, log the agent’s response.
# # # #         # In this multiagent setting you may also capture additional tool call logs.
# # # #         # For example, the orchestrator could log its own tool call for message storing
# # # #         orchestrator_tool_call = {
# # # #             "Tool_call_source": "Orchestrator",
# # # #             "Tool_call_Destination": "EphemeralMemory.store_message",
# # # #             "Tool_call_Arguments": f"thread_id: {thread_id}, sender: system, content: {response}",
# # # #             "Tool_call_Response": "Success"
# # # #         }
# # # #         # If the selected agent (last_agent) has logged tool calls from its execution,
# # # #         # include them as well (assuming agent.tool_call_logs exists).
# # # #         tool_calls_log = {}
# # # #         idx = 1
# # # #         tool_calls_log[f"ToolCall{idx}"] = orchestrator_tool_call
# # # #         idx += 1
# # # #         if hasattr(last_agent, "tool_call_logs"):
# # # #             for call in last_agent.tool_call_logs:
# # # #                 tool_calls_log[f"ToolCall{idx}"] = call
# # # #                 idx += 1
# # # #             # Clear the agent's logs after capturing them.
# # # #             last_agent.tool_call_logs = []
        
# # # #         iteration_log["Message3"] = {
# # # #             "Message Source": last_agent.agent_name,
# # # #             "Message Destination": "User",
# # # #             "Message Content": response,
# # # #             "Tools_Called_by_Message_Source": tool_calls_log
# # # #         }
        
# # # #         # Append this iteration's log to the conversation array.
# # # #         conversation_log.append(iteration_log)

# # # #     # At conversation end, prepare final log data.
# # # #     unique_msg_id = uuid.uuid4().hex
# # # #     final_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# # # #     user_timestamp = datetime.datetime.now().isoformat()
# # # #     log_data = {
# # # #         "UserFinalMessage": user_message,
# # # #         "UserTimestamp": user_timestamp,
# # # #         "orchestrator": {
# # # #             "type": "MultiAgentOrchestrator",
# # # #             "default_agent_name": orchestrator.classifier.default_agent
# # # #         },
# # # #         "AgentRegistry": {},
# # # #         "Conversation_Log": conversation_log  # all iterations are stored here.
# # # #     }
    
# # # #     # Populate AgentRegistry for all agents.
# # # #     for agent_info in orchestrator.agent_registry.list_agents():
# # # #         ag = orchestrator.agent_registry.get_agent(agent_info.name)
# # # #         tools = {}
# # # #         if ag.tool_registry:
# # # #             for tool in ag.tool_registry.get_tools():
# # # #                 tools[tool.name] = {
# # # #                     "tool_name": tool.name,
# # # #                     "tool_description": tool.description
# # # #                 }
# # # #         log_data["AgentRegistry"][agent_info.name] = {
# # # #             "agent_name": ag.agent_name,
# # # #             "description": ag.description,
# # # #             "model_name": ag.llm_config.get("model_name", ""),
# # # #             "agent_type": ag.agent_type,
# # # #             "system_Prompt": ag.system_prompt,
# # # #             "tool_registry": tools
# # # #         }
    
# # # #     # Write final log
# # # #     log_filename = f"{unique_msg_id}_User_Utterance_Flow_Log_{USER_NAME}_{USER_ID}_{final_timestamp}_quick_start_multiagent_logged.json"
# # # #     log_filepath = os.path.join("moya", "explainability", "utterance_history", log_filename)
# # # #     with open(log_filepath, "w") as f:
# # # #         json.dump(log_data, f, indent=4)
# # # #     print(f"\nLog written to: {log_filepath}")
    
# # # #     # Call the visualizer
# # # #     dot_filepath = log_filepath.replace(".json", ".dot")
# # # #     subprocess.run([
# # # #         "python", 
# # # #         "/workspaces/moya/moya/explainability/user_utterance_visualizer/single_agent_openai_visualizer.py", 
# # # #         log_filepath, dot_filepath
# # # #     ])
# # # #     print(f"\nVisualizer dot file generated at: {dot_filepath}")
    
# # # #     # Optionally, render PNG via Graphviz
# # # #     png_filepath = dot_filepath.replace(".dot", ".png")
# # # #     subprocess.run(["dot", "-Tpng", dot_filepath, "-o", png_filepath])
# # # #     print(f"Graph image generated at: {png_filepath}")

# # # # if __name__ == "__main__":
# # # #     main()

# # # # # import os
# # # # # from moya.agents.openai_agent import OpenAIAgent, OpenAIAgentConfig
# # # # # from moya.agents.remote_agent import RemoteAgent, RemoteAgentConfig
# # # # # from moya.classifiers.llm_classifier import LLMClassifier
# # # # # from moya.orchestrators.multi_agent_orchestrator import MultiAgentOrchestrator
# # # # # from moya.registry.agent_registry import AgentRegistry
# # # # # from moya.tools.ephemeral_memory import EphemeralMemory
# # # # # from moya.memory.in_memory_repository import InMemoryRepository
# # # # # from moya.tools.tool_registry import ToolRegistry


# # # # # def setup_memory_components():
# # # # #     """Set up memory components for the agents."""
# # # # #     tool_registry = ToolRegistry()
# # # # #     EphemeralMemory.configure_memory_tools(tool_registry)
# # # # #     return tool_registry


# # # # # def create_english_agent(tool_registry):
# # # # #     """Create an English-speaking OpenAI agent."""
# # # # #     agent_config = OpenAIAgentConfig(
# # # # #         agent_name="english_agent",
# # # # #         agent_type="ChatAgent",
# # # # #         description="English language specialist",
# # # # #         system_prompt="""You are a helpful AI assistant that always responds in English.
# # # # #         You should be polite, informative, and maintain a professional tone.""",
# # # # #         llm_config={
# # # # #             'temperature': 0.7,
# # # # #         },
# # # # #         model_name="gpt-4o",
# # # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # # #     )

# # # # #     return OpenAIAgent(config=agent_config)


# # # # # def create_spanish_agent(tool_registry) -> OpenAIAgent:
# # # # #     """Create a Spanish-speaking OpenAI agent."""
# # # # #     agent_config = OpenAIAgentConfig(
# # # # #         agent_name="spanish_agent",
# # # # #         agent_type="ChatAgent",
# # # # #         description="Spanish language specialist that provides responses only in Spanish",
# # # # #         system_prompt="""Eres un asistente de IA servicial que siempre responde en español.
# # # # #         Debes ser educado, informativo y mantener un tono profesional.
# # # # #         Si te piden hablar en otro idioma, declina cortésmente y continúa en español.""",
# # # # #         llm_config={
# # # # #             'temperature': 0.7
# # # # #         },
# # # # #         model_name="gpt-4o",
# # # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # # #     )

# # # # #     return OpenAIAgent(config=agent_config)



# # # # # def create_remote_agent(tool_registry) -> RemoteAgent:
# # # # #     """Create a remote agent for joke-related queries."""
# # # # #     return RemoteAgent(
# # # # #         config =RemoteAgentConfig(
# # # # #             agent_name="joke_agent",
# # # # #             agent_type="RemoteAgent",
# # # # #             description="Remote agent specialized in telling jokes",
# # # # #             base_url="http://localhost:8001",
# # # # #             verify_ssl=True,
# # # # #             auth_token="your-secret-token-here",
# # # # #             tool_registry=tool_registry,
# # # # #         )
# # # # #     )



# # # # # def create_classifier_agent() -> OpenAIAgent:
# # # # #     """Create a classifier agent for language and task detection."""

# # # # #     system_prompt="""You are a classifier. Your job is to determine the best agent based on the user's message:
# # # # #         1. If the message requests or implies a need for a joke, return 'joke_agent'
# # # # #         2. If the message is in English or requests English response, return 'english_agent'
# # # # #         3. If the message is in Spanish or requests Spanish response, return 'spanish_agent'
# # # # #         4. For any other language requests, return null
        
# # # # #         Analyze both the language and intent of the message.
# # # # #         Return only the agent name as specified above.""",

# # # # #     agent_config = OpenAIAgentConfig(
# # # # #         agent_name="classifier",
# # # # #         agent_type="AgentClassifier",
# # # # #         description="Language and task classifier for routing messages",
# # # # #         tool_registry=None,
# # # # #         model_name="gpt-4o",    
# # # # #         system_prompt=system_prompt,
# # # # #         api_key=os.getenv("OPENAI_API_KEY")
# # # # #     )

# # # # #     return OpenAIAgent(config=agent_config)



# # # # # def setup_orchestrator():
# # # # #     """Set up the multi-agent orchestrator with all components."""
# # # # #     # Set up shared components
# # # # #     tool_registry = setup_memory_components()

# # # # #     # Create agents
# # # # #     english_agent = create_english_agent(tool_registry)
# # # # #     spanish_agent = create_spanish_agent(tool_registry)
# # # # #     joke_agent = create_remote_agent(tool_registry)
# # # # #     classifier_agent = create_classifier_agent()

# # # # #     # Set up agent registry
# # # # #     registry = AgentRegistry()
# # # # #     registry.register_agent(english_agent)
# # # # #     registry.register_agent(spanish_agent)
# # # # #     registry.register_agent(joke_agent)

# # # # #     # Create and configure the classifier
# # # # #     classifier = LLMClassifier(classifier_agent, default_agent="english_agent")

# # # # #     # Create the orchestrator
# # # # #     orchestrator = MultiAgentOrchestrator(
# # # # #         agent_registry=registry,
# # # # #         classifier=classifier,
# # # # #         default_agent_name=None
# # # # #     )

# # # # #     return orchestrator


# # # # # def format_conversation_context(messages):
# # # # #     """Format conversation history for context."""
# # # # #     context = "\nPrevious conversation:\n"
# # # # #     for msg in messages:
# # # # #         sender = "User" if msg.sender == "user" else "Assistant"
# # # # #         context += f"{sender}: {msg.content}\n"
# # # # #     return context


# # # # # def main():
# # # # #     # Set up the orchestrator and all components
# # # # #     orchestrator = setup_orchestrator()
# # # # #     thread_id = "test_conversation"

# # # # #     print("Starting multi-agent chat (type 'exit' to quit)")
# # # # #     print("You can chat in English or Spanish, or request responses in either language.")
# # # # #     print("-" * 50)

# # # # #     def stream_callback(chunk):
# # # # #         print(chunk, end="", flush=True)

# # # # #     EphemeralMemory.store_message(thread_id=thread_id, sender="system", content=f"thread ID: {thread_id}")

# # # # #     while True:
# # # # #         # Get user input
# # # # #         user_message = input("\nYou: ").strip()

# # # # #         # Check for exit condition
# # # # #         if user_message.lower() == 'exit':
# # # # #             print("\nGoodbye!")
# # # # #             break

# # # # #         # Get available agents
# # # # #         agents = orchestrator.agent_registry.list_agents()
# # # # #         if not agents:
# # # # #             print("\nNo agents available!")
# # # # #             continue

# # # # #         # Get the last used agent or default to the first one
# # # # #         last_agent = orchestrator.agent_registry.get_agent(agents[0].name)

# # # # #         # Store the user message first
# # # # #         EphemeralMemory.store_message(thread_id=thread_id, sender="user", content=user_message) 

# # # # #         session_summary = EphemeralMemory.get_thread_summary(thread_id)
# # # # #         enriched_input = f"{session_summary}\nCurrent user message: {user_message}"

# # # # #         # Print Assistant prompt and get response
# # # # #         print("\nAssistant: ", end="", flush=True)
# # # # #         response = orchestrator.orchestrate(
# # # # #             thread_id=thread_id,
# # # # #             user_message=enriched_input,
# # # # #             stream_callback=stream_callback
# # # # #         )
# # # # #         print()  # New line after response
# # # # #         EphemeralMemory.store_message(thread_id=thread_id, sender="system", content=response)


# # # # # if __name__ == "__main__":
# # # # #     main()
