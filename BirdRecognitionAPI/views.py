import base64
import os
import zipfile
from datetime import datetime
from io import BytesIO

import bcrypt
import mysql.connector
from azure.storage.blob import BlobServiceClient
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from django.http import HttpResponse
from mysql.connector import Error
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['POST'])
def getData(request):
    sound_data = request.data.get("sound_data")
    # Decode the base64 encoded sound data (if it's base64 encoded)
    sound_bytes = base64.b64decode(sound_data)
    user_id = request.data.get("user_id")
    audio_name = request.data.get("audio_name")

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

    upload_sound_to_blob(user_id, audio_name)

    return Response(recording.detections)


@api_view(['POST'])
def getDataWithLocation(request):
    # Retrieve lon and lat values from the request data
    lon = request.data.get('lon')
    lat = request.data.get('lat')
    sound_data = request.data.get('sound_data')
    user_id = request.data.get("user_id")
    audio_name = request.data.get("audio_name")

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
    upload_sound_to_blob(user_id, audio_name)
    return Response(recording.detections)


@api_view(['POST'])
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
                        print("User authenticated successfully")
                        return Response({
                            "message": "User authenticated successfully",
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
def insert_sound(request):
    data = request.data
    name = data.get('name')
    length = data.get('length')
    blob_reference = data.get('blob_reference')
    user_id = data.get('user_id')
    time_added = data.get('time_added')

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
            INSERT INTO sounds (name, length, time_added, blob_reference, user_id)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, [name, length, time_added_formatted, blob_reference, user_id])
            connection.commit()
            return Response({"message": "Sound inserted successfully!"}, status=200)
    except Error as e:
        return Response({"error": str(e)}, status=500)
    finally:
        if connection and connection.is_connected():
            connection.close()


@api_view(['POST'])
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
def delete_sound(request):
    data = request.data
    blob_reference = data.get('blob_reference')
    user_id = data.get('user_id')

    if not all([blob_reference, user_id]):
        return Response({"error": "Missing required information (blob_reference, user_id)"}, status=400)

    connection_string = "BlobEndpoint=https://birdrecognitionapp.blob.core.windows.net/;QueueEndpoint=https://birdrecognitionapp.queue.core.windows.net/;FileEndpoint=https://birdrecognitionapp.file.core.windows.net/;TableEndpoint=https://birdrecognitionapp.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2030-01-01T17:44:07Z&st=2024-03-29T09:44:07Z&spr=https&sig=ZKmjN0p8xNBE%2FkSB97Bhw30GkP6Dqz87pzB2LVW7jhk%3D"
    container_name = "sounds"

    try:
        delete_blob_from_storage(blob_reference, container_name, connection_string,)

        # Now, delete the entry from your database
        connection = mysql.connector.connect(
            host='bird-recognition-mysql-db.mysql.database.azure.com',
            database='birdrecognitionapp',
            user='licenta',
            password='Admin123'
        )
        if connection.is_connected():
            cursor = connection.cursor()
            delete_query = "DELETE FROM sounds WHERE user_id = %s"
            cursor.execute(delete_query, (user_id,))
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
