"""
RemoteAgent for Moya.

An Agent that communicates with a remote API endpoint to generate responses.
It also logs and returns any tool calls returned by the remote endpoint.
"""

import requests
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Iterator
from moya.agents.base_agent import Agent, AgentConfig


@dataclass
class RemoteAgentConfig(AgentConfig):
    """Configuration for RemoteAgent, separate from AgentConfig to avoid inheritance issues"""
    base_url: str = None
    verify_ssl: bool = True
    auth_token: Optional[str] = None


class RemoteAgent(Agent):
    """
    An agent that forwards requests to a remote API endpoint.
    This implementation also logs and returns any tool calls.
    """

    def __init__(
        self,
        config: RemoteAgentConfig
    ):
        """
        Initialize a RemoteAgent.
        """
        super().__init__(config=config)

        if not config.base_url:
            raise ValueError("RemoteAgent base URL is required.")
                   
        self.base_url = config.base_url.rstrip('/')
        self.system_prompt = config.system_prompt
        self.session = requests.Session()
        
        # Configure authentication if provided
        if config.auth_token:
            self.session.headers.update({
                "Authorization": f"Bearer {config.auth_token}"
            })
        
        # Configure SSL verification
        self.session.verify = config.verify_ssl
        
        # Initialize an internal list for logging tool calls
        self.tool_call_logs = []

    def setup(self) -> None:
        """
        Set up the remote agent - test connection and configure session.
        """
        try:
            health_url = f"{self.base_url}/health"
            response = self.session.get(health_url)
            response.raise_for_status()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to remote agent at {self.base_url}: {str(e)}")

    def handle_message(self, message: str, **kwargs) -> str:
        """
        Send message to remote endpoint and get response.
        
        :param message: The message to process
        :param kwargs: Additional parameters to pass to the remote API (e.g., thread_id)
        :return: The plain text response from the remote agent
        """
        try:
            endpoint = f"{self.base_url}/chat"
            data = {
                "message": message,
                "thread_id": kwargs.get("thread_id"),
                **kwargs
            }
            
            response = self.session.post(endpoint, json=data)
            response.raise_for_status()
            json_response = response.json()
            res_text = json_response.get("response", "")
            
            # Log any tool calls returned from the remote endpoint.
            tool_calls = json_response.get("tool_calls", [])
            if tool_calls:
                self.tool_call_logs.extend(tool_calls)
            
            return res_text
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return "[RemoteAgent error: Authentication failed]"
            return f"[RemoteAgent error: {str(e)}]"
        except Exception as e:
            return f"[RemoteAgent error: {str(e)}]"

    def handle_message_stream(self, message: str, **kwargs) -> Iterator[str]:
        """
        Send message to remote endpoint and stream the response.
        Also logs any tool call segments if they are part of the streamed data.
        """
        try:
            endpoint = f"{self.base_url}/chat/stream"
            data = {
                "message": message,
                "thread_id": kwargs.get("thread_id"),
                **kwargs
            }
            
            with self.session.post(
                endpoint,
                json=data,
                stream=True,
                headers={"Accept": "text/event-stream"}
            ) as response:
                response.raise_for_status()
                current_text = ""
                # Reset any prior tool calls for this streaming session.
                self.tool_call_logs = []
                
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.startswith("data:"):
                        content = line[5:].strip()
                        if content and content != "done":
                            # Here, we assume that if the streamed data contains a JSON snippet
                            # with a "tool_calls" field, we process and log them.
                            try:
                                data_chunk = json.loads(content)
                                # If there's a tool call field, log it.
                                if "tool_calls" in data_chunk:
                                    self.tool_call_logs.extend(data_chunk["tool_calls"])
                                else:
                                    current_text += data_chunk.get("content", "")
                            except json.JSONDecodeError:
                                # Fallback to plain text accumulation
                                current_text += content
                            
                            yield current_text + " "
                            current_text = ""
                
                if current_text.strip():
                    yield current_text
                            
        except Exception as e:
            error_message = f"[RemoteAgent error: {str(e)}]"
            print(error_message)
            yield error_message

    def handle_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """
        Execute the tool specified in the tool call.
        Similar to the OpenAIAgent, this method looks up the tool in the registry,
        calls it with the provided arguments, logs the call, and returns the result.
        
        Args:
            tool_call (dict): Contains tool call information.
        
        Returns:
            str: The output from executing the tool.
        """
        function_data = tool_call.get("function", {})
        name = function_data.get("name")
        
        # Parse arguments if provided; they are passed as a JSON string by the API
        import json
        try:
            args = json.loads(function_data.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
            
        tool = self.tool_registry.get_tool(name) if self.tool_registry else None

        # Prepare a log entry for this tool call
        call_info = {
            "Tool_call_source": self.agent_name,
            "Tool_call_Destination": name,
            "Tool_call_Arguments": json.dumps(args),
            "Tool_call_Response": ""
        }

        if tool:
            result = tool.function(**args)
            call_info["Tool_call_Response"] = result
        else:
            result = f"[Tool '{name}' not found]"
            call_info["Tool_call_Response"] = result
        
        self.tool_call_logs.append(call_info)
        
        return result

    def __del__(self):
        """Cleanup the session when the agent is destroyed."""
        if hasattr(self, 'session'):
            self.session.close()

# """
# RemoteAgent for Moya.

# An Agent that communicates with a remote API endpoint to generate responses.
# """

# import requests
# from dataclasses import dataclass, field
# from typing import Any, Dict, Optional, Iterator
# from moya.agents.base_agent import Agent, AgentConfig


# @dataclass
# class RemoteAgentConfig(AgentConfig):
#     """Configuration for RemoteAgent, separate from AgentConfig to avoid inheritance issues"""
#     base_url: str = None
#     verify_ssl: bool = True
#     auth_token: Optional[str] = None


# class RemoteAgent(Agent):
#     """
#     An agent that forwards requests to a remote API endpoint.
#     """

#     def __init__(
#         self,
#         config=RemoteAgentConfig
#     ):
#         """
#         Initialize a RemoteAgent.
        
#         :param agent_name: Unique name for the agent
#         :param description: Description of the agent's capabilities
#         :param config: Optional configuration dictionary
#         :param tool_registry: Optional ToolRegistry for tool support
#         :param agent_config: Optional configuration for the RemoteAgent
#         """
#         super().__init__(config=config)

#         if not config.base_url:
#             raise ValueError("RemoteAgent base URL is required.")
                   
#         self.base_url = config.base_url.rstrip('/')
#         self.system_prompt = config.system_prompt
#         self.session = requests.Session()
        
#         # Configure authentication if provided
#         if config.auth_token:
#             self.session.headers.update({
#                 "Authorization": f"Bearer {config.auth_token}"
#             })
        
#         # Configure SSL verification
#         self.session.verify = config.verify_ssl

#     def setup(self) -> None:
#         """
#         Set up the remote agent - test connection and configure session.
#         """
#         try:
#             health_url = f"{self.base_url}/health"
#             response = self.session.get(health_url)
#             response.raise_for_status()
#         except Exception as e:
#             raise ConnectionError(f"Failed to connect to remote agent at {self.base_url}: {str(e)}")

#     def handle_message(self, message: str, **kwargs) -> str:
#         """
#         Send message to remote endpoint and get response.
        
#         :param message: The message to process
#         :param kwargs: Additional parameters to pass to the remote API
#         :return: Response from the remote agent
#         """
#         try:
#             endpoint = f"{self.base_url}/chat"
#             data = {
#                 "message": message,
#                 "thread_id": kwargs.get("thread_id"),
#                 **kwargs
#             }
            
#             response = self.session.post(endpoint, json=data)
#             response.raise_for_status()
#             return response.json()["response"]
            
#         except requests.exceptions.HTTPError as e:
#             if e.response.status_code == 401:
#                 return "[RemoteAgent error: Authentication failed]"
#             return f"[RemoteAgent error: {str(e)}]"
#         except Exception as e:
#             return f"[RemoteAgent error: {str(e)}]"

#     def handle_message_stream(self, message: str, **kwargs) -> Iterator[str]:
#         """
#         Send message to remote endpoint and stream the response.
#         """
#         try:
#             endpoint = f"{self.base_url}/chat/stream"
#             data = {
#                 "message": message,
#                 "thread_id": kwargs.get("thread_id"),
#                 **kwargs
#             }
            
#             with self.session.post(
#                 endpoint,
#                 json=data,
#                 stream=True,
#                 headers={"Accept": "text/event-stream"}
#             ) as response:
#                 response.raise_for_status()
#                 current_text = ""
                
#                 for line in response.iter_lines(decode_unicode=True):
#                     if line and line.startswith("data:"):
#                         content = line[5:].strip()
#                         if content and content != "done":
#                             # Clean up content
#                             clean_content = (
#                                 content
#                                 .encode('utf-8')
#                                 .decode('utf-8')
#                                 .replace('\u00A0', ' ')
#                             )
                            
#                             # Add to current text
#                             current_text += clean_content
                            
#                             # Find word boundaries
#                             words = []
#                             remaining = ""
                            
#                             # Split into words while preserving punctuation
#                             for word in current_text.split(' '):
#                                 if word:
#                                     if any(c.isalnum() for c in word):
#                                         words.append(word)
#                                     else:
#                                         # Handle punctuation
#                                         if words:
#                                             last_word = words[-1]
#                                             words[-1] = last_word + word
#                                         else:
#                                             words.append(word)
                            
#                             # If we have complete words, yield them
#                             if words:
#                                 text_to_yield = ' '.join(words)
#                                 yield text_to_yield + ' '
#                                 current_text = ""
                
#                 # Yield any remaining text
#                 if current_text.strip():
#                     yield current_text
                            
#         except Exception as e:
#             error_message = f"[RemoteAgent error: {str(e)}]"
#             print(error_message)
#             yield error_message

#     def __del__(self):
#         """Cleanup the session when the agent is destroyed."""
#         if hasattr(self, 'session'):
#             self.session.close()
