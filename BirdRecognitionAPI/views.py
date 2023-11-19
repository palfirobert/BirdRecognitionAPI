import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
import base64
from moviepy.editor import *


@api_view(['POST'])
def getData(request):
    sound_data = request.body
    # Decode the base64 encoded sound data (if it's base64 encoded)
    sound_bytes = base64.b64decode(sound_data)

    # Ensure the directory exists
    sound_dir = 'BirdRecognitionAPI/resources/sound'
    if not os.path.exists(sound_dir):
        os.makedirs(sound_dir)

    # Use an absolute path
    file_path = os.path.abspath(os.path.join(sound_dir, 'bird_sound.3gp'))

    with open(file_path, 'wb') as f:
        f.write(sound_bytes)


    analyzer = Analyzer()
    recording = Recording(
        analyzer,
        file_path,
        min_conf=0.25,
    )
    recording.analyze()
    return Response(recording.detections)
