import base64
import os
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
import gzip
import bcrypt
import io
import mysql.connector
from azure.storage.blob import BlobServiceClient
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from django.core.mail import send_mail
from django.http import HttpResponse
from django.http import JsonResponse
from mysql.connector import Error
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getData(request):
    sound_data = decompress_string(request.data.get("sound_data"))
    # Decode the base64 encoded sound data (if it's base64 encoded)
    sound_bytes = base64.b64decode(sound_data)
    user_id = request.data.get("user_id")
    audio_name = request.data.get("audio_name")
    is_new_recording = request.data.get("is_new_recording")

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
    if is_new_recording:
        upload_sound_to_blob(user_id, audio_name)

    return Response(recording.detections)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def getDataWithLocation(request):
    # Retrieve lon and lat values from the request data
    lon = request.data.get('lon')
    lat = request.data.get('lat')
    sound_data = decompress_string(request.data.get("sound_data"))
    user_id = request.data.get("user_id")
    audio_name = request.data.get("audio_name")
    is_new_recording = request.data.get("is_new_recording")

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
    if is_new_recording:
        upload_sound_to_blob(user_id, audio_name)
    return Response(recording.detections)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password').encode('utf-8')  # Encode password to bytes

    if not email or not password:
        return Response({"error": "Email and password are required"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            print("Connected to MySQL database")
            query = "SELECT * FROM user WHERE email = %s"
            cursor = connection.cursor()
            try:
                cursor.execute(query, (email,))
                user_details = cursor.fetchone()
                if user_details and bcrypt.checkpw(password, user_details[4].encode('utf-8')):
                    # Fetch additional user settings
                    settings_query = "SELECT language, use_location FROM user_settings WHERE user_id = %s"
                    cursor.execute(settings_query, (user_details[0],))
                    user_settings = cursor.fetchone()
                    if user_settings:
                        # Create a minimal Django User instance to tie with the Token
                        user, created = User.objects.get_or_create(username=email, defaults={'email': email})

                        # Generate or retrieve existing token
                        token, _ = Token.objects.get_or_create(user=user)
                        print("User authenticated successfully")
                        return Response({
                            "message": "User authenticated successfully",
                            "token": token.key,
                            "user_id": user_details[0],
                            "name": user_details[1],
                            "surname": user_details[2],
                            "email": user_details[3],
                            "language": user_settings[0],
                            "use_location": user_settings[1],
                            "password": user_details[4],
                        }, status=200)
                    else:
                        print("User settings not found")
                        return Response({"error": "User settings not found"}, status=404)
                else:
                    print("Invalid credentials")
                    return Response({"error": "Invalid credentials"}, status=401)
            except Error as e:
                print(f"Error: {e}")
                return Response({"error": str(e)}, status=500)
            finally:
                cursor.close()
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return Response({"error": str(e)}, status=500)
    finally:
        if connection.is_connected():
            connection.close()
            print("MySQL connection is closed")

    return Response({"error": "An unexpected error occurred"}, status=500)


@api_view(['POST'])
def signup(request):
    id = request.data.get('id')
    name = request.data.get('name')
    surname = request.data.get('surname')
    email = request.data.get('email')
    password = request.data.get('password')

    # Basic validation for required fields
    if not all([id, name, surname, email, password]):
        return Response({"error": "All fields (name, surname, email, password) are required"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            print("Connected to MySQL database")

            # Check if email already exists
            email_query = "SELECT COUNT(*) FROM user WHERE email = %s"
            cursor = connection.cursor()
            cursor.execute(email_query, (email,))
            if cursor.fetchone()[0] > 0:
                cursor.close()
                print("Email already exists")
                return Response({"error": "Email already exists"}, status=400)

            # Insert new user
            insert_query = "INSERT INTO user (id, name, surname, email, password) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(insert_query, (id, name, surname, email, password))
            connection.commit()
            print("User registered successfully")

            # Insert default user settings for the new user
            settings_insert_query = "INSERT INTO user_settings (user_id, language, use_location) VALUES (%s, %s, %s)"
            cursor.execute(settings_insert_query, (id, 'English', True))
            connection.commit()
            print("User settings added successfully")

            return Response({"message": "User registered successfully"}, status=201)
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("MySQL connection is closed")

    return Response({"error": "An unexpected error occurred"}, status=500)


@api_view(['PUT'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def updateUserDetails(request):
    # Deserialize the UserDetails object
    user_id = request.data.get('user_id')
    language = request.data.get('language')
    use_location = request.data.get('use_location')
    print(request.data)
    if not all([user_id, language, use_location is not None]):
        return Response({"user_id, language, and use_location are required"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # Update user_settings
            update_query = """
                UPDATE user_settings
                SET language = %s, use_location = %s
                WHERE user_id = %s
            """
            cursor.execute(update_query, (language, use_location, user_id))
            connection.commit()

            if cursor.rowcount == 0:
                # Assuming you want to create the settings if they don't exist
                insert_query = """
                    INSERT INTO user_settings (user_id, language, use_location)
                    VALUES (%s, %s, %s)
                """
                cursor.execute(insert_query, (user_id, language, use_location))
                connection.commit()
            print("User details updated successfully")
            return Response({"User details updated successfully"}, status=200)
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()

    return Response({"An unexpected error occurred"}, status=500)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def insert_sound(request):
    data = request.data
    name = data.get('name')
    length = data.get('length')
    blob_reference = data.get('blob_reference')
    user_id = data.get('user_id')
    time_added = data.get('time_added')
    id = data.get('id')

    if not all([name, length, blob_reference, user_id, time_added]):
        return Response({"error": "Missing required sound information"}, status=400)

    # Convert milliseconds to seconds
    try:
        timestamp_seconds = int(time_added) / 1000.0
        time_added_formatted = datetime.utcfromtimestamp(timestamp_seconds).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        return Response({"error": f"Incorrect time_added format: {e}"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            insert_query = """
            INSERT INTO sounds (id,name, length, time_added, blob_reference, user_id)
            VALUES (%s,%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, [id, name, length, time_added_formatted, blob_reference, user_id])
            connection.commit()
            return Response({"message": "Sound inserted successfully!"}, status=200)
    except Error as e:
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def insert_observation(request):
    data = request.data
    observation_date = data.get('observationDate')
    species = data.get('species')
    number = data.get('number')
    observer = data.get('observer')
    upload_date = data.get('uploadDate')
    location = data.get('location')
    user_id = data.get('userId')
    sound_id = data.get('soundId')

    if not all([observation_date, species, number, observer, upload_date, location, user_id, sound_id]):
        return Response({"error": "Missing required observation information"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # Delete existing observation for the same sound_id
            delete_query = "DELETE FROM observation_sheet WHERE sound_id = %s"
            cursor.execute(delete_query, [sound_id])

            # Convert and format timestamps with an added 2 hours
            observation_date_formatted = datetime.fromtimestamp(int(observation_date) / 1000) + timedelta(hours=3)
            observation_date_formatted = observation_date_formatted.strftime('%Y-%m-%d %H:%M:%S')

            upload_date_formatted = datetime.fromtimestamp(int(upload_date) / 1000) + timedelta(hours=3)
            upload_date_formatted = upload_date_formatted.strftime('%Y-%m-%d %H:%M:%S')

            # Insert the observation
            insert_query = """
            INSERT INTO observation_sheet (observation_date, species, number, observer, upload_date, location, user_id, sound_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query,
                           [observation_date_formatted, species, number, observer, upload_date_formatted, location,
                            user_id, sound_id])
            connection.commit()
            return Response({"message": "Observation inserted successfully!"}, status=200)
    except Error as e:
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_observation(request):
    sound_id = request.data.get('soundId')
    upload_date = request.data.get("uploadDate")
    location = request.data.get("location")
    user_id = request.data.get("userId")
    print(sound_id)
    print(upload_date)
    print(location)
    print(user_id)

    # Initialize database connection outside of the try block
    connection = None
    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # Check if sound_id is provided
            if sound_id:
                delete_query = "DELETE FROM observation_sheet WHERE sound_id = %s"
                cursor.execute(delete_query, [sound_id])
            else:
                # Delete based on user_id, location, and upload_date if sound_id is not provided
                delete_query = """
                DELETE FROM observation_sheet
                WHERE user_id = %s AND location = %s AND upload_date = %s
                """
                cursor.execute(delete_query, [user_id, location, upload_date])

            connection.commit()

            if cursor.rowcount > 0:
                return Response({"message": "Observation deleted successfully!"}, status=200)
            else:
                return Response({"error": "Observation not found"}, status=404)

    except Error as e:
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()

    return Response({"error": "Database connection could not be established"}, status=500)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def download_user_sounds(request):
    data = request.data
    user_id = data.get('user_id')

    if not user_id:
        return Response({"error": "User ID is required"}, status=400)

    container_name = "sounds"
    connection_string = "BlobEndpoint=https://birdrecognitionapp.blob.core.windows.net/;QueueEndpoint=https://birdrecognitionapp.queue.core.windows.net/;FileEndpoint=https://birdrecognitionapp.file.core.windows.net/;TableEndpoint=https://birdrecognitionapp.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-01-01T17:44:07Z&st=2024-03-29T09:44:07Z&spr=https&sig=ZKmjN0p8xNBE%2FkSB97Bhw30GkP6Dqz87pzB2LVW7jhk%3D"

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    zip_buffer = BytesIO()

    try:
        container_client = blob_service_client.get_container_client(container_name)
        user_prefix = f"{user_id}/"
        sound_files = list(container_client.list_blobs(name_starts_with=user_prefix))

        if not sound_files:
            return Response({"message": "No sounds found for the user"}, status=404)

        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for blob in sound_files:
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob.name)
                blob_data = blob_client.download_blob().readall()
                download_file_name = blob.name.replace(user_prefix, "", 1)

                zip_file.writestr(download_file_name, blob_data)

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename={user_id}_sounds.zip'

        return response
    except Exception as e:
        return Response({"error": f"An error occurred: {e}"}, status=500)


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_sound(request):
    data = request.data
    blob_reference = data.get('blob_reference')
    user_id = data.get('user_id')
    file_name = data.get('file_name')

    if not all([blob_reference, user_id]):
        return Response({"error": "Missing required information (blob_reference, user_id)"}, status=400)

    connection_string = "BlobEndpoint=https://birdrecognitionapp.blob.core.windows.net/;QueueEndpoint=https://birdrecognitionapp.queue.core.windows.net/;FileEndpoint=https://birdrecognitionapp.file.core.windows.net/;TableEndpoint=https://birdrecognitionapp.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-01-01T17:44:07Z&st=2024-03-29T09:44:07Z&spr=https&sig=ZKmjN0p8xNBE%2FkSB97Bhw30GkP6Dqz87pzB2LVW7jhk%3D"
    container_name = "sounds"

    try:
        delete_blob_from_storage(blob_reference, container_name, connection_string, )

        # Now, delete the entry from your database
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            delete_query = "DELETE FROM sounds WHERE user_id = %s AND name = %s"
            cursor.execute(delete_query, (user_id, file_name))
            connection.commit()

            if cursor.rowcount == 0:
                return Response({"Sound not found in the database."}, status=404)

            return Response({"Sound deleted successfully"}, status=200)
    except Error as db_error:
        return Response({f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        return Response({f"Storage error: {str(e)}"}, status=500)
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()


def upload_sound_to_blob(user_id, audio_name):
    # Replace with your Azure Blob Storage connection string
    connection_string = "BlobEndpoint=https://birdrecognitionapp.blob.core.windows.net/;QueueEndpoint=https://birdrecognitionapp.queue.core.windows.net/;FileEndpoint=https://birdrecognitionapp.file.core.windows.net/;TableEndpoint=https://birdrecognitionapp.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-01-01T17:44:07Z&st=2024-03-29T09:44:07Z&spr=https&sig=ZKmjN0p8xNBE%2FkSB97Bhw30GkP6Dqz87pzB2LVW7jhk%3D"

    # Name of the container you want to upload to
    container_name = "sounds/" + user_id

    # Local path to the file you want to upload
    local_file_path = "BirdRecognitionAPI/resources/sound/bird_sound.wav"

    # Name you want to save the file as in the container
    blob_name = audio_name

    # Create a blob service client
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Create a blob client using the local file name as the name for the blob
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Upload the sound file
    with open(local_file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    print(f"'{blob_name}' uploaded to container '{container_name}' successfully.")


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_creation_date_of_sounds(request):
    user_id = request.query_params.get('user_id')

    if not user_id:
        return Response({"error": "Missing required information (user_id)"}, status=400)

    connection_string = "BlobEndpoint=https://birdrecognitionapp.blob.core.windows.net/;QueueEndpoint=https://birdrecognitionapp.queue.core.windows.net/;FileEndpoint=https://birdrecognitionapp.file.core.windows.net/;TableEndpoint=https://birdrecognitionapp.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-01-01T17:44:07Z&st=2024-03-29T09:44:07Z&spr=https&sig=ZKmjN0p8xNBE%2FkSB97Bhw30GkP6Dqz87pzB2LVW7jhk%3D"

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)  # Use `dictionary=True` to get results as dict
            query = "SELECT name, UNIX_TIMESTAMP(time_added) AS time_added FROM sounds WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            sounds = cursor.fetchall()

            # Convert to hashmap format: {sound_name: time_added_timestamp}
            sounds_map = {sound['name']: sound['time_added'] for sound in sounds}

            return Response(sounds_map, status=200)

    except Error as db_error:
        return Response({f"Database error: {str(db_error)}"}, status=500)
    except Exception as e:
        return Response({f"Error: {str(e)}"}, status=500)
    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_observations_by_user(request, user_id):
    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)  # use dictionary=True to get results as dictionaries

            # Select all observations for the given user ID
            select_query = """
            SELECT observation_date, species, number, observer, upload_date, location, user_id, sound_id
            FROM observation_sheet
            WHERE user_id = %s
            """
            cursor.execute(select_query, (user_id,))

            results = cursor.fetchall()
            # Format the results to match the DTO structure
            observations = []
            for row in results:
                observation = {
                    'observationDate': row['observation_date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'species': row['species'],
                    'number': row['number'],
                    'observer': row['observer'],
                    'uploadDate': row['upload_date'].strftime('%Y-%m-%d %H:%M:%S'),
                    'location': row['location'],
                    'userId': row['user_id'],
                    'soundId': row['sound_id']
                }
                observations.append(observation)

            return JsonResponse(observations, safe=False)

    except Error as e:
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()


def delete_blob_from_storage(blob_name, container_name, connection_string):
    try:
        # Create a BlobServiceClient using a connection string
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Create a BlobClient to interact with a specific blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Delete the blob
        blob_client.delete_blob()

        print(f"The blob '{blob_name}' has been deleted from container '{container_name}'.")

    except Exception as e:
        print(f"An error occurred: {e}")


@api_view(['POST'])
def send_security_code(request):
    data = request.data
    email = data.get('email')
    security_code = data.get('securityCode')
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    # Send email with the security code
    send_mail(
        'Your Security Code',
        f'Your security code is {security_code}.',
        'from@example.com',  # Change to your actual sender email
        [email],
        fail_silently=False,
    )

    # Store the security code in the session for verification later
    request.session['security_code'] = security_code
    request.session['email'] = email

    return JsonResponse({'message': 'Security code sent successfully.'})


@api_view(['POST'])
def update_password(request):
    email = request.data.get('email')
    new_password = request.data.get('newPassword')

    # Basic validation for required fields
    if not email or not new_password:
        return Response({"error": "User ID and new password are required"}, status=400)

    try:
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # Update user's password
            update_query = "UPDATE user SET password = %s WHERE email = %s"
            cursor.execute(update_query, (new_password, email))
            connection.commit()

            return Response({"message": "Password updated successfully"}, status=200)
    except Error as e:
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()

    return Response({"error": "An unexpected error occurred"}, status=500)


def decompress_string(compressed_data_base64):
    compressed_data = base64.b64decode(compressed_data_base64)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed_data), mode='rb') as f:
        decompressed_data = f.read()
    return decompressed_data.decode('utf-8')