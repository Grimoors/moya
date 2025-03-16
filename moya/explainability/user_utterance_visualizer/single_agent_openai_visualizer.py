import json
import sys
import os

def escape_quotes(text):
    # Replace " with \"
    if text is None:
        return ""
    return text.replace('"', '\\"')

def main(log_filepath, dot_filepath):
    with open(log_filepath, 'r') as f:
        data = json.load(f)
    
    dot_lines = []
    dot_lines.append("digraph G {")
    dot_lines.append("    rankdir=LR;")
    
    # Create fixed nodes with tooltips. Escape quotes in tooltips.
    dot_lines.append('    User [shape=oval, style=filled, fillcolor=lavender, label="User", tooltip="User node"];')
    orchestrator_meta = data.get("orchestrator", {})
    orch_tooltip = escape_quotes(json.dumps(orchestrator_meta))
    dot_lines.append(f'    Orchestrator [shape=oval, style=filled, fillcolor=lightblue, label="Orchestrator", tooltip="{orch_tooltip}"];')
    
    # Create agent nodes with metadata as tooltip.
    agents = data.get("AgentRegistry", {})
    for ag_name, ag_data in agents.items():
        ag_tooltip = escape_quotes(json.dumps(ag_data))
        dot_lines.append(f'    {ag_name} [shape=circle, style=filled, fillcolor=lightgreen, label="{ag_name}", tooltip="{ag_tooltip}"];')
    
    # Collect unique tools from both the AgentRegistry and Message3 tool calls.
    tools_set = set()
    tools_metadata = {}
    for ag in agents.values():
        for tool, tool_meta in ag.get("tool_registry", {}).items():
            tools_set.add(tool)
            tools_metadata[tool] = tool_meta
    msg3 = data.get("Message_Log", {}).get("Message3", {})
    for tc in msg3.get("Tools_Called_by_Message_Source", {}).values():
        dest = tc.get("Tool_call_Destination")
        if dest:
            tools_set.add(dest)
    for tool in tools_set:
        meta = tools_metadata.get(tool, {})
        tool_tip = escape_quotes(json.dumps(meta))
        dot_lines.append(f'    "{tool}" [shape=box, style=filled, fillcolor=yellow, label="{tool}", tooltip="{tool_tip}"];')
    
    arrow_counter = 1
    # Message1: User -> Orchestrator
    msg1 = data.get("Message_Log", {}).get("Message1", {})
    tooltip1 = f'{msg1.get("Message Source", "User")} > {msg1.get("Message Destination", "Orchestrator")} , Message Passed: {msg1.get("Message Content", "")}'
    tooltip1 = escape_quotes(tooltip1)
    dot_lines.append(f'    User -> Orchestrator [label="{arrow_counter}", tooltip="{tooltip1}"];')
    arrow_counter += 1
    
    # Message2: Orchestrator -> default agent
    default_agent = data.get("orchestrator", {}).get("default_agent_name", "unknown_agent")
    msg2 = data.get("Message_Log", {}).get("Message2", {})
    tooltip2 = f'{msg2.get("Message Source", "Orchestrator")} > {msg2.get("Message Destination", default_agent)} , Message Passed: {msg2.get("Message Content", "")}'
    tooltip2 = escape_quotes(tooltip2)
    dot_lines.append(f'    Orchestrator -> {default_agent} [label="{arrow_counter}", tooltip="{tooltip2}"];')
    arrow_counter += 1

    # Draw tool call arrows from Message3.
    tools_log = msg3.get("Tools_Called_by_Message_Source", {})
    for _, tc in tools_log.items():
        source = default_agent  # Force tool call source as the default agent
        destination = tc.get("Tool_call_Destination")
        arguments = tc.get("Tool_call_Arguments", "")
        response = tc.get("Tool_call_Response", "")
        tooltip_tool_call = f'{source} > {destination} , Message Passed: {arguments}'
        tooltip_tool_call = escape_quotes(tooltip_tool_call)
        dot_lines.append(f'    {source} -> "{destination}" [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
        arrow_counter += 1
        tooltip_tool_call = f'{destination} > {source} , Message Passed: {response}'
        tooltip_tool_call = escape_quotes(tooltip_tool_call)
        dot_lines.append(f'    "{destination}" -> {source} [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
        arrow_counter += 1

    # Finally, Message3: default agent -> User
    msg3_tooltip = f'{msg3.get("Message Source", default_agent)} > {msg3.get("Message Destination", "User")} , Message Passed: {msg3.get("Message Content", "")}'
    msg3_tooltip = escape_quotes(msg3_tooltip)
    dot_lines.append(f'    {default_agent} -> User [label="{arrow_counter}", tooltip="{msg3_tooltip}"];')
    arrow_counter += 1

    dot_lines.append("}")
    
    with open(dot_filepath, "w") as f_out:
        f_out.write("\n".join(dot_lines))
    print(f"Dot file written to {dot_filepath}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python single_agent_openai_visualizer.py <log_json_file> <output_dot_file>")
        sys.exit(1)
    log_filepath = sys.argv[1]
    dot_filepath = sys.argv[2]
    if not os.path.exists(log_filepath):
        print(f"Log file {log_filepath} does not exist.")
        sys.exit(1)
    main(log_filepath, dot_filepath)

# import json
# import sys
# import os

# def main(log_filepath, dot_filepath):
#     with open(log_filepath, 'r') as f:
#         data = json.load(f)
    
#     dot_lines = []
#     dot_lines.append("digraph G {")
#     dot_lines.append("    rankdir=LR;")
    
#     # Create fixed nodes with metadata tooltips
#     # For User: we simply set tooltip as constant since no extra metadata is available.
#     dot_lines.append('    User [shape=oval, style=filled, fillcolor=purple, label="User", tooltip="User node"];')
    
#     # For Orchestrator, use its metadata
#     orchestrator_meta = data.get("orchestrator", {})
#     orch_tooltip = json.dumps(orchestrator_meta).replace('"', '\\"')
#     dot_lines.append(f'    Orchestrator [shape=oval, style=filled, fillcolor=blue, label="Orchestrator", tooltip="{orch_tooltip}"];')
    
#     # Create agent nodes from AgentRegistry with metadata as tooltip
#     agents = data.get("AgentRegistry", {})
#     for ag_name, ag_data in agents.items():
#         ag_tooltip = json.dumps(ag_data).replace('"', '\\"')
#         dot_lines.append(f'    {ag_name} [shape=circle, style=filled, fillcolor=green, label="{ag_name}", tooltip="{ag_tooltip}"];')
    
#     # Collect unique tools from both the AgentRegistry and Message3 tool calls.
#     tools_set = set()
#     tools_metadata = {}  # store metadata if available from agent registry
#     # From AgentRegistry
#     for ag in agents.values():
#         for tool, tool_meta in ag.get("tool_registry", {}).items():
#             tools_set.add(tool)
#             tools_metadata[tool] = tool_meta
#     # From Message3 tool calls
#     msg3 = data.get("Message_Log", {}).get("Message3", {})
#     for tc in msg3.get("Tools_Called_by_Message_Source", {}).values():
#         dest = tc.get("Tool_call_Destination")
#         if dest:
#             tools_set.add(dest)
#     for tool in tools_set:
#         meta = tools_metadata.get(tool, {})
#         tool_tip = json.dumps(meta).replace('"', '\\"')
#         dot_lines.append(f'    "{tool}" [shape=box, style=filled, fillcolor=yellow, label="{tool}", tooltip="{tool_tip}"];')
    
#     arrow_counter = 1
#     # Draw message edges with tooltips using data from Message_Log
#     # Message1: User -> Orchestrator
#     msg1 = data.get("Message_Log", {}).get("Message1", {})
#     tooltip1 = f"{msg1.get('Message Source', 'User')} > {msg1.get('Message Destination', 'Orchestrator')} , Message Passed: {msg1.get('Message Content', '')}"
#     dot_lines.append(f'    User -> Orchestrator [label="{arrow_counter}", tooltip="{tooltip1}"];')
#     arrow_counter += 1
#     # Message2: Orchestrator -> default agent
#     default_agent = data.get("orchestrator", {}).get("default_agent_name", "unknown_agent")
#     msg2 = data.get("Message_Log", {}).get("Message2", {})
#     tooltip2 = f"{msg2.get('Message Source', 'Orchestrator')} > {msg2.get('Message Destination', default_agent)} , Message Passed: {msg2.get('Message Content', '')}"
#     dot_lines.append(f'    Orchestrator -> {default_agent} [label="{arrow_counter}", tooltip="{tooltip2}"];')
#     arrow_counter += 1

#     # Now draw tool call arrows from Message3.
#     # For each tool call, we force the source to be the default agent.
#     tools_log = msg3.get("Tools_Called_by_Message_Source", {})
#     for _, tc in tools_log.items():
#         source = default_agent  # force tool call source as agent name
#         destination = tc.get("Tool_call_Destination")
#         arguments = tc.get("Tool_call_Arguments", "")
#         # Tooltip shows: source > destination , Message Passed: arguments
#         tooltip_tool_call = f"{source} > {destination} , Message Passed: {arguments}"
#         # Arrow: agent -> tool (call initiation)
#         dot_lines.append(f'    {source} -> "{destination}" [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
#         arrow_counter += 1
#         # Arrow: tool -> agent (tool response). Use same tooltip.
#         dot_lines.append(f'    "{destination}" -> {source} [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
#         arrow_counter += 1

#     # Finally, draw Message3: default agent -> User
#     msg3_tooltip = f"{msg3.get('Message Source', default_agent)} > {msg3.get('Message Destination', 'User')} , Message Passed: {msg3.get('Message Content', '')}"
#     dot_lines.append(f'    {default_agent} -> User [label="{arrow_counter}", tooltip="{msg3_tooltip}"];')
#     arrow_counter += 1

#     dot_lines.append("}")
    
#     # Write the dot file
#     with open(dot_filepath, "w") as f_out:
#         f_out.write("\n".join(dot_lines))
#     print(f"Dot file written to {dot_filepath}")

# if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print("Usage: python generate_dot.py <log_json_file> <output_dot_file>")
#         sys.exit(1)
#     log_filepath = sys.argv[1]
#     dot_filepath = sys.argv[2]
#     if not os.path.exists(log_filepath):
#         print(f"Log file {log_filepath} does not exist.")
#         sys.exit(1)
#     main(log_filepath, dot_filepath)

# # import json
# # import sys
# # import os

# # def main(log_filepath, dot_filepath):
# #     with open(log_filepath, 'r') as f:
# #         data = json.load(f)
    
# #     dot_lines = []
# #     dot_lines.append("digraph G {")
# #     dot_lines.append("    rankdir=LR;")
    
# #     # Create fixed nodes
# #     dot_lines.append('    User [shape=oval, style=filled, fillcolor=purple, label="User"];')
# #     dot_lines.append('    Orchestrator [shape=oval, style=filled, fillcolor=blue, label="Orchestrator"];')
    
# #     # Create agent nodes from AgentRegistry
# #     agents = data.get("AgentRegistry", {})
# #     for ag_name in agents.keys():
# #         dot_lines.append(f'    {ag_name} [shape=circle, style=filled, fillcolor=green, label="{ag_name}"];')
    
# #     # Collect unique tools from both the AgentRegistry and Message3 tool calls.
# #     tools_set = set()
# #     # From AgentRegistry
# #     for ag in agents.values():
# #         for tool in ag.get("tool_registry", {}).keys():
# #             tools_set.add(tool)
# #     # From Message3 tool calls
# #     msg3 = data.get("Message_Log", {}).get("Message3", {})
# #     for tc in msg3.get("Tools_Called_by_Message_Source", {}).values():
# #         dest = tc.get("Tool_call_Destination")
# #         if dest:
# #             tools_set.add(dest)
# #     for tool in tools_set:
# #         # Use quotes to preserve names with dots etc.
# #         dot_lines.append(f'    "{tool}" [shape=box, style=filled, fillcolor=yellow, label="{tool}"];')
    
# #     arrow_counter = 1
# #     # Draw message arrows:
# #     # Message1: User -> Orchestrator
# #     dot_lines.append(f'    User -> Orchestrator [label="{arrow_counter}"];')
# #     arrow_counter += 1
# #     # Message2: Orchestrator -> default agent (from orchestrator entry)
# #     default_agent = data.get("orchestrator", {}).get("default_agent_name", "unknown_agent")
# #     dot_lines.append(f'    Orchestrator -> {default_agent} [label="{arrow_counter}"];')
# #     arrow_counter += 1
    
    
# #     # Now draw tool call arrows from Message3.
# #     # For each tool call, draw two arrows: one from the source to the tool node and one back.
# #     tools_log = msg3.get("Tools_Called_by_Message_Source", {})
# #     for _, tc in tools_log.items():
# #         source = default_agent 
# #         destination = tc.get("Tool_call_Destination")
# #         if source and destination:
# #             # Arrow: source -> tool (call initiation)
# #             dot_lines.append(f'    {source} -> "{destination}" [label="{arrow_counter}"];')
# #             arrow_counter += 1
# #             # Arrow: tool -> source (tool response)
# #             dot_lines.append(f'    "{destination}" -> {source} [label="{arrow_counter}"];')
# #             arrow_counter += 1

# #     # Message3: default agent -> User
# #     dot_lines.append(f'    {default_agent} -> User [label="{arrow_counter}"];')
# #     arrow_counter += 1

# #     dot_lines.append("}")
    
# #     # Write the dot file
# #     with open(dot_filepath, "w") as f_out:
# #         f_out.write("\n".join(dot_lines))
# #     print(f"Dot file written to {dot_filepath}")

# # if __name__ == "__main__":
# #     if len(sys.argv) < 3:
# #         print("Usage: python generate_dot.py <log_json_file> <output_dot_file>")
# #         sys.exit(1)
# #     log_filepath = sys.argv[1]
# #     dot_filepath = sys.argv[2]
# #     # Ensure input file exists
# #     if not os.path.exists(log_filepath):
# #         print(f"Log file {log_filepath} does not exist.")
# #         sys.exit(1)
# #     main(log_filepath, dot_filepath)