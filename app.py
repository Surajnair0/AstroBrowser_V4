from flask import Flask, render_template, request, send_from_directory, session
from werkzeug.utils import secure_filename
import os
import base64
import re
import time
import secrets
import shutil
from analyze_fits import analyze_fits


app = Flask(__name__)
app.secret_key = os.environ.get(
    "ASTROBROWSER_SECRET_KEY"
) or secrets.token_hex(32)
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
    delete_owned_analysis_data()
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
def get_owned_upload_ids():
    """
    Return the analysis IDs owned by this browser session.
    """

    upload_ids = session.get("upload_ids", [])

    if not isinstance(upload_ids, list):
        return []

    return [
        upload_id
        for upload_id in upload_ids
        if UPLOAD_ID_PATTERN.fullmatch(upload_id)
    ]


def register_upload(upload_id):
    """
    Register an upload ID as belonging to this browser session.
    """

    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        return False

    upload_ids = get_owned_upload_ids()

    if upload_id in upload_ids:
        return False

    upload_ids.append(upload_id)
    session["upload_ids"] = upload_ids
    session.modified = True

    return True


def owns_upload(upload_id):
    """
    Check whether this browser session owns the analysis.
    """

    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        return False

    return upload_id in get_owned_upload_ids()


def delete_owned_analysis_data():
    """
    Delete all temporary analysis data belonging to this browser session.
    """

    upload_ids = get_owned_upload_ids()

    for upload_id in upload_ids:

        upload_dir = os.path.abspath(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                upload_id
            )
        )

        output_dir = os.path.abspath(
            os.path.join(
                OUTPUT_FOLDER,
                upload_id
            )
        )

        if os.path.isdir(upload_dir):
            try:
                shutil.rmtree(upload_dir)
                print(
                    f"Removed session upload: {upload_id}"
                )
            except OSError as e:
                print(
                    f"Unable to remove session upload "
                    f"{upload_id}: {e}"
                )

        if os.path.isdir(output_dir):
            try:
                shutil.rmtree(output_dir)
                print(
                    f"Removed session output: {upload_id}"
                )
            except OSError as e:
                print(
                    f"Unable to remove session output "
                    f"{upload_id}: {e}"
                )

    session.pop("upload_ids", None)
    session.modified = True
# =========================================================
# TEMPORARY DATA CLEANUP
# =========================================================

STALE_PART_MAX_AGE = 60 * 60  # 1 hour


def touch_analysis_activity(upload_id):
    """
    Refresh the activity timestamp for an active analysis.
    """

    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        return

    current_time = time.time()

    for root in (UPLOAD_FOLDER, OUTPUT_FOLDER):

        analysis_dir = os.path.join(
            root,
            upload_id
        )

        if os.path.isdir(analysis_dir):

            try:

                os.utime(
                    analysis_dir,
                    (current_time, current_time)
                )

            except OSError as e:

                print(
                    f"Unable to refresh activity for {upload_id}: {e}"
                )


def cleanup_temporary_data():
    """
    Remove temporary FITS files and generated analysis outputs.

    Each analysis is isolated by its upload_id. Only analysis
    directories that have been inactive for longer than the stale
    threshold are removed.
    """

    import shutil

    current_time = time.time()

    # -----------------------------------------------------
    # Remove abandoned chunked uploads
    # -----------------------------------------------------

    if os.path.exists(UPLOAD_FOLDER):

        for filename in os.listdir(UPLOAD_FOLDER):

            filepath = os.path.join(
                UPLOAD_FOLDER,
                filename
            )

            # Analysis directories are handled separately below.
            if not os.path.isfile(filepath):
                continue

            if filename.startswith(".") and filename.endswith(".part"):

                try:

                    file_age = (
                        current_time
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

    # -----------------------------------------------------
    # Find stale analysis upload directories
    # -----------------------------------------------------

    stale_upload_ids = set()

    if os.path.exists(UPLOAD_FOLDER):

        for upload_id in os.listdir(UPLOAD_FOLDER):

            analysis_dir = os.path.join(
                UPLOAD_FOLDER,
                upload_id
            )

            if not os.path.isdir(analysis_dir):
                continue

            if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
                continue

            try:

                file_age = (
                    current_time
                    - os.path.getmtime(analysis_dir)
                )

                if file_age > STALE_PART_MAX_AGE:

                    shutil.rmtree(
                        analysis_dir
                    )

                    stale_upload_ids.add(
                        upload_id
                    )

                    print(
                        f"Removed stale analysis upload: {upload_id}"
                    )

            except OSError as e:

                print(
                    f"Unable to remove analysis upload {upload_id}: {e}"
                )

    # -----------------------------------------------------
    # Remove stale or orphaned analysis outputs
    # -----------------------------------------------------

    if os.path.exists(OUTPUT_FOLDER):

        for upload_id in os.listdir(OUTPUT_FOLDER):

            output_dir = os.path.join(
                OUTPUT_FOLDER,
                upload_id
            )

            if not os.path.isdir(output_dir):
                continue

            if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
                continue

            try:

                upload_dir = os.path.join(
                    UPLOAD_FOLDER,
                    upload_id
                )

                # Upload directory was already identified as stale.
                if upload_id in stale_upload_ids:

                    shutil.rmtree(
                        output_dir
                    )

                    print(
                        f"Removed stale analysis output: {upload_id}"
                    )

                    continue

                # Output directory has no corresponding upload.
                if not os.path.exists(upload_dir):

                    file_age = (
                        current_time
                        - os.path.getmtime(output_dir)
                    )

                    if file_age > STALE_PART_MAX_AGE:

                        shutil.rmtree(
                            output_dir
                        )

                        print(
                            f"Removed orphaned analysis output: {upload_id}"
                        )

            except OSError as e:

                print(
                    f"Unable to remove analysis output {upload_id}: {e}"
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

    # ---------------------------------------------------------
# VALIDATE UPLOAD SESSION OWNERSHIP
# ---------------------------------------------------------

    if owns_upload(upload_id):
    # This browser already owns the upload.
    # Allow retries, including a retry of chunk 0.
        pass

    elif chunk_index == 0:
    # First chunk creates/registers a new upload session.
        if not register_upload(upload_id):
            return {
                "error": "Unable to create upload session."
            }, 500

    else:
    # Chunks after chunk 0 must belong to an existing
    # upload session owned by this browser.
        return {
            "error": "This upload session is not available."
        }, 403

    # ---------------------------------------------------------
    # VALIDATE FILE SIZE
    # ---------------------------------------------------------

    try:
        expected_file_size = int(
            request.headers.get("X-File-Size", "0")
        )
    except ValueError:
        return {"error": "Invalid file size."}, 400

    if expected_file_size < 1:
        return {"error": "Invalid file size."}, 400

    content_length = request.content_length

    if (
        content_length is not None
        and content_length > MAX_UPLOAD_CHUNK_SIZE
    ):
        return {
            "error": "Upload chunk is too large."
        }, 413

    # -----------------------------------------------------
    # PRIVATE UPLOAD WORKSPACE
    # -----------------------------------------------------

    upload_dir = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            upload_id
        )
    )

    os.makedirs(
        upload_dir,
        exist_ok=True
    )

    partial_path = os.path.abspath(
        os.path.join(
            upload_dir,
            ".upload.part"
        )
    )

    final_path = os.path.abspath(
        os.path.join(
            upload_dir,
            filename
        )
    )

    # -----------------------------------------------------
    # SECURITY CHECK
    # -----------------------------------------------------

    if not partial_path.startswith(
        upload_dir + os.sep
    ) or not final_path.startswith(
        upload_dir + os.sep
    ):
        return {"error": "Invalid upload path."}, 400

    # -----------------------------------------------------
    # Write only this small chunk to disk.
    # The complete FITS file is never held in RAM by Flask.
    # -----------------------------------------------------

    if chunk_index == 0:
        file_mode = "wb"
    else:
        if not os.path.exists(partial_path):
            return {
                "error": "Upload session was not initialized."
            }, 400

        file_mode = "ab"

    try:

        bytes_written = 0

        with open(
            partial_path,
            file_mode
        ) as destination:

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

        print(
            "Chunk upload error:"
        )

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
    # into this upload's private workspace.
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
                "error": (
                    "Uploaded file size does not match "
                    "the original file."
                )
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

    # ---------------------------------------------------------
    # SESSION OWNERSHIP CHECK
    # ---------------------------------------------------------

    if not owns_upload(upload_id):
        return render_template(
            "error.html",
            error="This analysis session is not available."
        ), 403

    # ---------------------------------------------------------
    # PRIVATE ANALYSIS WORKSPACE
    # ---------------------------------------------------------

    analysis_dir = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            upload_id
        )
    )

    filepath = os.path.abspath(
        os.path.join(
            analysis_dir,
            filename
        )
    )

    # ---------------------------------------------------------
    # SECURITY CHECK
    # ---------------------------------------------------------

    if not filepath.startswith(
        analysis_dir + os.sep
    ):
        return render_template(
            "error.html",
            error="Invalid upload path."
        )

    if not os.path.isfile(filepath):
        return render_template(
            "error.html",
            error="Uploaded FITS file is no longer available."
        )

    # ---------------------------------------------------------
    # PRIVATE OUTPUT DIRECTORY
    # ---------------------------------------------------------

    output_dir = os.path.abspath(
        os.path.join(
            OUTPUT_FOLDER,
            upload_id
        )
    )

    touch_analysis_activity(upload_id)

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    try:

        print(
            f"Running Python FITS analysis on: {filename}"
        )

        result = analyze_fits(
            filepath,
            output_dir
        )

        print(
            "Analysis finished!"
        )

        results_path = os.path.join(
            output_dir,
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
            result=result,
            upload_id=upload_id
        )

    except Exception as e:

        print(
            "Analysis error:"
        )

        print(e)

        return render_template(
            "error.html",
            error=str(e)
        ), 500


# =========================================================
# OUTPUT FILES
# =========================================================

@app.route("/outputs/<upload_id>/<filename>")
def output_file(upload_id, filename):

    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):

        return render_template(
            "error.html",
            error="Invalid analysis identifier."
        ), 400

    # ---------------------------------------------------------
    # SESSION OWNERSHIP CHECK
    # ---------------------------------------------------------

    if not owns_upload(upload_id):

        return render_template(
            "error.html",
            error="This analysis session is not available."
        ), 403

    safe_filename = secure_filename(filename)

    if safe_filename != filename:

        return render_template(
            "error.html",
            error="Invalid output file."
        ), 400

    output_dir = os.path.abspath(
        os.path.join(
            OUTPUT_FOLDER,
            upload_id
        )
    )

    output_path = os.path.abspath(
        os.path.join(
            output_dir,
            safe_filename
        )
    )

    if not output_path.startswith(
        output_dir + os.sep
    ):

        return render_template(
            "error.html",
            error="Invalid output path."
        ), 400

    if not os.path.isfile(output_path):

        return render_template(
            "error.html",
            error="Requested analysis output is no longer available."
        ), 404

    touch_analysis_activity(upload_id)

    return send_from_directory(
        output_dir,
        safe_filename
    )


# =========================================================
# DOWNLOAD HTML REPORT
# =========================================================

@app.route("/download")
def download():

    # -----------------------------------------------------
    # Get analysis identifier
    # -----------------------------------------------------

    upload_id = request.args.get(
        "upload_id",
        ""
    )

    # -----------------------------------------------------
    # Validate analysis identifier
    # -----------------------------------------------------

    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):

        return render_template(
            "error.html",
            error="Invalid analysis identifier."
        ), 400

    # -----------------------------------------------------
    # SESSION OWNERSHIP CHECK
    # -----------------------------------------------------

    if not owns_upload(upload_id):

        return render_template(
            "error.html",
            error="This analysis session is not available."
        ), 403

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
    # Analysis-specific output directory
    # -----------------------------------------------------

    output_dir = os.path.abspath(
        os.path.join(
            OUTPUT_FOLDER,
            upload_id
        )
    )

    # -----------------------------------------------------
    # Read analysis results
    # -----------------------------------------------------

    results_path = os.path.join(
        output_dir,
        "results.txt"
    )

    if not os.path.exists(results_path):

        return render_template(
            "error.html",
            error="Analysis results are not available."
        )

    touch_analysis_activity(upload_id)

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
                output_dir,
                "raw.png"
            )
        )

        processed_img = encode_image(
            os.path.join(
                output_dir,
                "processed.png"
            )
        )

        histogram_img = encode_image(
            os.path.join(
                output_dir,
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
        output_dir,
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
        output_dir,
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