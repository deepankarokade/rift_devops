import re

def reconstruct_format(raw_output: str):
    pattern = r"(LINTING|SYNTAX|LOGIC|TYPE_ERROR|IMPORT|INDENTATION) error in (.+) line (\d+) → Fix: (.+)"
    match = re.match(pattern, raw_output.strip())
    if not match:
        raise ValueError("Invalid classifier format")

    bug_type, file_path, line, fix = match.groups()

    return f"{bug_type} error in {file_path.lower()} line {line} → Fix: {fix}"
