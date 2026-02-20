import os
import logging
from app.integrations.groq_client import call_groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous DevOps CI healing agent.

Rules:
- Only modify the necessary lines.
- Do NOT change unrelated code.
- Maintain original formatting.
- Do NOT add comments.
- Return the full updated file content only.
"""

def generate_fix(file_content, formatted_failure):
    user_prompt = f"""Original file content:

{file_content}

Failure:
{formatted_failure}

Generate corrected full file content.
"""

    return call_groq(SYSTEM_PROMPT, user_prompt)


def run(state):
    """Generate fixes for classified failures."""
    repo_path = state.get("repo_path") or state.get("repo_url")
    # Note: In a real scenario, repo_url is the https link, but we expect a local checkout.
    # We'll assume the workspace is the actual repo for now or use the repo_path if defined.
    
    classified_failures = state.get("classified_failures", [])
    applied_fixes = []
    logs = list(state.get("logs") or [])

    if not repo_path:
        logs.append("Fix generation skipped: repo_path missing")
        state["logs"] = logs
        return state
    
    for failure_str in classified_failures:
        # Extract file path from formatted string: "BUG_TYPE error in file_path line N → Fix: desc"
        try:
            file_path = failure_str.split(" error in ")[1].split(" line ")[0].strip()
            
            # Read real file content
            full_path = os.path.join(repo_path, file_path) if not os.path.isabs(file_path) else file_path
            
            if os.path.exists(full_path):
                with open(full_path, "r") as f:
                    content = f.read()
                
                fix = generate_fix(content, failure_str)
                applied_fixes.append(fix)
                
                # Write the fix back to the file for validation
                with open(full_path, "w") as f:
                    f.write(fix)
                logger.info(f"Applied fix to {file_path}")
        except Exception as e:
            logger.error(f"Failed to generate/apply fix for {failure_str}: {e}")
    
    state["applied_fixes"] = applied_fixes
    logs.append(f"Generated and applied {len(applied_fixes)} fixes")
    state["logs"] = logs
    return state
