from rest_framework.decorators import api_view
from rest_framework.response import Response
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer



@api_view(['POST'])
def getData(request):
    analyzer = Analyzer()
    recording = Recording(
        analyzer,
        "resources/sound/randunica.mp3",
        min_conf=0.25,
    )
    recording.analyze()
    return Response(recording.detections)
