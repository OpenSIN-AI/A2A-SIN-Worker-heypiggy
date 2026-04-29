#!/usr/bin/env python3
import sys, time, json, base64, urllib.request, traceback
sys.path.insert(0, '.')
from mcp_survey_runner import cua_screenshot_bytes, _ask_nvidia, _ask_cloudflare, CF_TOKEN, NVIDIA_KEY
from PIL import Image
from io import BytesIO

print('1. Taking screenshot...', flush=True)
png = cua_screenshot_bytes()
img = Image.open(BytesIO(png)).convert('RGB')
buf = BytesIO()
img.save(buf, 'JPEG', quality=50)
img_b64 = base64.b64encode(buf.getvalue()).decode()
print(f'2. Screenshot encoded, length={len(img_b64)}', flush=True)

prompt = 'Grid overlay visible. Find the Next button. Reply: COORD=X,Y'
print(f'3. Calling _ask_nvidia with prompt: {prompt}', flush=True)
start = time.time()

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
    headers={'Authorization':f'Bearer {NVIDIA_KEY}','Content-Type':'application/json'}
)

try:
    resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
    text = resp['choices'][0]['message']['content']
    elapsed = time.time() - start
    print(f'4. Response text: "{text}"', flush=True)
    print(f'Time: {elapsed:.1f}s', flush=True)
except Exception as e:
    print(f'ERROR: {e}', flush=True)
    import traceback
    traceback.print_exc()
