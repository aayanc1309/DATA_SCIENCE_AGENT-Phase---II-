"""
Secure-ish Python Code Runner tool for MVP Phase 2.
Executes pandas and plotly code locally in memory.
In Phase 3 this will be replaced with Jupyter Kernel Gateway.
"""

import sys
import io
import json
import traceback
import pandas as pd

from app.services.file_service import file_service


def run_python_code(file_id: str, code: str) -> dict:
    """
    Executes a block of python code. 
    It injects the specific dataframe `df` into the globals.
    Catches stdout and extracts any plotly figure assigned to the `fig` variable.
    """
    # 1. Get the dataframe
    df = file_service.get_dataframe(file_id)
    if df is None:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Error: DataFrame not found in memory. Cannot execute code.",
            "error": "DataFrame not found",
            "visualizations": []
        }

    # 2. Setup execution environment
    # We provide a clean globals dict with pandas and the dataframe injected.
    exec_globals = {
        "pd": pd,
        "df": df.copy(), # Provide a copy so they don't break the base dataframe
        # Inject standard modules they might need (like numpy if available)
    }
    
    # We will try to pre-import plotly.express to make it easier for the model
    try:
        import plotly.express as px
        exec_globals["px"] = px
    except ImportError:
        pass

    # 3. Capture Stdout/Stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    sys.stdout = captured_stdout
    sys.stderr = captured_stderr

    success = True
    error_msg = None
    exec_locals = {}

    import ast

    # 4. Execute
    try:
        tree = ast.parse(code)
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_expr = tree.body.pop()
            code_to_exec = compile(tree, filename='<ast>', mode='exec')
            code_to_eval = compile(ast.Expression(last_expr.value), filename='<ast>', mode='eval')
            
            exec(code_to_exec, exec_globals, exec_locals)
            res = eval(code_to_eval, exec_globals, exec_locals)
            if res is not None:
                print(res)
        else:
            exec(code, exec_globals, exec_locals)
    except Exception as e:
        success = False
        error_msg = traceback.format_exc()
        print(f"🚨 [CodeRunner] EXEC ERROR:\n{error_msg}")
        print(f"🚨 [CodeRunner] FAILED CODE:\n{code}")

    # 5. Restore Stdout/Stderr
    sys.stdout = old_stdout
    sys.stderr = old_stderr

    stdout_str = captured_stdout.getvalue()
    stderr_str = captured_stderr.getvalue()

    # 6. Extract visualizations
    visualizations = []
    print(f"🧐 [CodeRunner] Exec completed. Locals keys: {list(exec_locals.keys())}")
    
    # Find any plotly figure in the local variables
    for var_name, var_val in exec_locals.items():
        if hasattr(var_val, "to_json") and "Figure" in type(var_val).__name__:
            try:
                fig_json = json.loads(var_val.to_json())
                visualizations.append({
                    "title": "Visualization",
                    "chart_type": "plotly",
                    "plotly_json": fig_json
                })
                print(f"📈 [CodeRunner] Successfully extracted figure from variable: {var_name}")
                break # Only grab the first one to avoid duplicates if they assigned it multiple times
            except Exception as fig_err:
                stderr_str += f"\nError converting figure '{var_name}' to JSON: {str(fig_err)}"

    return {
        "success": success,
        "stdout": stdout_str,
        "stderr": stderr_str,
        "error": error_msg,
        "visualizations": visualizations
    }
