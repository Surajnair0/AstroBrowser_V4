from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
import os
import base64
import re
import time
from analyze_fits import analyze_fits


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    cleanup_temporary_data()

    return render_template(
        "index.html"
    )

# =========================================================
# FITS UPLOAD + ANALYSIS
# =========================================================

# =========================================================
# CHUNKED FITS UPLOAD
# =========================================================

UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
MAX_UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024
UPLOAD_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
# =========================================================
# TEMPORARY DATA CLEANUP
# =========================================================

STALE_PART_MAX_AGE = 60 * 60  # 1 hour


def cleanup_temporary_data():
    """
    Remove temporary FITS files and generated analysis outputs.

    This application is intended to process data temporarily rather
    than act as a permanent data-storage service.
    """

    # -----------------------------------------------------
    # Remove uploaded FITS files and abandoned .part files
    # -----------------------------------------------------

    if os.path.exists(UPLOAD_FOLDER):

        for filename in os.listdir(UPLOAD_FOLDER):

            filepath = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            if not os.path.isfile(filepath):
                continue

            # Abandoned chunked uploads
            if filename.startswith(".") and filename.endswith(".part"):

                try:

                    file_age = (
                        time.time()
                        - os.path.getmtime(filepath)
                    )

                    if file_age > STALE_PART_MAX_AGE:

                        os.remove(filepath)

                        print(
                            f"Removed stale upload: {filename}"
                        )

                except OSError as e:

                    print(
                        f"Unable to remove stale upload {filename}: {e}"
                    )

                continue

            # Completed temporary FITS files
            if filename.lower().endswith(".fits"):

                try:

                    os.remove(filepath)

                    print(
                        f"Removed temporary FITS: {filename}"
                    )

                except OSError as e:

                    print(
                        f"Unable to remove temporary FITS {filename}: {e}"
                    )


    # -----------------------------------------------------
    # Remove generated analysis outputs
    # -----------------------------------------------------

    if os.path.exists(OUTPUT_FOLDER):

        for filename in os.listdir(OUTPUT_FOLDER):

            filepath = os.path.join(
                OUTPUT_FOLDER,
                filename
            )

            if not os.path.isfile(filepath):
                continue

            try:

                os.remove(filepath)

                print(
                    f"Removed temporary output: {filename}"
                )

            except OSError as e:

                print(
                    f"Unable to remove output {filename}: {e}"
                )

def validate_upload_metadata(upload_id, filename, chunk_index, total_chunks):

    if not upload_id or not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        return "Invalid upload identifier."

    filename = secure_filename(filename or "")

    if filename == "":
        return "Invalid file name."

    if not filename.lower().endswith(".fits"):
        return "Invalid file type. Please upload a .fits file."

    try:
        chunk_index = int(chunk_index)
        total_chunks = int(total_chunks)
    except (TypeError, ValueError):
        return "Invalid upload chunk information."

    if total_chunks < 1 or chunk_index < 0 or chunk_index >= total_chunks:
        return "Invalid upload chunk information."

    return None


@app.route("/upload-chunk", methods=["POST"])
def upload_chunk():

    upload_id = request.headers.get("X-Upload-ID", "")
    filename = request.headers.get("X-Filename", "")
    chunk_index = request.headers.get("X-Chunk-Index")
    total_chunks = request.headers.get("X-Total-Chunks")

    error = validate_upload_metadata(
        upload_id,
        filename,
        chunk_index,
        total_chunks
    )

    if error:
        return {"error": error}, 400

    filename = secure_filename(filename)
    chunk_index = int(chunk_index)
    total_chunks = int(total_chunks)

    try:
        expected_file_size = int(
            request.headers.get("X-File-Size", "0")
        )
    except ValueError:
        return {"error": "Invalid file size."}, 400

    if expected_file_size < 1:
        return {"error": "Invalid file size."}, 400

    content_length = request.content_length

    if content_length is not None and content_length > MAX_UPLOAD_CHUNK_SIZE:
        return {"error": "Upload chunk is too large."}, 413

    partial_path = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            f".{upload_id}.part"
        )
    )

    final_path = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    # -----------------------------------------------------
    # Write only this small chunk to disk.
    # The complete FITS file is never held in RAM by Flask.
    # -----------------------------------------------------

    if chunk_index == 0:
        file_mode = "wb"
    else:
        if not os.path.exists(partial_path):
            return {"error": "Upload session was not initialized."}, 400
        file_mode = "ab"

    try:

        bytes_written = 0

        with open(partial_path, file_mode) as destination:

            while True:

                chunk = request.stream.read(
                    min(
                        UPLOAD_CHUNK_SIZE,
                        1024 * 1024
                    )
                )

                if not chunk:
                    break

                destination.write(chunk)
                bytes_written += len(chunk)

                if bytes_written > MAX_UPLOAD_CHUNK_SIZE:
                    return {
                        "error": "Upload chunk is too large."
                    }, 413

    except Exception as e:

        print("Chunk upload error:")
        print(e)

        return {
            "error": "Unable to write upload chunk."
        }, 500

    if chunk_index < total_chunks - 1:

        return {
            "success": True,
            "complete": False,
            "chunk": chunk_index + 1
        }

    # -----------------------------------------------------
    # Final chunk: verify the assembled file, then move it
    # into the normal upload path. Scientific analysis is
    # performed by the separate analyze-upload request.
    # -----------------------------------------------------

    try:

        actual_file_size = os.path.getsize(
            partial_path
        )

        if actual_file_size != expected_file_size:

            os.remove(
                partial_path
            )

            return {
                "error": "Uploaded file size does not match the original file."
            }, 400

        os.replace(
            partial_path,
            final_path
        )

        print(
            f"Chunked FITS upload complete: {filename}"
        )

        return {
            "success": True,
            "complete": True
        }

    except Exception as e:

        print(
            "Upload finalization error:"
        )

        print(e)

        return {
            "error": "Unable to finalize the uploaded FITS file."
        }, 500


@app.route("/analyze-upload", methods=["GET"])
def analyze_upload():

    upload_id = request.args.get(
        "upload_id",
        ""
    )

    filename = secure_filename(
        request.args.get(
            "filename",
            ""
        )
    )

    error = validate_upload_metadata(
        upload_id,
        filename,
        "0",
        "1"
    )

    if error:
        return render_template(
            "error.html",
            error=error
        )

    filepath = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    if not os.path.exists(filepath):
        return render_template(
            "error.html",
            error="Uploaded FITS file is no longer available."
        )

    try:

        print(
            f"Running Python FITS analysis on: {filename}"
        )

        result = analyze_fits(
            filepath
        )

        print(
            "Analysis finished!"
        )

        results_path = os.path.join(
            OUTPUT_FOLDER,
            "results.txt"
        )

        with open(
            results_path,
            "r",
            encoding="utf-8"
        ) as f:

            results = f.read()

        return render_template(
            "results.html",
            results=results,
            filename=filename,
            result=result
        )

    except Exception as e:

        print(
            "Analysis error:"
        )

        print(e)

        return render_template(
            "error.html",
            error=str(e)
        )


# =========================================================
# OUTPUT FILES
# =========================================================

@app.route("/outputs/<filename>")
def output_file(filename):

    return send_from_directory(
        OUTPUT_FOLDER,
        filename
    )


# =========================================================
# DOWNLOAD HTML REPORT
# =========================================================

@app.route("/download")
def download():

    # -----------------------------------------------------
    # Get uploaded filename
    # -----------------------------------------------------

    filename = request.args.get(
        "file",
        "Uploaded FITS File"
    )

    # -----------------------------------------------------
    # Secure filename
    # -----------------------------------------------------

    filename = secure_filename(
        filename
    )

    if filename == "":

        filename = "Uploaded_FITS_File.fits"

    # -----------------------------------------------------
    # Read analysis results
    # -----------------------------------------------------

    results_path = os.path.join(
        OUTPUT_FOLDER,
        "results.txt"
    )

    if not os.path.exists(results_path):

        return render_template(
            "error.html",
            error="Analysis results are not available."
        )

    with open(
        results_path,
        "r",
        encoding="utf-8"
    ) as f:

        results = f.read()

    # -----------------------------------------------------
    # Convert images to Base64
    # -----------------------------------------------------

    def encode_image(path):

        if not os.path.exists(path):

            raise FileNotFoundError(
                f"Required image not found: {path}"
            )

        with open(
            path,
            "rb"
        ) as img:

            return base64.b64encode(
                img.read()
            ).decode("utf-8")

    try:

        raw_img = encode_image(
            os.path.join(
                OUTPUT_FOLDER,
                "raw.png"
            )
        )

        processed_img = encode_image(
            os.path.join(
                OUTPUT_FOLDER,
                "processed.png"
            )
        )

        histogram_img = encode_image(
            os.path.join(
                OUTPUT_FOLDER,
                "histogram.png"
            )
        )

    except Exception as e:

        return render_template(
            "error.html",
            error=str(e)
        )

    # -----------------------------------------------------
    # Create report filename
    # -----------------------------------------------------

    base_name = os.path.splitext(
        filename
    )[0]

    base_name = base_name.replace(
        " ",
        "_"
    )

    report_filename = (
        f"Analysis_Report_{base_name}.html"
    )

    # -----------------------------------------------------
    # Create standalone HTML report
    # -----------------------------------------------------

    html = f"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>AstroBrowser Analysis Report</title>


<style>

/* -----------------------------------------------------
   BASE
----------------------------------------------------- */

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 40px 20px;

    background: #080b10;

    color: rgba(255, 255, 255, 0.88);

    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        Helvetica,
        Arial,
        sans-serif;

    line-height: 1.6;
}}


/* -----------------------------------------------------
   MAIN CONTAINER
----------------------------------------------------- */

.container {{
    width: 100%;
    max-width: 1050px;
    margin: 0 auto;
}}


/* -----------------------------------------------------
   HEADER
----------------------------------------------------- */

.header {{
    padding-bottom: 30px;

    border-bottom:
        1px solid rgba(255, 255, 255, 0.08);
}}

.brand {{
    font-size: 12px;
    font-weight: 600;

    letter-spacing: 0.18em;

    color:
        rgba(255, 255, 255, 0.72);
}}

.brand-symbol {{
    margin-right: 8px;
}}

.report-label {{
    margin-top: 55px;

    font-size: 10px;
    font-weight: 600;

    letter-spacing: 0.18em;

    color:
        rgba(255, 255, 255, 0.38);
}}

h1 {{
    margin: 10px 0 8px;

    font-size: 34px;
    line-height: 1.15;

    font-weight: 500;

    letter-spacing: -0.03em;

    color:
        rgba(255, 255, 255, 0.96);
}}

.filename {{
    font-size: 13px;

    color:
        rgba(255, 255, 255, 0.42);

    overflow-wrap: anywhere;
}}


/* -----------------------------------------------------
   SECTIONS
----------------------------------------------------- */

.section {{
    margin-top: 42px;
}}

.section-heading {{
    display: flex;
    align-items: baseline;

    gap: 14px;

    margin-bottom: 20px;
}}

.section-number {{
    font-size: 11px;

    letter-spacing: 0.12em;

    color:
        rgba(255, 255, 255, 0.28);
}}

.section-title {{
    font-size: 12px;

    font-weight: 600;

    letter-spacing: 0.16em;

    color:
        rgba(255, 255, 255, 0.58);
}}


/* -----------------------------------------------------
   ANALYSIS RESULTS
----------------------------------------------------- */

.results-box {{
    padding: 24px;

    border:
        1px solid rgba(255, 255, 255, 0.08);

    background:
        rgba(255, 255, 255, 0.025);

    border-radius: 8px;
}}

pre {{
    margin: 0;

    font-family:
        "SFMono-Regular",
        Consolas,
        "Liberation Mono",
        monospace;

    font-size: 12px;

    line-height: 1.7;

    color:
        rgba(255, 255, 255, 0.70);

    white-space: pre-wrap;

    overflow-wrap: anywhere;
}}


/* -----------------------------------------------------
   SCIENTIFIC INTERPRETATION
----------------------------------------------------- */

.note {{
    padding: 24px;

    border:
        1px solid rgba(255, 255, 255, 0.08);

    background:
        rgba(255, 255, 255, 0.025);

    border-radius: 8px;
}}

.note-label {{
    margin-bottom: 12px;

    font-size: 10px;

    font-weight: 600;

    letter-spacing: 0.16em;

    color:
        rgba(255, 255, 255, 0.42);
}}

.note p {{
    margin: 0;

    max-width: 850px;

    font-size: 13px;

    line-height: 1.7;

    color:
        rgba(255, 255, 255, 0.62);
}}

.note strong {{
    color:
        rgba(255, 255, 255, 0.88);

    font-weight: 600;
}}


/* -----------------------------------------------------
   IMAGE SECTIONS
----------------------------------------------------- */

.image-block {{
    padding: 20px;

    border:
        1px solid rgba(255, 255, 255, 0.08);

    background:
        rgba(255, 255, 255, 0.025);

    border-radius: 8px;
}}

.image-title {{
    margin-bottom: 16px;

    font-size: 10px;

    font-weight: 600;

    letter-spacing: 0.14em;

    color:
        rgba(255, 255, 255, 0.42);
}}

img {{
    display: block;

    width: 100%;

    max-width: 850px;

    height: auto;

    margin: 0 auto;

    border-radius: 5px;

    border:
        1px solid rgba(255, 255, 255, 0.08);
}}


/* -----------------------------------------------------
   FOOTER
----------------------------------------------------- */

.footer {{
    margin-top: 60px;

    padding-top: 20px;

    border-top:
        1px solid rgba(255, 255, 255, 0.08);

    text-align: center;

    font-size: 10px;

    letter-spacing: 0.12em;

    color:
        rgba(255, 255, 255, 0.28);
}}


/* -----------------------------------------------------
   MOBILE
----------------------------------------------------- */

@media (max-width: 700px) {{

    body {{
        padding: 25px 14px;
    }}

    h1 {{
        font-size: 28px;
    }}

    .report-label {{
        margin-top: 35px;
    }}

    .section {{
        margin-top: 32px;
    }}

    .results-box,
    .note,
    .image-block {{
        padding: 18px;
    }}

}}

</style>

</head>


<body>

<div class="container">


    <!-- =================================================
         HEADER
    ================================================== -->

    <header class="header">

        <div class="brand">

            <span class="brand-symbol">
                ✦
            </span>

            ASTROBROWSER

        </div>


        <div class="report-label">

            ASTRONOMICAL IMAGE ANALYSIS REPORT

        </div>


        <h1>

            FITS Analysis Report

        </h1>


        <div class="filename">

            Analyzed file: {filename}

        </div>

    </header>



    <!-- =================================================
         01 — ANALYSIS RESULTS
    ================================================== -->

    <section class="section">

        <div class="section-heading">

            <span class="section-number">
                01
            </span>

            <span class="section-title">
                ANALYSIS RESULTS
            </span>

        </div>


        <div class="results-box">

            <pre>{results}</pre>

        </div>

    </section>



    <!-- =================================================
         02 — SCIENTIFIC INTERPRETATION
    ================================================== -->

    <section class="section">

        <div class="section-heading">

            <span class="section-number">
                02
            </span>

            <span class="section-title">
                SCIENTIFIC INTERPRETATION
            </span>

        </div>


        <div class="note">

            <div class="note-label">
                NOTE
            </div>


            <p>

                <strong>
                    UV emission is being used as a tracer of recent
                    star formation.
                </strong>

                The classification is based on the measured UV
                intensity and the number of detected bright regions.
                This is a heuristic classification intended to indicate
                the level of star-forming activity in the analyzed image.

            </p>

        </div>

    </section>



    <!-- =================================================
         03 — RAW IMAGE
    ================================================== -->

    <section class="section">

        <div class="section-heading">

            <span class="section-number">
                03
            </span>

            <span class="section-title">
                RAW FITS IMAGE
            </span>

        </div>


        <div class="image-block">

            <div class="image-title">

                ORIGINAL IMAGE DATA

            </div>


            <img
                src="data:image/png;base64,{raw_img}"
                alt="Raw FITS Image"
            >

        </div>

    </section>



    <!-- =================================================
         04 — PROCESSED IMAGE
    ================================================== -->

    <section class="section">

        <div class="section-heading">

            <span class="section-number">
                04
            </span>

            <span class="section-title">
                PROCESSED IMAGE
            </span>

        </div>


        <div class="image-block">

            <div class="image-title">

                NOISE REDUCED + HEAT MAP

            </div>


            <img
                src="data:image/png;base64,{processed_img}"
                alt="Processed FITS Image"
            >

        </div>

    </section>



    <!-- =================================================
         05 — INTENSITY HISTOGRAM
    ================================================== -->

    <section class="section">

        <div class="section-heading">

            <span class="section-number">
                05
            </span>

            <span class="section-title">
                INTENSITY HISTOGRAM
            </span>

        </div>


        <div class="image-block">

            <div class="image-title">

                UV INTENSITY DISTRIBUTION

            </div>


            <img
                src="data:image/png;base64,{histogram_img}"
                alt="UV Intensity Histogram"
            >

        </div>

    </section>



    <!-- =================================================
         FOOTER
    ================================================== -->

    <footer class="footer">

        ASTROBROWSER
        ·
        PYTHON-POWERED ASTRONOMICAL ANALYSIS

    </footer>


</div>

</body>

</html>
"""

    # -----------------------------------------------------
    # Save report
    # -----------------------------------------------------

    report_path = os.path.join(
        OUTPUT_FOLDER,
        report_filename
    )

    with open(
        report_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html)

    # -----------------------------------------------------
    # Send report to browser
    # -----------------------------------------------------

    return send_from_directory(
        OUTPUT_FOLDER,
        report_filename,
        as_attachment=True
    )


# =========================================================
# START FLASK SERVER
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5001
    )