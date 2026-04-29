#!/usr/bin/env python3
import sys, time, json, base64, urllib.request
sys.path.insert(0, '.')
from mcp_survey_runner import cua_screenshot_bytes, _ask_nvidia, _extract_coord
from PIL import Image
from io import BytesIO

print('1. Taking screenshot...', flush=True)
png = cua_screenshot_bytes()
img = Image.open(BytesIO(png)).convert('RGB')
buf = BytesIO()
img.save(buf, 'JPEG', quality=50)
img_b64 = base64.b64encode(buf.getvalue()).decode()
print(f'2. Screenshot encoded, length={len(img_b64)}', flush=True)

print('3. Calling _ask_nvidia...', flush=True)
start = time.time()
prompt = 'Grid overlay visible. Find the Next button. Reply: COORD=X,Y'
result = _ask_nvidia(img_b64, prompt)
elapsed = time.time() - start
print(f'4. Result: {result}', flush=True)
print(f'Time: {elapsed:.1f}s', flush=True)

if result:
    print(f'5. Coordinates: {result}', flush=True)
else:
    print('5. No coordinates returned. Checking raw response...', flush=True)
    data = json.dumps({
        'model': 'mistralai/mistral-large-3-675b-instruct-2512',
        'messages': [{'role':'user','content':[
            {'type':'text','text':prompt},
            {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
        ]}],'max_tokens':30
    }).encode()
    req = urllib.request.Request(
        'https://integrate.api.nvidia.com/v1/chat/completions',
        data=data,
        headers={'Authorization':f'Bearer {open(".env").read().split("NVIDIA_API_KEY=")[1].split("\\n")[0].strip().strip("\\\"")}','Content-Type':'application/json'}
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = resp['choices'][0]['message']['content']
        print(f'6. Raw response text: {text}', flush=True)
        coords = _extract_coord(text)
        print(f'7. Parsed coords: {coords}', flush=True)
    except Exception as e:
        print(f'ERROR: {e}', flush=True)
