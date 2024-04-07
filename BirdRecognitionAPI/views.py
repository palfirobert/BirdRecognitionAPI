import base64
import os

import mysql.connector
from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer
from mysql.connector import Error
from rest_framework.decorators import api_view
from rest_framework.response import Response
import bcrypt

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

