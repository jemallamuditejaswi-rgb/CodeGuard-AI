
import ast
import json
import os
import subprocess
import sys
import tempfile
import streamlit as st
from datetime import datetime

# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="CodeGuard AI",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ CodeGuard AI")
st.subheader("AI-Assisted Python Code Review and Bug Detection")
st.write(
    "Analyze Python code, identify bugs, understand suggestions, "
    "compare fixes, and download reports."
)

st.info(
    "Safety: Run only trusted Python code. This tool executes code "
    "on your computer and is not a secure sandbox."
)

# ---------------- SAMPLE CODE ----------------

SAMPLE_CODE = '''import os

x = 10
y = 0

print("Hello CodeGuard AI")
print(x / y)
print(undefined_variable)
'''

# ---------------- SESSION STATE ----------------

if "code_input" not in st.session_state:
    st.session_state.code_input = SAMPLE_CODE

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "fixed_code" not in st.session_state:
    st.session_state.fixed_code = None


# ---------------- SYNTAX CHECK ----------------

def check_syntax(code):
    try:
        ast.parse(code)
        return True, "Syntax is correct!"
    except SyntaxError as error:
        return False, (
            f"Line {error.lineno}: {error.msg}"
        )


# ---------------- CODE QUALITY CHECK ----------------

def check_ruff(code):
    path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            newline="",
            delete=False
        ) as file:
            file.write(code)
            path = file.name

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--output-format",
                "json",
                path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode not in (0, 1):
            return None, (
                result.stderr.strip()
                or "Ruff could not complete the check."
            )

        try:
            issues = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None, "Could not read Ruff results."

        # Remove the temporary filename from displayed results.
        for issue in issues:
            issue["location"] = issue.get("location", {})

        return issues, None

    except FileNotFoundError:
        return None, (
            "Ruff is not installed. Install it using: "
            "python -m pip install ruff"
        )
    except subprocess.TimeoutExpired:
        return None, "Code-quality checking timed out."
    except Exception as error:
        return None, str(error)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# ---------------- RUNTIME CHECK ----------------

def check_runtime(code):
    path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            newline="",
            delete=False
        ) as file:
            file.write(code)
            path = file.name

        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=5
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "return_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Program timed out after 5 seconds.",
            "return_code": None
        }
    except Exception as error:
        return {
            "success": False,
            "output": "",
            "error": str(error),
            "return_code": None
        }
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# ---------------- ERROR EXPLANATIONS ----------------


    explanations = {
        "F401": (
            "Unused import. Remove the import if it is not needed."
        ),
        "F821": (
            "Undefined name. Check spelling or define the variable "
            "before using it."
        ),
        "F841": (
            "A local variable is assigned but never used."
        ),
        "E722": (
            "Avoid a bare except. Catch a specific exception instead."
        ),
        "E702": (
            "Multiple statements share one line. Put them on separate lines."
        ),
        "E999": (
            "Python syntax error. Check the line and its indentation."
        )
    }
   
def explain_issue(issue):
    explanations = {
        "F401": "Unused import. Remove the import if it is not needed.",
        "F821": "Undefined name. Check spelling or define the variable before using it.",
        "F841": "A local variable is assigned but never used.",
        "E722": "Avoid a bare except. Catch a specific exception instead.",
        "E702": "Multiple statements share one line. Put them on separate lines.",
        "E999": "Python syntax error. Check the line and its indentation."
    }

    code = issue.get("code", "")
    return explanations.get(
        code,
        "Review this line and the reported code-quality rule."
    )



def severity_for_issue(issue):
    code = issue.get("code", "")

    if code in ("F821", "E999"):
        return "High"

    if code in ("F401", "F841", "E722", "E702"):
        return "Medium"

    return "Low"


def explain_runtime_error(error):
    if "ZeroDivisionError" in error:
        return (
            "A number is being divided by zero. Check the denominator "
            "before dividing. Example: if y != 0: print(x / y)"
        )

    if "NameError" in error:
        return (
            "A variable or function name is undefined. Check spelling "
            "and define it before use."
        )

    if "TypeError" in error:
        return (
            "The operation may use incompatible data types. "
            "Check the values and their types."
        )

    if "IndexError" in error:
        return (
            "A list or sequence index is outside the available range. "
            "Check its length before accessing an index."
        )

    if "KeyError" in error:
        return (
            "The dictionary key was not found. Check the key or use "
            "a safe lookup method."
        )

    if "IndentationError" in error or "TabError" in error:
        return (
            "Check the indentation. Use consistent spaces in code blocks."
        )

    if "FileNotFoundError" in error:
        return "Check the file path and whether the file exists."

    if "timed out" in error.lower():
        return (
            "The program took too long. Check loops and operations "
            "that may not finish."
        )

    return (
        "Read the traceback and inspect the line where the error occurred."
    )

def show_severity(level):
    if level == "High":
        st.error("Severity: High")
    elif level == "Medium":
        st.warning("Severity: Medium")
    else:
        st.info("Severity: Low")


# ---------------- AUTOMATIC FIX ----------------

def automatic_fix(code):
    path = None

    try:
        # Ruff fixes are attempted only when syntax is valid.
        ast.parse(code)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            encoding="utf-8",
            newline="",
            delete=False
        ) as file:
            file.write(code)
            path = file.name

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--fix",
                path
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode not in (0, 1):
            return None, (
                result.stderr.strip()
                or "Automatic fixing could not complete."
            )

        with open(path, "r", encoding="utf-8") as file:
            fixed = file.read()

        return fixed, None

    except SyntaxError as error:
        return None, (
            f"Fix syntax first. Line {error.lineno}: {error.msg}"
        )
    except FileNotFoundError:
        return None, (
            "Ruff is not installed. Run: python -m pip install ruff"
        )
    except subprocess.TimeoutExpired:
        return None, "Automatic fixing timed out."
    except Exception as error:
        return None, str(error)
    finally:
        if path and os.path.exists(path):
            os.remove(path)


# ---------------- ANALYSIS FUNCTION ----------------

def analyze_code(code):
    syntax_ok, syntax_message = check_syntax(code)

    result = {
        "syntax_ok": syntax_ok,
        "syntax_message": syntax_message,
        "issues": [],
        "ruff_error": None,
        "runtime": None,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if syntax_ok:
        issues, ruff_error = check_ruff(code)
        result["issues"] = issues or []
        result["ruff_error"] = ruff_error
        result["runtime"] = check_runtime(code)

    return result


# ---------------- SESSION CALLBACK ----------------

def use_fixed_code():
    fixed = st.session_state.get("fixed_code")

    if fixed is not None:
        st.session_state.code_input = fixed
        st.session_state.analysis_result = None


# ---------------- CODE EDITOR ----------------

st.header("📝 Python Code Editor")

st.text_area(
    "Enter or edit your Python code",
    key="code_input",
    height=300
)

left, right = st.columns(2)

with left:
    analyze_clicked = st.button(
        "🔍 Analyze Code",
        use_container_width=True
    )

with right:
    fix_clicked = st.button(
        "🛠️ Fix Supported Issues",
        use_container_width=True
    )

if analyze_clicked:
    if not st.session_state.code_input.strip():
        st.warning("Please enter Python code first.")
    else:
        st.session_state.analysis_result = analyze_code(
            st.session_state.code_input
        )

if fix_clicked:
    current_code = st.session_state.code_input

    if not current_code.strip():
        st.warning("Please enter Python code first.")
    else:
        fixed, error = automatic_fix(current_code)

        if error:
            st.session_state.fixed_code = None
            st.error(error)
        else:
            st.session_state.fixed_code = fixed
            st.success("Automatic fix completed.")


# ---------------- ANALYSIS RESULTS ----------------

analysis = st.session_state.analysis_result

if analysis is not None:
    st.divider()
    st.header("📊 Analysis Results")

    if analysis["syntax_ok"]:
        st.success(analysis["syntax_message"])
    else:
        st.error("Syntax error: " + analysis["syntax_message"])

    st.subheader("🧹 Code Quality Checking")

    issues = analysis["issues"]

    if analysis["ruff_error"]:
        st.error(analysis["ruff_error"])
    elif not issues:
        st.success("No code-quality issues found!")
    else:
        st.warning(f"Found {len(issues)} issue(s).")

        for index, issue in enumerate(issues, start=1):
            location = issue.get("location", {})
            line_number = location.get("row", "?")
            code_name = issue.get("code", "Unknown")
            message = issue.get("message", "Code-quality issue")
            severity = severity_for_issue(issue)

            with st.expander(
                f"{index}. Line {line_number} — {code_name}: {message}",
                expanded=True
            ):
                st.write("**Suggestion:**")
                st.write(explain_issue(issue))
                show_severity(severity)

    st.subheader("⚙️ Runtime Error Detection")

    runtime = analysis["runtime"]

    if runtime is None:
        st.info("Runtime checking skipped because syntax is invalid.")
    elif runtime["success"]:
        st.success("Program executed successfully!")

        if runtime["output"].strip():
            st.code(runtime["output"], language="text")
        else:
            st.info("The program produced no printed output.")
    else:
        st.error("Runtime error detected!")

        if runtime["error"].strip():
            st.code(runtime["error"], language="text")
            st.write("**Explanation and suggestion:**")
            st.write(explain_runtime_error(runtime["error"]))

            high_errors = (
                "ZeroDivisionError",
                "NameError",
                "TypeError",
                "IndexError",
                "KeyError"
            )

            if any(
                error_name in runtime["error"]
                for error_name in high_errors
            ):
                show_severity("High")
            else:
                show_severity("Medium")

    st.divider()
    st.header("🧾 Final Summary")

    summary_left, summary_middle, summary_right = st.columns(3)

    with summary_left:
        st.metric(
            "Syntax",
            "PASS" if analysis["syntax_ok"] else "ERROR"
        )

    with summary_middle:
        if analysis["ruff_error"]:
            st.metric("Code Quality", "CHECK ERROR")
        else:
            st.metric("Issues Found", len(issues))

    with summary_right:
        if runtime is None:
            runtime_status = "NOT CHECKED"
        else:
            runtime_status = (
                "PASS" if runtime["success"] else "ERROR"
            )

        st.metric("Runtime", runtime_status)

    # ---------------- DOWNLOAD ANALYSIS REPORT ----------------

    report_lines = [
        "CODEGUARD AI - ANALYSIS REPORT",
        "=" * 36,
        f"Analysis time: {analysis['analyzed_at']}",
        "",
        "SYNTAX CHECK",
        analysis["syntax_message"],
        "",
        "CODE QUALITY"
    ]

    if analysis["ruff_error"]:
        report_lines.append("Checker error: " + analysis["ruff_error"])
    elif not issues:
        report_lines.append("No code-quality issues found.")
    else:
        for issue in issues:
            line_number = issue.get("location", {}).get("row", "?")
            code_name = issue.get("code", "Unknown")
            message = issue.get("message", "")
            report_lines.append(
                f"Line {line_number} | {code_name} | "
                f"{severity_for_issue(issue)} | {message}"
            )
            report_lines.append(
                "Suggestion: " + explain_issue(issue)
            )

    report_lines.extend(["", "RUNTIME CHECK"])

    if runtime is None:
        report_lines.append("Runtime check skipped.")
    elif runtime["success"]:
        report_lines.append("Program executed successfully.")
        report_lines.append("Output:")
        report_lines.append(runtime["output"])
    else:
        report_lines.append("Runtime error detected.")
        report_lines.append(runtime["error"])
        report_lines.append(
            "Suggestion: " + explain_runtime_error(runtime["error"])
        )

    st.download_button(
        "📄 Download Analysis Report",
        data="\n".join(report_lines),
        file_name="CodeGuard_AI_Report.txt",
        mime="text/plain",
        use_container_width=True
    )


# ---------------- FIXED CODE AND COMPARISON ----------------

fixed_code = st.session_state.fixed_code

if fixed_code is not None:
    st.divider()
    st.header("🛠️ Automatic Fix Results")

    st.write(
        "Ruff applies supported code-quality fixes. "
        "It does not automatically repair every runtime error."
    )

    if fixed_code == st.session_state.code_input:
        st.info(
            "No supported Ruff changes were needed for this version of the code."
        )
    else:
        st.success("Ruff changed the code.")

    st.subheader("🔎 Original vs Fixed Code")

    original_col, fixed_col = st.columns(2)

    with original_col:
        st.markdown("**Original Code**")
        st.code(
            st.session_state.code_input,
            language="python"
        )

    with fixed_col:
        st.markdown("**Fixed Code**")
        st.code(fixed_code, language="python")

    st.download_button(
        "⬇️ Download Fixed Python Code",
        data=fixed_code,
        file_name="fixed_code.py",
        mime="text/x-python",
        use_container_width=True
    )

    st.button(
        "↩️ Use Fixed Code in Editor",
        on_click=use_fixed_code,
        use_container_width=True
    )

    st.caption(
        "After using the fixed code in the editor, click Analyze Code "
        "to check the updated version."
    )

# ---------------- FOOTER ----------------

st.divider()
st.caption(
    "CodeGuard AI | Python Code Review and Bug Detection"
)
