import os
from rest_framework.decorators import api_view
from rest_framework.response import Response
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
import base64


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
    file_path = os.path.abspath(os.path.join(sound_dir, 'bird_sound.wav'))

    with open(file_path, 'wb') as f:
        f.write(sound_bytes)

    analyzer = Analyzer()
    recording = Recording(
        analyzer,
        file_path,
        # lat=45.4244,
        # lon=24.7463,
        min_conf=0.1,
    )
    recording.analyze()
    print(recording.detections)
    return Response(recording.detections)
