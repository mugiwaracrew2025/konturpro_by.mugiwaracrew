# app.py
from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import numpy as np
import matplotlib
# Set the Matplotlib backend to 'Agg' for non-GUI environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import io
import ezdxf  # Library for AutoCAD (DXF) files
import base64
import os
import datetime
import uuid # For generating unique filenames
import traceback # To print detailed error information

app = Flask(__name__)
# A secret key for session management. Replace with a strong, random key in production.
app.secret_key = 'kunci_super_rahasia_dan_aman_yang_sangat_panjang_dan_unik'

# Ensure a temporary directory exists for storing images
TEMP_FOLDER = os.path.join('static', 'temp')
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

# --- Main Application Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/history')
def show_history():
    history_data = session.get('contour_history', [])
    return render_template('history.html', history=history_data)

# --- API Endpoint for Data Processing ---

@app.route('/generate_contour', methods=['POST'])
def generate_contour():
    try:
        data_source = request.form.get('data_source')
        
        if data_source == 'excel':
            file = request.files.get('excel_file')
            if not file or file.filename == '':
                return jsonify({"success": False, "error": "Tidak ada file yang diunggah."}), 400
            
            try:
                df = pd.read_excel(file)
            except Exception:
                return jsonify({"success": False, "error": "Gagal membaca file. Pastikan itu file Excel yang valid."}), 400
            
            if not all(col in df.columns for col in ['X', 'Y', 'Z']):
                return jsonify({"success": False, "error": "File Excel harus memiliki kolom 'X', 'Y', dan 'Z'."}), 400
            
            x, y, z = df["X"].values, df["Y"].values, df["Z"].values

        elif data_source == 'manual':
            manual_data = request.form.get('manual_data')
            if not manual_data:
                return jsonify({"success": False, "error": "Data manual tidak boleh kosong."}), 400
            
            rows = manual_data.strip().split('\n')
            data_list = []
            for row in rows:
                try:
                    parts = row.strip().split(',')
                    if len(parts) == 3:
                        data_list.append([float(p.strip()) for p in parts])
                except ValueError:
                    continue
            
            if not data_list:
                return jsonify({"success": False, "error": "Format data manual tidak valid. Gunakan: X,Y,Z per baris."}), 400
            
            df = pd.DataFrame(data_list, columns=['X', 'Y', 'Z'])
            x, y, z = df["X"].values, df["Y"].values, df["Z"].values
        else:
            return jsonify({"success": False, "error": "Sumber data tidak valid."}), 400
        
        try:
            interval = float(request.form.get('interval', 1))
            fig_w = float(request.form.get('fig_w', 10))
            fig_h = float(request.form.get('fig_h', 8))
        except ValueError:
            return jsonify({"success": False, "error": "Input interval, lebar, atau tinggi harus berupa angka."}), 400
        
        # --- Tambahkan validasi input yang lebih ketat ---
        if interval <= 0 or fig_w <= 0 or fig_h <= 0:
            return jsonify({"success": False, "error": "Interval, lebar, dan tinggi harus lebih dari 0."}), 400
        
        if len(x) < 4:
            return jsonify({"success": False, "error": "Diperlukan minimal 4 titik data untuk interpolasi kontur."}), 400

        # --- Validasi Data Tambahan ---
        if len(np.unique(z)) < 2:
            return jsonify({"success": False, "error": "Data elevasi (Z) tidak bervariasi. Kontur tidak dapat dibuat."}), 400
        
        if len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
            return jsonify({"success": False, "error": "Semua titik data memiliki koordinat X atau Y yang sama. Tidak dapat membentuk grid."}), 400

        # --- Part 1: Grid Data Interpolation ---
        grid_x, grid_y = np.meshgrid(
            np.linspace(x.min(), x.max(), 200),
            np.linspace(y.min(), y.max(), 200)
        )
        grid_z = griddata((x, y), z, (grid_x, grid_y), method='cubic')
        
        # --- Part 2: Create Contour Plot (PNG) ---
        plt.figure(figsize=(fig_w, fig_h))
        levels = np.arange(np.nanmin(grid_z), np.nanmax(grid_z) + interval, interval)
        
        if len(levels) == 0:
            return jsonify({"success": False, "error": "Tidak ada level kontur yang valid. Periksa data elevasi atau interval."}), 400
        
        contours = plt.contour(
            grid_x, grid_y, grid_z,
            levels=levels,
            cmap='terrain'
        )
        plt.clabel(contours, inline=True, fontsize=8)
        plt.scatter(x, y, c=z, cmap='terrain', s=10, edgecolor='k')
        plt.colorbar(label="Elevasi (m)")
        plt.title(f"Peta Kontur (Interval {interval} m)")
        plt.xlabel("Koordinat X")
        plt.ylabel("Koordinat Y")

        # Create PNG image and save to temporary file
        img_filename = f"{uuid.uuid4()}.png"
        img_path = os.path.join(TEMP_FOLDER, img_filename)
        plt.savefig(img_path, format='png', bbox_inches='tight')
        plt.close()

        # Read the image file and encode to Base64 for a one-time display
        with open(img_path, 'rb') as img_file:
            encoded_png = base64.b64encode(img_file.read()).decode('utf-8')

        # --- Part 3: Create AutoCAD (DXF) File ---
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        
        for i, segments_at_level in enumerate(contours.allsegs):
            level = contours.levels[i]
            layer_name = f'Kontur_{level:.2f}'.replace('.', '_').replace('-', 'm')
            
            if layer_name not in doc.layers:
                doc.layers.new(name=layer_name, dxfattribs={'color': 7})

            for segment in segments_at_level:
                points = [(v[0], v[1]) for v in segment]
                if len(points) >= 2:
                    msp.add_lwpolyline(points, dxfattribs={'layer': layer_name})

        # SOLUSI BARU: Tulis ke buffer teks, lalu encode ke bytes
        dxf_text_buffer = io.StringIO()
        doc.write(dxf_text_buffer)
        dxf_text_buffer.seek(0)
        dxf_bytes = dxf_text_buffer.getvalue().encode('utf-8')
        encoded_dxf = base64.b64encode(dxf_bytes).decode('utf-8')

        # Save data to session history, storing only the filename
        history_entry = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'interval': interval,
            'source': data_source,
            'image_url': f"/static/temp/{img_filename}"
        }
        if 'contour_history' not in session:
            session['contour_history'] = []
        # Tambahkan data baru di awal daftar agar yang terbaru selalu di atas
        session['contour_history'].insert(0, history_entry)
        
        # Keep history list limited to 10 entries to prevent growth
        while len(session.get('contour_history', [])) > 10:
            # Delete old image file
            oldest_entry = session['contour_history'].pop()
            old_filename = oldest_entry['image_url'].split('/')[-1]
            old_path = os.path.join(TEMP_FOLDER, old_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
                
        response_data = {
            "success": True,
            "image_url": 'data:image/png;base64,' + encoded_png, # Still send Base64 for immediate display
            "dxf_url": 'data:application/octet-stream;base64,' + encoded_dxf,
        }
        return jsonify(response_data)

    except Exception as e:
        print(f"Error occurred: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": f"Terjadi kesalahan pada server. Detail: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)