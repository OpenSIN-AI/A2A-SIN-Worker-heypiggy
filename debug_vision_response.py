import sys, time, json, base64
sys.path.insert(0, '.')
from mcp_survey_runner import cua_screenshot_bytes, ask_vision_text
from PIL import Image
from io import BytesIO

print('1. Screenshot...', flush=True)
png = cua_screenshot_bytes()
img = Image.open(BytesIO(png)).convert('RGB')

print('2. Calling ask_vision_text with grid overlay...', flush=True)
prompt = """This image shows a web page with a numbered GRID OVERLAY (coordinates marked as [X,Y]).
Look at the image carefully. Find the FIRST survey card or NEXT/WEITER/SUBMIT button.
Reply with ONLY the coordinates like: COORD=X,Y
Nothing else."""
start = time.time()
result = ask_vision_text(img, prompt)
elapsed = time.time() - start
print(f'3. KI-Antwort: "{result}"', flush=True)
print(f'Time: {elapsed:.1f}s', flush=True)

print('4. Calling without grid overlay...', flush=True)
img2 = Image.open(BytesIO(png)).convert('RGB')
prompt2 = """This is a screenshot of a HeyPiggy survey page. 
Find the NEXT or WEITER or SUBMIT button.
Reply with ONLY: COORD=X,Y where X,Y are the coordinates from the image.
Nothing else."""
start2 = time.time()
result2 = ask_vision_text(img2, prompt2)
elapsed2 = time.time() - start2
print(f'5. KI-Antwort (ohne Grid): "{result2}"', flush=True)
print(f'Time: {elapsed2:.1f}s', flush=True)
