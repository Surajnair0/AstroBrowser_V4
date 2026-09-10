from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
import os
import base64

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

    return render_template(
        "index.html"
    )


# =========================================================
# FITS UPLOAD + ANALYSIS
# =========================================================

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files.get("fitsfile")

    # -----------------------------------------------------
    # Check that a file was selected
    # -----------------------------------------------------

    if file is None or file.filename == "":

        return render_template(
            "error.html",
            error="No FITS file was selected."
        )

    # -----------------------------------------------------
    # Secure the filename
    # -----------------------------------------------------

    filename = secure_filename(
        file.filename
    )

    if filename == "":

        return render_template(
            "error.html",
            error="Invalid file name."
        )

    # -----------------------------------------------------
    # Check FITS extension
    # -----------------------------------------------------

    if not filename.lower().endswith(".fits"):

        return render_template(
            "error.html",
            error="Invalid file type. Please upload a .fits file."
        )

    # -----------------------------------------------------
    # Create safe file path
    # -----------------------------------------------------

    filepath = os.path.abspath(
        os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    # -----------------------------------------------------
    # Save uploaded FITS file
    # -----------------------------------------------------

    file.save(filepath)

    try:

        print(
            f"Running Python FITS analysis on: {filename}"
        )

        # =================================================
        # RUN PYTHON ANALYSIS
        # =================================================

        result = analyze_fits(
            filepath
        )

        print(
            "Analysis finished!"
        )

        # =================================================
        # READ RESULTS
        # =================================================

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

        # =================================================
        # DISPLAY RESULTS PAGE
        # =================================================

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