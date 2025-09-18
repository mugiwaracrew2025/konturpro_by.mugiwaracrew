// static/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('contourForm');
    const resultsSection = document.getElementById('results');
    const loadingSpinner = document.getElementById('loading');
    const contourImage = document.getElementById('contour_image');
    const downloadPngBtn = document.getElementById('download_png');
    const downloadDxfBtn = document.getElementById('download_dxf');
    const dataSourceSelect = document.getElementById('data_source');
    const excelUploadDiv = document.getElementById('excel_upload');
    const manualInputDiv = document.getElementById('manual_input');

    // Show/hide input fields based on data source selection
    dataSourceSelect.addEventListener('change', (event) => {
        if (event.target.value === 'excel') {
            excelUploadDiv.style.display = 'block';
            manualInputDiv.style.display = 'none';
        } else {
            excelUploadDiv.style.display = 'none';
            manualInputDiv.style.display = 'block';
        }
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Show loading spinner and hide previous results
        resultsSection.style.display = 'block';
        loadingSpinner.style.display = 'block';
        contourImage.style.display = 'none';
        downloadPngBtn.style.display = 'none';
        downloadDxfBtn.style.display = 'none';
        
        const formData = new FormData(form);

        try {
            const response = await fetch('/generate_contour', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // Show the generated contour image
                contourImage.src = result.image_url;
                contourImage.style.display = 'block';
                
                // Show download links
                downloadPngBtn.href = result.image_url;
                downloadPngBtn.style.display = 'inline-block';
                
                downloadDxfBtn.href = result.dxf_url;
                downloadDxfBtn.style.display = 'inline-block';
            } else {
                alert('Gagal memproses data. ' + result.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Terjadi kesalahan. Silakan coba lagi.');
        } finally {
            // Hide the loading spinner
            loadingSpinner.style.display = 'none';
        }
    });
});