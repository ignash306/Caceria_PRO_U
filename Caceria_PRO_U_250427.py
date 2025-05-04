import flet as ft
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
import math
import serial
import serial.tools.list_ports
import threading
import os
import webbrowser
import sys

serial_lock = threading.Lock()  # Lock for serial port access

def generate_kml(longitude1, latitude1, longitude2, latitude2, length, filename, line_color, line_width):
    """
    Generates a KML file with a straight line starting at Point 1, passing through Point 2,
    and extending by a specified length.

    Args:
        longitude1 (float): Longitude of Point 1.
        latitude1 (float): Latitude of Point 1.
        longitude2 (float): Longitude of Point 2.
        latitude2 (float): Latitude of Point 2.
        length (float): Length to extend the line (in meters).
        filename (str): Path to save the KML file.
    """
    earth_radius = 6378137  # Radius of the Earth in meters

    # Calculate direction vector
    direction_longitude = float(longitude2) - float(longitude1)
    direction_latitude = float(latitude2) - float(latitude1)
    magnitude = math.sqrt(direction_longitude**2 + direction_latitude**2)

    if magnitude == 0:
        raise ValueError("The two points cannot be the same.")

    # Normalize direction vector
    direction_longitude /= magnitude
    direction_latitude /= magnitude

    # Calculate extended endpoint
    delta_longitude = (length / (earth_radius * math.cos(math.pi * float(latitude2) / 180))) * (180 / math.pi)
    delta_latitude = (length / earth_radius) * (180 / math.pi)
    end_longitude = float(longitude2) + direction_longitude * delta_longitude
    end_latitude = float(latitude2) + direction_latitude * delta_latitude

    # Create KML document
    kml_doc = KML.kml(
        KML.Placemark(
            KML.Style(
                KML.LineStyle(
                    KML.color(line_color),  # Usar color personalizado
                    KML.width(line_width),  # Usar ancho personalizado
                )
            ),
            KML.LineString(
                KML.coordinates(f"{longitude1},{latitude1},0 {longitude2},{latitude2},0 {end_longitude},{end_latitude},0")
            )
        )
    )

    # Save KML file
    with open(filename, 'wb') as file:
        file.write(etree.tostring(kml_doc, pretty_print=True))

def generate_circle_kml(center_longitude, center_latitude, radius_km, filename, line_color, line_width):
    """
    Generates a KML file with a circle of a specified radius around a center point.

    Args:
        center_longitude (float): Longitude of the center point.
        center_latitude (float): Latitude of the center point.
        radius_km (float): Radius of the circle in kilometers.
        filename (str): Path to save the KML file.
    """
    earth_radius = 6371  # Earth's radius in kilometers
    num_points = 100  # Number of points to approximate the circle

    # Calculate circle points
    circle_points = []
    for i in range(num_points + 1):
        angle = 2 * math.pi * i / num_points
        delta_lat = (radius_km / earth_radius) * (180 / math.pi)
        delta_lon = (radius_km / (earth_radius * math.cos(math.pi * center_latitude / 180))) * (180 / math.pi)
        point_lat = center_latitude + delta_lat * math.sin(angle)
        point_lon = center_longitude + delta_lon * math.cos(angle)
        circle_points.append(f"{point_lon},{point_lat},0")

    # Create KML document
    kml_doc = KML.kml(
        KML.Placemark(
            KML.Style(
                KML.LineStyle(
                    KML.color(line_color),  # Usar color personalizado
                    KML.width(line_width),  # Usar ancho personalizado
                )
            ),
            KML.LineString(
                KML.coordinates(" ".join(circle_points))
            )
        )
    )

    # Save KML file
    with open(filename, 'wb') as file:
        file.write(etree.tostring(kml_doc, pretty_print=True))

def read_gps_coordinates(port, baudrate, callback):
    """
    Reads GPS coordinates from a serial port and passes them to a callback function.

    Args:
        port (str): Serial port name.
        baudrate (int): Baud rate for the serial connection.
        callback (function): Function to pass the longitude and latitude.
    """
    def read_from_port():
        try:
            with serial_lock:
                print(f"Connecting to GPS on port {port} with baudrate {baudrate}...")
                with serial.Serial(port, baudrate=baudrate, timeout=5) as ser:
                    ser.reset_input_buffer()
                    while True:
                        line = ser.readline().decode('ascii', errors='replace').strip()
                        print(f"Received data: {line}")

                        if line.startswith('$GNGGA') or line.startswith('$GPGGA'):
                            parts = line.split(',')
                            if len(parts) > 5 and parts[2] and parts[4]:
                                try:
                                    lat = float(parts[2])
                                    lon = float(parts[4])
                                    lat_deg = int(lat / 100)
                                    lon_deg = int(lon / 100)
                                    lat_min = lat - lat_deg * 100
                                    lon_min = lon - lon_deg * 100
                                    latitude = lat_deg + lat_min / 60
                                    longitude = lon_deg + lon_min / 60
                                    if parts[3] == 'S':
                                        latitude = -latitude
                                    if parts[5] == 'W':
                                        longitude = -longitude
                                    print(f"Processed coordinates: Longitude={longitude}, Latitude={latitude}")
                                    callback(longitude, latitude)
                                    break
                                except ValueError as e:
                                    print(f"Error processing GGA coordinates: {e}")

                        elif line.startswith('$GNRMC') or line.startswith('$GPRMC'):
                            parts = line.split(',')
                            if len(parts) > 6 and parts[3] and parts[5]:
                                try:
                                    lat = float(parts[3])
                                    lon = float(parts[5])
                                    lat_deg = int(lat / 100)
                                    lon_deg = int(lon / 100)
                                    lat_min = lat - lat_deg * 100
                                    lon_min = lon - lon_deg * 100
                                    latitude = lat_deg + lat_min / 60
                                    longitude = lon_deg + lon_min / 60
                                    if parts[4] == 'S':
                                        latitude = -latitude
                                    if parts[6] == 'W':
                                        longitude = -longitude
                                    print(f"Processed coordinates: Longitude={longitude}, Latitude={latitude}")
                                    callback(longitude, latitude)
                                    break
                                except ValueError as e:
                                    print(f"Error processing RMC coordinates: {e}")

                        else:
                            print("Received line does not contain valid GGA or RMC data.")
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")
            callback(None, None)
        except Exception as e:
            print(f"Error reading GPS data: {e}")
            callback(None, None)

    threading.Thread(target=read_from_port, daemon=True).start()

def get_serial_ports():
    """
    Returns a list of available serial ports.
    """
    ports = serial.tools.list_ports.comports()
    return [port.device for port in ports]

def get_next_filename(directory, base_name, extension):
    """
    Generates the next available filename in the specified directory.

    Args:
        directory (str): The directory where the file will be saved.
        base_name (str): The base name of the file (e.g., "direccional").
        extension (str): The file extension (e.g., "kml").

    Returns:
        str: The next available filename with an incremented number.
    """
    counter = 1
    while True:
        filename = os.path.join(directory, f"{base_name} {counter}.{extension}")
        if not os.path.exists(filename):
            return filename
        counter += 1

def calculate_angle(longitude1, latitude1, longitude2, latitude2):
    """
    Calculates the angle with respect to the north (0°) between two points.

    Args:
        longitude1 (float): Longitude of Point 1.
        latitude1 (float): Latitude of Point 1.
        longitude2 (float): Longitude of Point 2.
        latitude2 (float): Latitude of Point 2.

    Returns:
        float: Angle in degrees.
    """
    delta_lon = longitude2 - longitude1
    delta_lat = latitude2 - latitude1
    angle = math.degrees(math.atan2(delta_lon, delta_lat))
    return (angle + 360) % 360  # Normalize to 0-360 degrees

def update_compass_display(page):
    """
    Updates the compass display to show the angle between Point 1 and Point 2.
    """
    try:
        if longitude1.value and latitude1.value and longitude2.value and latitude2.value:
            lon1 = float(longitude1.value)
            lat1 = float(latitude1.value)
            lon2 = float(longitude2.value)
            lat2 = float(latitude2.value)
            angle = calculate_angle(lon1, lat1, lon2, lat2)
            compass_angle_display.value = f"{angle:.2f}°"

            # Update the position of the point
            center_x, center_y = 150, 150  # Center of the larger compass
            radius = 110  # Reduced radius to move the point inward
            point_x = center_x + radius * math.sin(math.radians(angle))
            point_y = center_y - radius * math.cos(math.radians(angle))  # Invert Y-axis for container

            compass_point.left = point_x - 7.5  # Adjust for point size
            compass_point.top = point_y - 7.5
            compass_point.visible = True
        else:
            compass_angle_display.value = "N/A"
            compass_point.visible = False
    except ValueError:
        compass_angle_display.value = "Error"
        compass_point.visible = False
    page.update()

def main(page: ft.Page):
    page.title = "GPS KML Generator"
    page.scroll = "auto"
    page.theme_mode = ft.ThemeMode.DARK  # Establecer el modo oscuro

    # Stop the program when the browser window is closed
    def on_window_close(e):
        print("Browser window closed. Exiting program...")
        os._exit(0)  # Forcefully terminate the program

    page.on_disconnect = on_window_close

    # Error display components
    error_display_1 = ft.Text("", color="red", size=14)
    error_display_2 = ft.Text("", color="red", size=14)

    def show_error(message):
        # Shift the previous error to the second display and show the new error in the first
        error_display_2.value = error_display_1.value
        error_display_1.value = message
        page.update()

    # Snackbar para notificaciones visuales
    snackbar = ft.SnackBar(content=ft.Text(""), duration=3000)
    page.overlay.append(snackbar)

    def show_snackbar(message, success=True):
        snackbar.content.value = message
        snackbar.bgcolor = ft.Colors.GREEN if success else ft.Colors.RED
        snackbar.open = True
        page.update()

    # UI Components
    global longitude1
    global latitude1
    global longitude2
    global latitude2
    longitude1 = ft.TextField(label="Longitude Point 1", width=200)
    latitude1 = ft.TextField(label="Latitude Point 1", width=200)
    longitude2 = ft.TextField(label="Longitude Point 2", width=200)
    latitude2 = ft.TextField(label="Latitude Point 2", width=200)
    line_length = ft.TextField(label="Line Length (m)", width=200, value="50000")
    gps_status1 = ft.Text("GPS Status Point 1: Disconnected", color="red")
    gps_status2 = ft.Text("GPS Status Point 2: Disconnected", color="red")
    port_combo1 = ft.Dropdown(label="GPS Port Point 1", options=[ft.dropdown.Option(p) for p in get_serial_ports()])
    port_combo2 = ft.Dropdown(label="GPS Port Point 2", options=[ft.dropdown.Option(p) for p in get_serial_ports()])
    baudrate_combo1 = ft.Dropdown(
        label="Baudrate Point 1",
        options=[ft.dropdown.Option(str(b)) for b in [4800, 9600, 19200, 38400, 57600, 115200]],
        value="9600"
    )
    baudrate_combo2 = ft.Dropdown(
        label="Baudrate Point 2",
        options=[ft.dropdown.Option(str(b)) for b in [4800, 9600, 19200, 38400, 57600, 115200]],
        value="9600"
    )

    def load_gps(point, callback):
        """
        Loads GPS data for a specific point.

        Args:
            point (int): Point number (1 or 2).
            callback (function): Function to handle the GPS data.
        """
        port = port_combo1.value if point == 1 else port_combo2.value
        baudrate = baudrate_combo1.value if point == 1 else baudrate_combo2.value

        if not port or not baudrate:
            show_error(f"Select a valid port and baudrate for Point {point}.")
            callback(None, None)
            return

        status_label = gps_status1 if point == 1 else gps_status2
        status_label.value = f"GPS Status Point {point}: Connecting..."
        page.update()

        def gps_callback(lon, lat):
            if lon and lat:
                if point == 1:
                    longitude1.value = str(lon)
                    latitude1.value = str(lat)
                    gps_status1.value = "GPS Status Point 1: Connected"
                else:
                    longitude2.value = str(lon)
                    latitude2.value = str(lat)
                    gps_status2.value = "GPS Status Point 2: Connected"
            else:
                status_label.value = f"GPS Status Point {point}: Error"
                show_error(f"Failed to load GPS data for Point {point}.")
            page.update()
            callback(lon, lat)  # Pass only two arguments to the callback

        try:
            read_gps_coordinates(port, int(baudrate), gps_callback)
        except Exception as e:
            show_error(f"Error initializing GPS for Point {point}: {e}")
            status_label.value = f"GPS Status Point {point}: Error"
            page.update()

    def load_both_gps_and_generate():
        """
        Loads GPS data for both points and generates the KML file if both are successfully loaded.
        """
        gps_data = {"point1": None, "point2": None}

        def on_both_loaded():
            if gps_data["point1"] and gps_data["point2"]:
                # Update the compass display with the loaded GPS data
                update_compass_display(page)
                # Generate the KML file
                generate_kml_file()

        def point1_callback(lon, lat):
            if lon and lat:
                gps_data["point1"] = (lon, lat)
                on_both_loaded()

        def point2_callback(lon, lat):
            if lon and lat:
                gps_data["point2"] = (lon, lat)
                on_both_loaded()

        load_gps(1, point1_callback)  # Load GPS for Point 1
        load_gps(2, point2_callback)  # Load GPS for Point 2

    # Configuración avanzada: opciones de estilo
    radius_dropdown = ft.Dropdown(
        label="Radius (km)",
        options=[
            ft.dropdown.Option(str(i), text=f"{i} km") for i in range(5, 105, 5)  # Generate options from 5 to 100 km
        ],
        value="5",  # Default radius value
    )

    line_color_dropdown = ft.Dropdown(
        label="Line Color",
        options=[
            ft.dropdown.Option("ff0000ff", text="Red"),      # Rojo (ARGB: ff0000ff)
            ft.dropdown.Option("ff00ff00", text="Green"),    # Verde (ARGB: ff00ff00)
            ft.dropdown.Option("ffff0000", text="Blue"),     # Azul (ARGB: ffff0000)
            ft.dropdown.Option("ffffff00", text="Yellow"),   # Amarillo (ARGB: ffffff00)
            ft.dropdown.Option("ffff00ff", text="Magenta"),  # Magenta (ARGB: ffff00ff)
            ft.dropdown.Option("ff00ffff", text="Cyan"),     # Cian (ARGB: ff00ffff)
        ],
        value="ff0000ff",  # Rojo por defecto (ARGB)
    )
    line_width_slider = ft.Slider(
        label="Line Width", min=1, max=10, divisions=9, value=2, width=200
    )  # Ancho de línea predeterminado: 2

    # Modificar las funciones para usar los valores seleccionados
    def generate_kml_file():
        if not longitude1.value or not latitude1.value or not longitude2.value or not latitude2.value or not line_length.value:
            show_error("Please fill in all fields to generate the KML file.")
            return

        if selected_folder.value == "No folder selected":
            show_error("Please select a folder to save the KML file.")
            return

        try:
            lon1 = float(longitude1.value)
            lat1 = float(latitude1.value)
            lon2 = float(longitude2.value)
            lat2 = float(latitude2.value)
            length = float(line_length.value)

            # Estilo personalizado
            line_color = line_color_dropdown.value  # Usar directamente el valor ARGB
            line_width = int(line_width_slider.value)

            # Guardar el archivo en la carpeta seleccionada
            filename = get_next_filename(selected_folder.value, "direccional", "kml")

            generate_kml(lon1, lat1, lon2, lat2, length, filename, line_color, line_width)
            print(f"KML file generated: {filename}")

            # Agregar a la lista de archivos recientes
            add_to_recent_files(filename)

            # Mostrar notificación de éxito
            show_snackbar(f"KML file generated: {filename}")

            # Open the KML file immediately after saving
            webbrowser.open(f"file://{filename}")

        except ValueError:
            show_error("Please enter valid numeric values for coordinates and length.")
        except Exception as e:
            show_error(f"Error generating KML file: {e}")

    def generate_circle_file():
        if not longitude1.value or not latitude1.value or not radius_dropdown.value:
            show_error("Please fill in all fields to generate the circle KML file.")
            return

        if selected_folder.value == "No folder selected":
            show_error("Please select a folder to save the KML file.")
            return

        try:
            # Use Point 1 coordinates as the center of the circle
            center_lon = float(longitude1.value)
            center_lat = float(latitude1.value)
            radius_km = float(radius_dropdown.value)

            # Estilo personalizado
            line_color = line_color_dropdown.value  # Usar directamente el valor ARGB
            line_width = int(line_width_slider.value)

            # Guardar el archivo en la carpeta seleccionada
            filename = get_next_filename(selected_folder.value, "circle", "kml")

            generate_circle_kml(center_lon, center_lat, radius_km, filename, line_color, line_width)
            print(f"Circle KML file generated: {filename}")

            # Agregar a la lista de archivos recientes
            add_to_recent_files(filename)

            # Mostrar notificación de éxito
            show_snackbar(f"Circle KML file generated: {filename}")

            # Open the KML file immediately after saving
            webbrowser.open(f"file://{filename}")

        except ValueError:
            show_error("Please enter valid numeric values for coordinates and radius.")
        except Exception as e:
            show_error(f"Error generating circle KML file: {e}")

    auto_button = ft.ElevatedButton(
        "Automatic Directional",
        on_click=lambda e: load_both_gps_and_generate(),
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE,  # Cambiar a ft.Colors
            color=ft.Colors.WHITE,  # Cambiar a ft.Colors
            padding=ft.Padding(20, 15, 20, 15),
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        width=300,
        height=60,
    )

    # Lista de archivos KML generados recientemente
    recent_files = []
    recent_files_list = ft.ListView(expand=True, spacing=10, padding=10)

    def update_recent_files():
        recent_files_list.controls.clear()
        for file in recent_files:
            recent_files_list.controls.append(
                ft.Row(
                    [
                        ft.Text(file, expand=True),
                        ft.IconButton(
                            icon=ft.icons.OPEN_IN_BROWSER,
                            tooltip="Open File",
                            on_click=lambda e, f=file: webbrowser.open(f"file://{f}"),
                        ),
                        ft.IconButton(
                            icon=ft.icons.DELETE,
                            tooltip="Delete File",
                            on_click=lambda e, f=file: delete_file(f),
                        ),
                    ],
                    alignment="spaceBetween",
                )
            )
        page.update()

    def delete_file(file):
        try:
            os.remove(file)
            recent_files.remove(file)
            update_recent_files()
            show_snackbar(f"File deleted: {file}")
        except Exception as e:
            show_error(f"Error deleting file: {e}")

    def add_to_recent_files(file):
        if file not in recent_files:
            recent_files.append(file)
            update_recent_files()

    # Carpeta seleccionada por el usuario
    selected_folder = ft.Text("No folder selected", size=14, color="gray")

    def select_folder_result(e: ft.FilePickerResultEvent):
        """
        Callback para manejar la selección de carpeta.
        """
        if e.path:
            selected_folder.value = e.path
        else:
            selected_folder.value = "No folder selected"
        page.update()

    # FilePicker para seleccionar la carpeta de destino
    folder_picker = ft.FilePicker(on_result=select_folder_result)
    page.overlay.append(folder_picker)

    # Add a Text component to display the compass angle
    global compass_angle_display
    compass_angle_display = ft.Text("N/A", size=16, weight="bold", color="blue", text_align="center")

    # Add a Container for the compass point
    global compass_point
    compass_point = ft.Container(
        width=15,  # Increased size of the point
        height=15,  # Increased size of the point
        bgcolor="red",  # Point color
        border_radius=7.5,  # Make it circular
        visible=False,  # Initially hidden
    )

    # Degree markings
    degree_markings = []
    for i in range(0, 360, 30):  # Add markings every 30 degrees
        angle_rad = math.radians(i)
        x = 150 + 130 * math.sin(angle_rad)  # Adjust radius for markings
        y = 150 - 130 * math.cos(angle_rad)
        degree_markings.append(
            ft.Text(
                str(i),
                size=12,  # Slightly larger text size
                weight="bold",
                left=x - 10,  # Center the text
                top=y - 10,
            )
        )

    # Compass graphic
    compass_graphic = ft.Container(
        width=300,  # Increased width
        height=300,  # Increased height
        content=ft.Stack(
            [
                ft.Container(width=300, height=300, bgcolor="lightgray", border_radius=150),  # Background circle
                *degree_markings,  # Add degree markings
                compass_point,  # Compass point
                ft.Container(
                    content=compass_angle_display,  # Place angle display in the center
                    alignment=ft.alignment.center,
                ),
            ]
        ),
    )

    # Layout
    page.add(
        ft.Column(
            [
                ft.Text("GPS KML Generator", size=24, weight="bold", text_align="center"),
                ft.Divider(),
                ft.Text("Select Folder to Save KML", size=18, weight="bold"),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Select Folder",
                            on_click=lambda e: folder_picker.get_directory_path(),
                        ),
                        selected_folder,
                    ],
                    alignment="spaceBetween",
                ),
                ft.Divider(),
                ft.Text("GPS Configuration", size=18, weight="bold"),
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Point 1", size=16, weight="bold"),
                                longitude1,
                                latitude1,
                                port_combo1,
                                baudrate_combo1,
                                ft.ElevatedButton(
                                    "Load GPS Point 1",
                                    on_click=lambda e: load_gps(1, lambda lon, lat: update_compass_display(page)),
                                ),
                                gps_status1,
                            ],
                            spacing=10,
                        ),
                        ft.Column(
                            [
                                ft.Text("Compass", size=16, weight="bold", text_align="center"),  # Centered text
                                compass_graphic,  # Add the compass graphic
                            ],
                            alignment="center",  # Center the column
                            horizontal_alignment="center",  # Center horizontally
                        ),
                        ft.Column(
                            [
                                ft.Text("Point 2", size=16, weight="bold"),
                                longitude2,
                                latitude2,
                                port_combo2,
                                baudrate_combo2,
                                ft.ElevatedButton(
                                    "Load GPS Point 2",
                                    on_click=lambda e: load_gps(2, lambda lon, lat: update_compass_display(page)),
                                ),
                                gps_status2,
                            ],
                            spacing=10,
                        ),
                    ],
                    alignment="spaceBetween",
                ),
                ft.Row(
                    [auto_button],  # Center the "Automatic Directional" button
                    alignment="center",
                ),
                ft.Row(
                    [error_display_1],  # Display the most recent error
                    alignment="center",
                ),
                ft.Row(
                    [error_display_2],  # Display the second most recent error
                    alignment="center",
                ),
                ft.Divider(),
                ft.Text("Line Configuration", size=18, weight="bold"),
                ft.Column(
                    [
                        line_length,
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Generate KML",
                                    on_click=lambda e: generate_kml_file(),
                                )
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Divider(),
                ft.Text("Circle Configuration", size=18, weight="bold"),
                ft.Row(
                    [radius_dropdown, ft.ElevatedButton(
                        "Generate Circle KML",
                        on_click=lambda e: generate_circle_file(),
                    )],
                    alignment="center",
                ),
                ft.Divider(),
                ft.Text("Advanced Configuration", size=18, weight="bold"),
                ft.Row([line_color_dropdown, line_width_slider], alignment="center"),
                ft.Divider(),
                ft.Text("Recent Files", size=18, weight="bold"),
                recent_files_list,
                ft.Divider(),
            ],
            spacing=20,
        )
    )

    # Add version display at the bottom-right corner
    version_text = ft.Text("Version 25.04.27", size=12, color="gray", text_align="right")  # Actualizar versión
    page.add(
        ft.Row(
            [version_text],
            alignment="end",  # Align to the bottom-right
            vertical_alignment="end",
        )
    )

if __name__ == "__main__":
    # Cambiar la vista a "flet_app" para una aplicación de escritorio
    ft.app(target=main, view="flet_app")
