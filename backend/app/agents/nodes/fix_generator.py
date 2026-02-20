import os
import logging
from app.integrations.groq_client import call_groq

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert code fixing agent for CI/CD pipelines.

Your task is to fix bugs and errors in code files while preserving all existing functionality.

CRITICAL RULES:
1. NEVER delete existing code unless it's the direct cause of the error
2. ONLY modify the specific lines that are causing the failure
3. Preserve ALL other code exactly as it is
4. Maintain original formatting, indentation, and style
5. Do NOT add comments or explanations
6. Do NOT remove imports, functions, or classes unless they are the error source
7. Return the COMPLETE file with the fix applied

WHAT TO FIX:
- Syntax errors (missing colons, brackets, quotes)
- Logic errors (wrong operators, incorrect conditions)
- Import errors (missing or incorrect imports)
- Type errors (wrong data types)
- Runtime errors (null references, index errors)

WHAT NOT TO DO:
- Do NOT delete entire files
- Do NOT remove working code
- Do NOT change code style or formatting unnecessarily
- Do NOT add new features
- Do NOT refactor unrelated code

Output format: Return ONLY the complete corrected file content, nothing else.
"""

def generate_fix(file_content, formatted_failure):
    user_prompt = f"""You are fixing a bug in a code file. Here is the original file:

```
{file_content}
```

The error/failure detected:
{formatted_failure}

Instructions:
1. Identify the exact line(s) causing the error
2. Fix ONLY those specific lines
3. Keep ALL other code exactly the same
4. Return the COMPLETE file with the fix applied

IMPORTANT: Do NOT delete code. Do NOT remove functions or classes. Only fix the specific error.

Return the complete corrected file content below:
"""

    return call_groq(SYSTEM_PROMPT, user_prompt)


def run(state):
    """Generate fixes for classified failures."""
    repo_path = state.get("repo_path") or state.get("repo_url")
    
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
                    original_content = f.read()
                
                # Safety check: Don't process empty files
                if not original_content.strip():
                    logger.warning(f"Skipping empty file: {file_path}")
                    continue
                
                # Count original lines and functions/classes
                original_lines = len(original_content.splitlines())
                original_functions = original_content.count("def ")
                original_classes = original_content.count("class ")
                
                logger.info(f"Original file stats - Lines: {original_lines}, Functions: {original_functions}, Classes: {original_classes}")
                
                fix = generate_fix(original_content, failure_str)
                
                # Safety check 1: Ensure fix is not empty or too short
                if not fix or len(fix.strip()) < 10:
                    logger.error(f"Generated fix is too short or empty for {file_path}, skipping")
                    logs.append(f"Fix generation failed for {file_path}: output too short")
                    continue
                
                # Safety check 2: Ensure fix is not drastically shorter than original
                if len(fix) < len(original_content) * 0.5:  # Changed from 0.3 to 0.5 (50%)
                    logger.error(f"Generated fix is suspiciously short for {file_path} (original: {len(original_content)}, fix: {len(fix)})")
                    logs.append(f"Fix rejected for {file_path}: suspiciously short output (original: {len(original_content)} chars, fix: {len(fix)} chars)")
                    continue
                
                # Safety check 3: Ensure functions/classes are not deleted
                fix_lines = len(fix.splitlines())
                fix_functions = fix.count("def ")
                fix_classes = fix.count("class ")
                
                if fix_functions < original_functions * 0.8:  # Lost more than 20% of functions
                    logger.error(f"Fix deleted too many functions for {file_path} (original: {original_functions}, fix: {fix_functions})")
                    logs.append(f"Fix rejected for {file_path}: too many functions deleted")
                    continue
                
                if fix_classes < original_classes * 0.8:  # Lost more than 20% of classes
                    logger.error(f"Fix deleted too many classes for {file_path} (original: {original_classes}, fix: {fix_classes})")
                    logs.append(f"Fix rejected for {file_path}: too many classes deleted")
                    continue
                
                # Safety check 4: Ensure line count is reasonable
                if fix_lines < original_lines * 0.6:  # Lost more than 40% of lines
                    logger.error(f"Fix deleted too many lines for {file_path} (original: {original_lines}, fix: {fix_lines})")
                    logs.append(f"Fix rejected for {file_path}: too many lines deleted (original: {original_lines}, fix: {fix_lines})")
                    continue
                
                # All safety checks passed
                applied_fixes.append(fix)
                
                # Write the fix back to the file for validation
                with open(full_path, "w") as f:
                    f.write(fix)
                logger.info(f"Applied fix to {file_path} - Lines: {fix_lines}, Functions: {fix_functions}, Classes: {fix_classes}")
                logs.append(f"Applied fix to {file_path} (preserved {fix_functions}/{original_functions} functions, {fix_classes}/{original_classes} classes)")
            else:
                logger.warning(f"File not found: {full_path}")
                logs.append(f"File not found: {file_path}")
        except Exception as e:
            logger.error(f"Failed to generate/apply fix for {failure_str}: {e}")
            logs.append(f"Fix generation error: {str(e)}")
    
    state["applied_fixes"] = applied_fixes
    
    if len(applied_fixes) > 0:
        logs.append(f"Successfully generated and applied {len(applied_fixes)} fixes")
    else:
        logs.append(f"No fixes were applied (all rejected by safety checks or errors)")
    
    state["logs"] = logs
    return state
