import ast
import logging

logger = logging.getLogger(__name__)

def validate_fix(updated_content):
    """
    Perform a basic syntax check on the updated content using AST.
    """
    try:
        ast.parse(updated_content)
        return "VALID"
    except SyntaxError as e:
        logger.error(f"Syntax error in generated fix: {e}")
        return f"INVALID: syntax error - {e}"
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return f"INVALID: {e}"


def run(state):
    """Validate fixes generated for classified failures."""
    applied_fixes = state.get("applied_fixes", [])
    
    validation_results = []
    for fix_content in applied_fixes:
        result = validate_fix(fix_content)
        validation_results.append(result)
    
    state["validation_results"] = validation_results
    logs = list(state.get("logs") or [])
    
    # Check if any fix failed validation
    all_valid = all(r == "VALID" for r in validation_results)
    if not all_valid:
        logs.append(f"Validation failed for some fixes: {validation_results}")
    else:
        logs.append(f"Validated {len(validation_results)} fixes (all VALID)")
    state["logs"] = logs
        
    return state
