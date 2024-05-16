from flask import Flask, render_template, request, redirect, send_file, abort
import folium
import sqlite3
import subprocess
from pyproj import Transformer
import urllib.parse
import os

app = Flask(__name__)

# Function to fetch path from the database using dataID
def get_path(dataID):
    connection = sqlite3.connect('dronedb.db')
    cursor = connection.cursor()

    # Fetch path using dataID
    cursor.execute("SELECT path FROM pointclouds WHERE dataID=?", (dataID,))
    result = cursor.fetchone()
    connection.close()
    return result[0] if result else None

# Function to handle subprocess execution for lasinfo
def run_lasinfo(path):
    try:
        # Run the las
        # info subprocess
        subprocess.run(['lasinfo', '-i', path, '-repair_bb'], check=True)
    except subprocess.CalledProcessError as e:
        return str(e)

# Function to handle subprocess execution for PotreeConverter
def run_potree_converter(path):
    try:
        # Run the PotreeConverter subprocess
        subprocess.run(['PotreeConverter.exe', path, '-o', 'C:\\Users\\PC53\\Documents\\gwp_pointcloud_test\\gwp_pointcloud_test\\gwp_drone_node\\public\\pointclouds\\temp', '--generate-page', 'temp'], check=True)
    except subprocess.CalledProcessError as e:
        return str(e)

# Route to handle the popup click event
@app.route('/process_pointcloud/<int:dataID>', methods=['GET'])
def process_pointcloud(dataID):
    # Get the path from the database using dataID
    path = get_path(dataID)
    print(path)
    if not path:
        return "Error: Path not found in database"

    # Call the function to run lasinfo
    lasinfo_result = run_lasinfo(path)
    if lasinfo_result:
        return lasinfo_result

    # Call the function to run PotreeConverter
    potree_converter_result = run_potree_converter(path)
    if potree_converter_result:
        return potree_converter_result

    # Return the URL after the subprocesses are done
    return redirect("https://192.168.16.41:3000/pointclouds/temp/temp.html")

# Function to fetch data from the database
def get_data():
    connection = sqlite3.connect('dronedb.db')
    cursor = connection.cursor()

    # Fetch sites data
    cursor.execute("SELECT * FROM sites")
    sites = cursor.fetchall()

    # Fetch point clouds data
    cursor.execute("SELECT * FROM pointclouds")
    pointclouds = cursor.fetchall()

    # Fetch DSM data
    cursor.execute("SELECT * FROM dsm")
    dsms = cursor.fetchall()

    # Fetch Ortho data
    cursor.execute("SELECT * FROM ortho")
    orthos = cursor.fetchall()

    connection.close()
    return sites, pointclouds, dsms, orthos

@app.route('/')
def map():
    sites, pointclouds, dsms, orthos = get_data()

    # Create map centered on a default location
    my_map = folium.Map(location=[54.7023545, -3.2765753], zoom_start=6)

    # Initialize transformer to convert from EPSG:27700 to EPSG:4326
    transformer = Transformer.from_crs("epsg:27700", "epsg:4326", always_xy=True)

    # Add markers for each site
    for site in sites:
        site_id = site[0]
        site_name = site[1]
        centroid = site[4].split(',')
        
        try:
            easting = float(centroid[0].strip())
            northing = float(centroid[1].strip())
        
            # Convert coordinates
            lon, lat = transformer.transform(easting, northing)

            # Create a marker for the site
            marker = folium.Marker([lat, lon], popup=site_name)

            # Create a tooltip with the site name
            tooltip = folium.Tooltip(site_name)

            # Add the tooltip to the marker
            marker.add_child(tooltip)

            # Create a popup with available point cloud, DSM, and Ortho dates and dataIDs
            popup_content = f"""
                <div class='popup-content' style='font-family: Arial, sans-serif; font-size: 1.5vh; width: 15vw; height: 42vh; overflow-y: scroll; display: flex; align-items: center; justify-content: center; flex-direction: column;'>
                    <b style='font-size: 2vh;'>{site_name}</b><br><ul>
                """
            
            # Ortho
            popup_content += "<div style='margin-top: 3vh; height: 9vh; width: 12vw; overflow-y: scroll;'><b>Ortho:</b><br><ul>"
            for ortho in orthos:
                if ortho[1] == site_id:  # Check if the siteID matches
                    date = ortho[3]
                    ortho_path = urllib.parse.quote(ortho[2])  # Encode the file path
                    popup_content += f"<li><a href='/download_file/{ortho_path}'>{date}</a></li>"
            popup_content += "</ul></div>"

            # Point Clouds
            popup_content += "<div style='margin-top: 3vh; height: 9vh; width: 12vw; overflow-y: scroll;'><b>Point Clouds:</b><br><ul>"
            for pointcloud in pointclouds:
                if pointcloud[1] == site_id:  # Check if the siteID matches
                    date = pointcloud[3]
                    dataID = pointcloud[0]
                    popup_content += f"<li><a href='/process_pointcloud/{dataID}' onclick='showModal()'>{date}</a></li>"
            popup_content += "</ul></div>"

            # DSM
            popup_content += "<div style='margin-top: 3vh; height: 9vh; width: 12vw; overflow-y: scroll;'><b>DSM:</b><br><ul>"
            for dsm in dsms:
                if dsm[1] == site_id:  # Check if the siteID matches
                    date = dsm[3]
                    dsm_path = urllib.parse.quote(dsm[2])  # Encode the file path
                    popup_content += f"<li><a href='/download_file/{dsm_path}'>{date}</a></li>"
            popup_content += "</ul></div>"

            # Add the popup to the marker
            marker.add_child(folium.Popup(popup_content))

            # Add the marker to the map
            my_map.add_child(marker)
        
        except ValueError as e:
            print(f"Error converting centroid coordinates for site {site_name}: {e}")

    map_html = my_map._repr_html_()
    return render_template('map.html', map_html=map_html)


@app.route('/download_file/<path:file_path>')
def download_file(file_path):
    # Ensure the requested file path is within the allowed directory
    allowed_directory = "D:\\1-UAV Surveys"  # Specify the root directory where the files are located
    full_file_path = os.path.abspath(os.path.join(allowed_directory, file_path))
    
    # Check if the requested file path is within the allowed directory
    if not os.path.abspath(full_file_path).startswith(allowed_directory):
        # Abort the request with a 403 Forbidden status
        abort(403)

    # Check if the file exists
    if not os.path.exists(full_file_path):
        # Return a 404 Not Found error
        abort(404)

    # Return the file to the user for download
    return send_file(full_file_path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
