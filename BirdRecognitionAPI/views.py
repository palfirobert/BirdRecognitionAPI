import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
import base64
import resampy

@api_view(['POST'])
def getData(request):
    sound_data=request.body
    # Decode the base64 encoded sound data (if it's base64 encoded)
    sound_bytes = base64.b64decode(sound_data)
    # Save the sound data as an MP3 file named "randunica.mp3" in the resources folder
    file_path = os.path.join('resources/sound', 'bird_sound.mp3')
    with open(file_path, 'wb') as f:
        f.write(sound_bytes)
    analyzer = Analyzer()
    recording = Recording(
        analyzer,
        "resources/sound/bird_sound.mp3",
        min_conf=0.25,
    )
    recording.analyze()
    return Response(recording.detections)
