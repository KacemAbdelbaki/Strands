import subprocess
from strands import tool

@tool
def terminal_exec(command: str):
    """Execute a command in the terminal."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return str(e)

@tool
def take_screenshot():
    """Takes a screenshot of the user's screen and returns it as a base64 encoded image."""
    import pyautogui
    import base64
    from io import BytesIO
    
    img = pyautogui.screenshot()
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"
