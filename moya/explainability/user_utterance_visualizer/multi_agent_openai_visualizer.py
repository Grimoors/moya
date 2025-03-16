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
    
    # Fixed nodes for User and Orchestrator.
    dot_lines.append('    User [shape=oval, style=filled, fillcolor=lavender, label="User", tooltip="User node"];')
    orchestrator_meta = data.get("orchestrator", {})
    orch_tooltip = escape_quotes(json.dumps(orchestrator_meta))
    dot_lines.append(f'    Orchestrator [shape=oval, style=filled, fillcolor=skyblue, label="Orchestrator", tooltip="{orch_tooltip}"];')
    
    # Create agent nodes from AgentRegistry with metadata as tooltip.
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
    
    # Message2: Orchestrator -> Agent (read from log)
    msg2 = data.get("Message_Log", {}).get("Message2", {})
    dest_agent = msg2.get("Message Destination", "unknown_agent")
    tooltip2 = f'{msg2.get("Message Source", "Orchestrator")} > {dest_agent} , Message Passed: {msg2.get("Message Content", "")}'
    tooltip2 = escape_quotes(tooltip2)
    dot_lines.append(f'    Orchestrator -> {dest_agent} [label="{arrow_counter}", tooltip="{tooltip2}"];')
    arrow_counter += 1

    # Draw tool call arrows from Message3 using log fields.
    msg3 = data.get("Message_Log", {}).get("Message3", {})
    tools_log = msg3.get("Tools_Called_by_Message_Source", {})
    for _, tc in tools_log.items():
        source = tc.get("Tool_call_source", "unknown")
        destination = tc.get("Tool_call_Destination", "unknown")
        arguments = tc.get("Tool_call_Arguments", "")
        tooltip_tool_call = f'{source} > {destination} , Message Passed: {arguments}'
        tooltip_tool_call = escape_quotes(tooltip_tool_call)
        dot_lines.append(f'    {source} -> "{destination}" [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
        arrow_counter += 1
        response = tc.get("Tool_call_Response", "")
        tooltip_tool_call_resp = f'{destination} > {source} , Message Passed: {response}'
        tooltip_tool_call_resp = escape_quotes(tooltip_tool_call_resp)
        dot_lines.append(f'    "{destination}" -> {source} [label="{arrow_counter}", tooltip="{tooltip_tool_call_resp}"];')
        arrow_counter += 1

    # Message3: Agent -> User (read from log)
    msg3_source = msg3.get("Message Source", "unknown_agent")
    msg3_destination = msg3.get("Message Destination", "User")
    tooltip3 = f'{msg3_source} > {msg3_destination} , Message Passed: {msg3.get("Message Content", "")}'
    tooltip3 = escape_quotes(tooltip3)
    dot_lines.append(f'    {msg3_source} -> {msg3_destination} [label="{arrow_counter}", tooltip="{tooltip3}"];')
    arrow_counter += 1

    dot_lines.append("}")
    
    with open(dot_filepath, "w") as f_out:
        f_out.write("\n".join(dot_lines))
    print(f"Dot file written to {dot_filepath}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python multi_agent_visualizer.py <log_json_file> <output_dot_file>")
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

# def escape_quotes(text):
#     # Replace " with \"
#     if text is None:
#         return ""
#     return text.replace('"', '\\"')

# def main(log_filepath, dot_filepath):
#     with open(log_filepath, 'r') as f:
#         data = json.load(f)
    
#     dot_lines = []
#     dot_lines.append("digraph G {")
#     dot_lines.append("    rankdir=LR;")
    
#     # Fixed nodes for User and Orchestrator.
#     dot_lines.append('    User [shape=oval, style=filled, fillcolor=purple, label="User", tooltip="User node"];')
#     orchestrator_meta = data.get("orchestrator", {})
#     orch_tooltip = escape_quotes(json.dumps(orchestrator_meta))
#     dot_lines.append(f'    Orchestrator [shape=oval, style=filled, fillcolor=blue, label="Orchestrator", tooltip="{orch_tooltip}"];')
    
#     # Create agent nodes from AgentRegistry with metadata as tooltip.
#     agents = data.get("AgentRegistry", {})
#     for ag_name, ag_data in agents.items():
#         ag_tooltip = escape_quotes(json.dumps(ag_data))
#         dot_lines.append(f'    {ag_name} [shape=circle, style=filled, fillcolor=green, label="{ag_name}", tooltip="{ag_tooltip}"];')
    
#     # Collect unique tools from both the AgentRegistry and Message3 tool calls.
#     tools_set = set()
#     tools_metadata = {}
#     for ag in agents.values():
#         for tool, tool_meta in ag.get("tool_registry", {}).items():
#             tools_set.add(tool)
#             tools_metadata[tool] = tool_meta
#     msg3 = data.get("Message_Log", {}).get("Message3", {})
#     for tc in msg3.get("Tools_Called_by_Message_Source", {}).values():
#         dest = tc.get("Tool_call_Destination")
#         if dest:
#             tools_set.add(dest)
#     for tool in tools_set:
#         meta = tools_metadata.get(tool, {})
#         tool_tip = escape_quotes(json.dumps(meta))
#         dot_lines.append(f'    "{tool}" [shape=box, style=filled, fillcolor=yellow, label="{tool}", tooltip="{tool_tip}"];')
    
#     arrow_counter = 1
#     # Message1: User -> Orchestrator
#     msg1 = data.get("Message_Log", {}).get("Message1", {})
#     tooltip1 = f'{msg1.get("Message Source", "User")} > {msg1.get("Message Destination", "Orchestrator")} , Message Passed: {msg1.get("Message Content", "")}'
#     tooltip1 = escape_quotes(tooltip1)
#     dot_lines.append(f'    User -> Orchestrator [label="{arrow_counter}", tooltip="{tooltip1}"];')
#     arrow_counter += 1
    
#     # Message2: Orchestrator -> Agent (read from log)
#     msg2 = data.get("Message_Log", {}).get("Message2", {})
#     dest_agent = msg2.get("Message Destination", "unknown_agent")
#     tooltip2 = f'{msg2.get("Message Source", "Orchestrator")} > {dest_agent} , Message Passed: {msg2.get("Message Content", "")}'
#     tooltip2 = escape_quotes(tooltip2)
#     dot_lines.append(f'    Orchestrator -> {dest_agent} [label="{arrow_counter}", tooltip="{tooltip2}"];')
#     arrow_counter += 1

#     # Draw tool call arrows from Message3 using log fields.
#     msg3 = data.get("Message_Log", {}).get("Message3", {})
#     tools_log = msg3.get("Tools_Called_by_Message_Source", {})
#     for _, tc in tools_log.items():
#         source = tc.get("Tool_call_source", "unknown")
#         destination = tc.get("Tool_call_Destination", "unknown")
#         arguments = tc.get("Tool_call_Arguments", "")
#         tooltip_tool_call = f'{source} > {destination} , Message Passed: {arguments}'
#         tooltip_tool_call = escape_quotes(tooltip_tool_call)
#         dot_lines.append(f'    {source} -> "{destination}" [label="{arrow_counter}", tooltip="{tooltip_tool_call}"];')
#         arrow_counter += 1
#         response = tc.get("Tool_call_Response", "")
#         tooltip_tool_call_resp = f'{destination} > {source} , Message Passed: {response}'
#         tooltip_tool_call_resp = escape_quotes(tooltip_tool_call_resp)
#         dot_lines.append(f'    "{destination}" -> {source} [label="{arrow_counter}", tooltip="{tooltip_tool_call_resp}"];')
#         arrow_counter += 1

#     # Message3: Agent -> User (read from log)
#     msg3_source = msg3.get("Message Source", "unknown_agent")
#     msg3_destination = msg3.get("Message Destination", "User")
#     tooltip3 = f'{msg3_source} > {msg3_destination} , Message Passed: {msg3.get("Message Content", "")}'
#     tooltip3 = escape_quotes(tooltip3)
#     dot_lines.append(f'    {msg3_source} -> {msg3_destination} [label="{arrow_counter}", tooltip="{tooltip3}"];')
#     arrow_counter += 1

#     dot_lines.append("}")
    
#     with open(dot_filepath, "w") as f_out:
#         f_out.write("\n".join(dot_lines))
#     print(f"Dot file written to {dot_filepath}")

# if __name__ == "__main__":
#     if len(sys.argv) < 3:
#         print("Usage: python multi_agent_visualizer.py <log_json_file> <output_dot_file>")
#         sys.exit(1)
#     log_filepath = sys.argv[1]
#     dot_filepath = sys.argv[2]
#     if not os.path.exists(log_filepath):
#         print(f"Log file {log_filepath} does not exist.")
#         sys.exit(1)
#     main(log_filepath, dot_filepath)
