from app.integrations.groq_client import call_groq

SYSTEM_PROMPT = """You are a reflection agent in a multi-agent CI healing system.

The previous fix attempt failed.
Return short actionable correction strategy.
"""

def reflect(classified_failure, previous_patch, new_error):
    user_prompt = f"""
Previous failure classification:
{classified_failure}

Previous fix attempt:
{previous_patch}

New CI error:
{new_error}
"""
    return call_groq(SYSTEM_PROMPT, user_prompt)


def run(state):
    """Reflect on failed fix attempts and generate corrections."""
    classified_failure = state.get("classified_failures", [""])[0]
    previous_patch = state.get("applied_fixes", [""])[0]
    new_error = state.get("test_errors", "")
    
    correction = reflect(classified_failure, previous_patch, new_error)
    
    state["reflection"] = correction
    logs = list(state.get("logs") or [])
    logs.append("Reflection agent generated correction")
    state["logs"] = logs
    return state
