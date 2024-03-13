import base64
import os

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from rest_framework.decorators import api_view
from rest_framework.response import Response


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
        min_conf=0.1,
    )
    recording.analyze()
    print(recording.detections)
    return Response(recording.detections)

@api_view(['POST'])
def getDataWithLocation(request):
    # Retrieve lon and lat values from the request data
    lon = request.data.get('lon')
    lat = request.data.get('lat')
    sound_data = request.data.get('sound_data')

    # Proceed only if all required parameters are provided
    if lon is None or lat is None or sound_data is None:
        return Response({'error': 'Missing required parameters'}, status=400)

    # Decode the base64 encoded sound data
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
        lat=float(lat),
        lon=float(lon),
        min_conf=0.1,
    )
    recording.analyze()
    print(lon)
    print(lat)
    print(recording.detections)
    return Response(recording.detections)
