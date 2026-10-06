"use strict";


/* =========================================================
   ASTRO LABORATORY RESULTS PAGE
   ========================================================= */


/*
 * Render backend URL.
 */

const API_BASE_URL =
    "https://astro-laboratory.onrender.com";


/*
 * Read analysis data from sessionStorage.
 */

const storedAnalysis =
    sessionStorage.getItem("astroBrowserAnalysis");


/*
 * Stop if analysis data does not exist.
 */

if (!storedAnalysis) {

    document.body.innerHTML = `
        <div style="
            padding: 40px;
            font-family: sans-serif;
            text-align: center;
        ">
            <h2>Analysis data not found</h2>
            <p>
                Please upload and analyze a FITS file again.
            </p>
            <a href="/">
                Return to Astro Laboratory
            </a>
        </div>
    `;

    throw new Error(
        "Astro Laboratory analysis data was not found in sessionStorage."
    );
}


/*
 * Parse the stored API response.
 */

let data;

try {

    data =
        JSON.parse(storedAnalysis);

} catch (error) {

    console.error(
        "Failed to parse Astro Laboratory analysis data:",
        error
    );

    throw new Error(
        "Invalid Astro Laboratory analysis data."
    );
}


/*
 * Basic API validation.
 */

if (
    !data ||
    !data.success ||
    !data.result ||
    !data.outputs
) {

    console.error(
        "Invalid analysis response:",
        data
    );

    throw new Error(
        "The analysis response is incomplete."
    );
}


/* =========================================================
   HELPER FUNCTIONS
   ========================================================= */


/*
 * Convert a backend-relative output URL
 * into a complete Render URL.
 */

function backendUrl(url) {

    if (!url) {
        return "";
    }

    if (
        url.startsWith("http://") ||
        url.startsWith("https://")
    ) {
        return url;
    }

    return (
        API_BASE_URL +
        (
            url.startsWith("/")
                ? url
                : "/" + url
        )
    );
}


/*
 * Safely display a value in an element.
 */

function setText(id, value) {

    const element =
        document.getElementById(id);

    if (!element) {
        return;
    }

    if (
        value === undefined ||
        value === null ||
        value === ""
    ) {

        element.textContent =
            "Not available";

        return;
    }

    element.textContent =
        String(value);
}


/*
 * Format a number to a fixed number of decimal places.
 */

function formatNumber(value, decimals) {

    const number =
        Number(value);

    if (!Number.isFinite(number)) {

        return "Not available";

    }

    return number.toFixed(decimals);
}


/*
 * Set an output link.
 */

function setOutputLink(id, url) {

    const link =
        document.getElementById(id);

    if (!link) {
        return;
    }

    const fullUrl =
        backendUrl(url);

    if (!fullUrl) {

        link.removeAttribute("href");

        return;

    }

    link.href =
        fullUrl;
}


/* =========================================================
   RESULT DATA
   ========================================================= */

const result =
    data.result;


/* =========================================================
   SECTION 01 — SCIENTIFIC RESULTS
   ========================================================= */

setText(
    "num-regions",
    result.num_regions
);

setText(
    "uv-intensity",
    formatNumber(
        result.uv_intensity,
        6
    )
);

setText(
    "intensity-variation",
    formatNumber(
        result.intensity_variation,
        5
    )
);

setText(
    "classification",
    result.category
);


/* =========================================================
   SECTION 03 — FITS METADATA
   ========================================================= */

const metadata =
    result.metadata || {};


setText(
    "metadata-dimensions",
    metadata.dimensions
);

setText(
    "metadata-dimension-type",
    metadata.dimension_type
);

setText(
    "metadata-analysis-plane",
    metadata.analysis_plane
);

setText(
    "metadata-data-type",
    metadata.data_type
);

setText(
    "metadata-instrument",
    metadata.instrument
);

setText(
    "metadata-filter",
    metadata.filter
);

setText(
    "metadata-exposure",
    metadata.exposure_time
);

setText(
    "metadata-observation-date",
    metadata.observation_date
);

setText(
    "metadata-telescope",
    metadata.telescope
);

setText(
    "metadata-object",
    metadata.object
);


/* =========================================================
   SECTION 04 — IMAGE STATISTICS
   ========================================================= */

setText(
    "stat-background",
    result.background
);

setText(
    "stat-threshold",
    result.threshold
);

setText(
    "stat-num-regions",
    result.num_regions
);

setText(
    "stat-uv-intensity",
    formatNumber(
        result.uv_intensity,
        6
    )
);

setText(
    "stat-intensity-variation",
    formatNumber(
        result.intensity_variation,
        5
    )
);


/* =========================================================
   SECTION 05 — VISUAL ANALYSIS
   ========================================================= */

const outputs =
    data.outputs;


const rawImage =
    document.getElementById(
        "raw-image"
    );

const processedImage =
    document.getElementById(
        "processed-image"
    );

const histogramImage =
    document.getElementById(
        "histogram-image"
    );


if (rawImage) {

    rawImage.src =
        backendUrl(
            outputs.raw
        );

}


if (processedImage) {

    processedImage.src =
        backendUrl(
            outputs.processed
        );

}


if (histogramImage) {

    histogramImage.src =
        backendUrl(
            outputs.histogram
        );

}


/* =========================================================
   SECTION 07 — TECHNICAL OUTPUT
   ========================================================= */

setOutputLink(
    "output-raw",
    outputs.raw
);

setOutputLink(
    "output-processed",
    outputs.processed
);

setOutputLink(
    "output-histogram",
    outputs.histogram
);

setOutputLink(
    "output-results",
    outputs.results
);


/*
 * Set the HTML report download link.
 */

const downloadReport =
    document.getElementById(
        "download-report"
    );


if (downloadReport) {

    downloadReport.href =
        `${API_BASE_URL}/download?upload_id=${encodeURIComponent(data.upload_id)}&file=${encodeURIComponent(data.filename)}`;

}


/* =========================================================
   IMAGE TAB HANDLING
   ========================================================= */

const imageTabs =
    document.querySelectorAll(
        ".image-tab"
    );

const imageContainers =
    document.querySelectorAll(
        ".image-container"
    );


function activateImageTab(type) {

    imageContainers.forEach(
        function(container) {

            container.classList.remove(
                "active"
            );

        }
    );


    imageTabs.forEach(
        function(tab) {

            tab.classList.remove(
                "active"
            );

        }
    );


    const selectedContainer =
        document.getElementById(
            "image-" + type
        );


    const selectedTab =
        document.querySelector(
            `.image-tab[data-image-type="${type}"]`
        );


    if (selectedContainer) {

        selectedContainer.classList.add(
            "active"
        );

    }


    if (selectedTab) {

        selectedTab.classList.add(
            "active"
        );

    }

}


imageTabs.forEach(
    function(tab) {

        tab.addEventListener(
            "click",
            function() {

                const type =
                    tab.dataset.imageType;

                if (!type) {
                    return;
                }

                activateImageTab(
                    type
                );

            }
        );

    }
);


/*
 * Show RAW image by default.
 */

activateImageTab(
    "raw"
);


/* =========================================================
   DEBUG INFORMATION
   ========================================================= */

console.log(
    "Astro Laboratory results page loaded:",
    data
);