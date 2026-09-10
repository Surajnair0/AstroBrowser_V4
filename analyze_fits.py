import os
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from astropy.io import fits
from scipy.ndimage import median_filter, label
from skimage.filters import threshold_otsu


# =============================================================
# FITS VALIDATION
# =============================================================

def validate_fits_file(fits_file):
    """
    Validate that the supplied file is a usable astronomical
    image FITS file for the AstroBrowser analysis pipeline.
    """

    # ---------------------------------------------------------
    # CHECK FILE EXISTS
    # ---------------------------------------------------------

    if not os.path.isfile(fits_file):
        raise ValueError(
            "The uploaded FITS file could not be found."
        )

    # ---------------------------------------------------------
    # CHECK FILE EXTENSION
    # ---------------------------------------------------------

    if not fits_file.lower().endswith(".fits"):
        raise ValueError(
            "Invalid file type. Please upload a FITS file "
            "with a .fits extension."
        )

    # ---------------------------------------------------------
    # CHECK FILE IS NOT EMPTY
    # ---------------------------------------------------------

    if os.path.getsize(fits_file) == 0:
        raise ValueError(
            "The uploaded FITS file is empty."
        )

    # ---------------------------------------------------------
    # OPEN AND VALIDATE FITS
    # ---------------------------------------------------------

    try:

        with fits.open(
            fits_file,
            mode="readonly",
            memmap=False
        ) as hdul:

            # FITS must contain at least one HDU
            if len(hdul) == 0:
                raise ValueError(
                    "The FITS file contains no HDUs."
                )

            primary_hdu = hdul[0]
            img = primary_hdu.data

            # Primary HDU must contain image data
            if img is None:
                raise ValueError(
                    "This FITS file does not contain an image in "
                    "the Primary HDU. Please upload an image FITS "
                    "(Level-2 image), not an event table."
                )

            # Image must contain data
            if img.size == 0:
                raise ValueError(
                    "The FITS image contains no data."
                )

            # Only 2D images and 3D cubes are supported
            if img.ndim not in (2, 3):
                raise ValueError(
                    f"Unsupported FITS image dimensions: {img.ndim}D. "
                    "AstroBrowser supports 2D images and 3D image cubes."
                )

            # Pixel data must be numeric
            if not np.issubdtype(img.dtype, np.number):
                raise ValueError(
                    "The FITS image does not contain numeric pixel data."
                )

            # Check for valid finite pixels
            finite_pixels = np.isfinite(img)

            if not np.any(finite_pixels):
                raise ValueError(
                    "The FITS image contains no valid finite pixel values."
                )

            valid_pixels = img[finite_pixels]

            # Reject completely zero images
            if np.all(valid_pixels == 0):
                raise ValueError(
                    "The FITS image contains no detectable signal. "
                    "All valid pixels are zero."
                )

    except ValueError:
        raise

    except Exception as e:

        print(f"FITS validation error: {e}")

        raise ValueError(
            "The uploaded file could not be read as a valid FITS image. "
            "Please make sure you are uploading a valid astronomical FITS image."
        )

    return True


# =============================================================
# METADATA FORMATTING
# =============================================================

def format_data_type(dtype):
    """
    Convert a NumPy/FITS dtype into a scientist-friendly
    description while preserving the original meaning.
    """

    # Normalize FITS byte order such as >f4
    # so that it correctly matches NumPy float32.
    dtype = np.dtype(dtype).newbyteorder("=")

    if dtype == np.dtype("float32"):
        return "32-bit floating point"

    if dtype == np.dtype("float64"):
        return "64-bit floating point"

    if dtype == np.dtype("int8"):
        return "8-bit integer"

    if dtype == np.dtype("uint8"):
        return "8-bit unsigned integer"

    if dtype == np.dtype("int16"):
        return "16-bit integer"

    if dtype == np.dtype("uint16"):
        return "16-bit unsigned integer"

    if dtype == np.dtype("int32"):
        return "32-bit integer"

    if dtype == np.dtype("uint32"):
        return "32-bit unsigned integer"

    if dtype == np.dtype("int64"):
        return "64-bit integer"

    if dtype == np.dtype("uint64"):
        return "64-bit unsigned integer"

    return str(dtype)


def format_observation_date(value):
    """
    Convert a FITS DATE-OBS value into a compact,
    scientist-friendly date representation.

    Example:
        2021-11-19T00:00:00.000
        -> 19 Nov 2021
    """

    if value is None:
        return "Not available"

    text = str(value).strip()

    if text == "" or text.lower() == "not available":
        return "Not available"

    try:

        # Remove time portion if present
        date_part = text.split("T")[0]

        # Handle FITS dates such as YYYY-MM-DD
        from datetime import datetime

        parsed_date = datetime.strptime(
            date_part,
            "%Y-%m-%d"
        )

        return parsed_date.strftime(
            "%d %b %Y"
        )

    except Exception:

        # Preserve original value if it cannot be parsed
        return text


def format_exposure_time(value):
    """
    Convert FITS EXPTIME into a readable value in seconds.

    Example:
        1200
        -> 1200 s
    """

    if value is None:
        return "Not available"

    text = str(value).strip()

    if text == "" or text.lower() == "not available":
        return "Not available"

    try:

        exposure = float(text)

        if exposure.is_integer():

            return f"{int(exposure)} s"

        return f"{exposure:.3f} s"

    except Exception:

        # Preserve original FITS value if conversion fails
        return text


def format_dimensions(shape):
    """
    Convert an image shape into a readable dimension string.

    Example:
        (1171, 2560)
        -> 1,171 × 2,560
    """

    return " × ".join(
        f"{int(value):,}"
        for value in shape
    )


# =============================================================
# SCIENTIFIC INTERPRETATION
# =============================================================

def build_scientific_interpretation(
    category,
    num_regions,
    uv_intensity,
    intensity_variation,
    bright_pixel_count,
    bright_pixel_fraction,
    largest_region_size,
    average_region_size
):
    """
    Generate a qualitative scientific interpretation from the
    measured properties of the UV image.

    This interpretation does not calculate a physical star
    formation rate. It explains the measured image characteristics
    and the existing heuristic classification.
    """

    # ---------------------------------------------------------
    # BRIGHT PIXEL PERCENTAGE
    # ---------------------------------------------------------

    bright_fraction_percent = (
        bright_pixel_fraction * 100
    )

    # ---------------------------------------------------------
    # GENERAL ANALYSIS SUMMARY
    # ---------------------------------------------------------

    summary = (
        f"The analysis detected {num_regions:,} bright UV regions "
        f"within the image. The total normalized UV intensity is "
        f"{uv_intensity:.6f}, with an intensity variation of "
        f"{intensity_variation:.6f}."
    )

    # ---------------------------------------------------------
    # SPATIAL STRUCTURE DESCRIPTION
    # ---------------------------------------------------------

    spatial_description = (
        f"{bright_pixel_count:,} pixels were classified as bright, "
        f"representing {bright_fraction_percent:.4f}% of the image. "
        f"The largest detected region contains {largest_region_size:,} "
        f"pixels, while the average detected region contains "
        f"{average_region_size:.2f} pixels."
    )

    # ---------------------------------------------------------
    # CLASSIFICATION EXPLANATION
    # ---------------------------------------------------------

    classification_explanation = (
        f"Using the current image-analysis classification criteria, "
        f"the source is categorized as a {category.lower()}."
    )

    # ---------------------------------------------------------
    # SCIENTIFIC CONTEXT
    # ---------------------------------------------------------

    scientific_context = (
        "Ultraviolet emission is associated with young, massive stars "
        "and can therefore provide information about recent star-forming "
        "activity. The detected UV structures provide qualitative "
        "evidence about the spatial distribution and strength of UV "
        "emission in the analyzed image."
    )

    # ---------------------------------------------------------
    # SCIENTIFIC LIMITATION
    # ---------------------------------------------------------

    limitation = (
        "This classification is qualitative and image-based. A physical "
        "star-formation rate cannot be calculated from the current "
        "analysis because the FITS pixel values have not been converted "
        "to a calibrated physical UV luminosity."
    )

    # ---------------------------------------------------------
    # RETURN INTERPRETATION
    # ---------------------------------------------------------

    return {

        "summary": summary,

        "spatial_description": spatial_description,

        "classification_explanation": (
            classification_explanation
        ),

        "scientific_context": (
            scientific_context
        ),

        "limitation": limitation
    }


# =============================================================
# MEMORY-SAFE DISPLAY IMAGE
# =============================================================

def prepare_display_image(img, max_pixels=4_000_000):
    """
    Prepare a memory-safe image for visualization only.

    Scientific calculations continue to use the full-resolution
    image. Large images are reduced only for PNG display.
    """

    height, width = img.shape
    total_pixels = height * width

    if total_pixels <= max_pixels:
        return img

    scale = np.sqrt(
        max_pixels / total_pixels
    )

    new_height = max(
        1,
        int(height * scale)
    )

    new_width = max(
        1,
        int(width * scale)
    )

    row_indices = np.linspace(
        0,
        height - 1,
        new_height
    ).astype(int)

    col_indices = np.linspace(
        0,
        width - 1,
        new_width
    ).astype(int)

    return img[
        np.ix_(
            row_indices,
            col_indices
        )
    ]


# =============================================================
# MAIN FITS ANALYSIS
# =============================================================

def analyze_fits(fits_file):

    # ---------------------------------------------------------
    # VALIDATE FITS FILE
    # ---------------------------------------------------------

    validate_fits_file(fits_file)

    # ---------------------------------------------------------
    # OUTPUT DIRECTORY
    # ---------------------------------------------------------

    base_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    out_dir = os.path.join(
        base_dir,
        "outputs"
    )

    os.makedirs(
        out_dir,
        exist_ok=True
    )

    # ---------------------------------------------------------
    # READ FITS IMAGE AND HEADER
    # ---------------------------------------------------------
    #
    # The FITS file is opened only once.
    # Both image data and metadata are extracted here.
    # ---------------------------------------------------------

    try:

        with fits.open(
            fits_file,
            mode="readonly",
            memmap=False
        ) as hdul:

            primary_hdu = hdul[0]

            raw_data = primary_hdu.data
            header = primary_hdu.header

            if raw_data is None or raw_data.size == 0:
                raise RuntimeError(
                    "This FITS file does not contain an image in "
                    "the Primary HDU. Please upload an image FITS "
                    "(Level-2 image), not an event table."
                )

            # Preserve original FITS information
            original_shape = raw_data.shape
            original_dtype = raw_data.dtype

            # -------------------------------------------------
            # FITS METADATA
            # -------------------------------------------------

            def get_header_value(keyword):

                value = header.get(keyword)

                if value is None or str(value).strip() == "":
                    return "Not available"

                return str(value).strip()

            if len(original_shape) == 2:

                dimension_text = "2D Image"
                analysis_plane = "Full 2D image"

            elif len(original_shape) == 3:

                dimension_text = "3D Image Cube"
                analysis_plane = (
                    f"First 2D plane (1 of {original_shape[0]})"
                )

            else:

                dimension_text = f"{len(original_shape)}D"
                analysis_plane = "Not applicable"

            # -------------------------------------------------
            # SCIENTIST-FRIENDLY METADATA
            # -------------------------------------------------

            raw_observation_date = get_header_value(
                "DATE-OBS"
            )

            raw_exposure_time = get_header_value(
                "EXPTIME"
            )

            metadata = {

                "dimensions": format_dimensions(
                    original_shape
                ),

                "dimension_type": dimension_text,

                "analysis_plane": analysis_plane,

                "data_type": format_data_type(
                    original_dtype
                ),

                "instrument": get_header_value(
                    "INSTRUME"
                ),

                "filter": get_header_value(
                    "FILTER"
                ),

                "exposure_time": format_exposure_time(
                    raw_exposure_time
                ),

                "observation_date": format_observation_date(
                    raw_observation_date
                ),

                "telescope": get_header_value(
                    "TELESCOP"
                ),

                "object": get_header_value(
                    "OBJECT"
                )
            }

            # -------------------------------------------------
            # COPY IMAGE DATA INTO NUMPY ARRAY
            # -------------------------------------------------

            img = np.array(
                raw_data,
                dtype=np.float64,
                copy=True
            )

    except RuntimeError:
        raise

    except Exception as e:

        raise RuntimeError(
            f"Unable to read FITS file: {str(e)}"
        )

    # ---------------------------------------------------------
    # HANDLE IMAGE DIMENSIONS
    # ---------------------------------------------------------

    if img.ndim == 3:

        # Use first plane of the image cube
        img = img[0, :, :]

    elif img.ndim != 2:

        raise RuntimeError(
            "Unsupported FITS image dimensions. "
            "Expected a 2D image or a 3D image cube."
        )

    # ---------------------------------------------------------
    # REPLACE INVALID VALUES
    # ---------------------------------------------------------

    img[~np.isfinite(img)] = 0

    # =========================================================
    # IMAGE STATISTICS
    # =========================================================
    #
    # These statistics describe the input image before
    # background subtraction and normalization.
    # =========================================================

    valid_pixels = img[
        np.isfinite(img)
    ]

    if valid_pixels.size == 0:

        raise RuntimeError(
            "Image contains no valid pixel values."
        )

    minimum_intensity = np.min(
        valid_pixels
    )

    maximum_intensity = np.max(
        valid_pixels
    )

    mean_intensity = np.mean(
        valid_pixels
    )

    median_intensity = np.median(
        valid_pixels
    )

    standard_deviation = np.std(
        valid_pixels
    )

    total_pixels = img.size

    # ---------------------------------------------------------
    # RAW IMAGE
    # ---------------------------------------------------------

    raw_display = np.log10(
        prepare_display_image(img) + 1e-6
    )

    plt.figure(
        figsize=(8, 6)
    )

    plt.imshow(
        raw_display,
        cmap="gray",
        aspect="equal"
    )

    plt.axis("off")

    plt.colorbar()

    plt.title(
        "Raw FITS Image"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            out_dir,
            "raw.png"
        ),
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    # ---------------------------------------------------------
    # BACKGROUND SUBTRACTION
    # ---------------------------------------------------------

    background = np.median(
        img
    )

    img_clean = (
        img - background
    )

    img_clean[
        img_clean < 0
    ] = 0

    # ---------------------------------------------------------
    # MEDIAN FILTER
    # ---------------------------------------------------------

    img_filtered = median_filter(
        img_clean,
        size=(3, 3)
    )

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    mx = np.max(
        img_filtered
    )

    if mx <= 0:

        raise RuntimeError(
            "Image contains no useful signal."
        )

    img_norm = (
        img_filtered / mx
    )

    # ---------------------------------------------------------
    # PROCESSED IMAGE
    # ---------------------------------------------------------

    img_display = np.log10(
        prepare_display_image(img_norm) + 1e-6
    )

    plt.figure(
        figsize=(8, 6)
    )

    plt.imshow(
        img_display,
        cmap="hot",
        aspect="equal"
    )

    plt.axis("off")

    plt.colorbar()

    plt.title(
        "Processed FITS Image"
    )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            out_dir,
            "processed.png"
        ),
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    # ---------------------------------------------------------
    # BRIGHT REGION DETECTION
    # ---------------------------------------------------------

    threshold = threshold_otsu(
        img_norm
    )

    binary_img = (
        img_norm > threshold
    )

    # Explicit 8-connectivity.
    # This matches MATLAB bwconncomp()
    # default behavior.

    structure = np.ones(
        (3, 3),
        dtype=int
    )

    labeled_img, num_regions = label(
        binary_img,
        structure=structure
    )

    # =========================================================
    # DETECTED REGION STATISTICS
    # =========================================================

    # Number of bright pixels
    bright_pixel_count = int(
        np.sum(binary_img)
    )

    # Fraction of image classified as bright
    if total_pixels > 0:

        bright_pixel_fraction = (
            bright_pixel_count /
            total_pixels
        )

    else:

        bright_pixel_fraction = 0.0

    # ---------------------------------------------------------
    # REGION SIZES
    # ---------------------------------------------------------

    region_sizes = np.bincount(
        labeled_img.ravel()
    )

    # Remove background label (label 0)
    region_sizes = region_sizes[1:]

    if region_sizes.size > 0:

        largest_region_size = int(
            np.max(region_sizes)
        )

        average_region_size = float(
            np.mean(region_sizes)
        )

    else:

        largest_region_size = 0

        average_region_size = 0.0

    # ---------------------------------------------------------
    # UV INTENSITY
    # ---------------------------------------------------------

    positive_pixels = img_norm[
        img_norm > 0
    ]

    if positive_pixels.size == 0:

        uv_intensity = 0.0

        intensity_variation = 0.0

    else:

        uv_intensity = np.sum(
            positive_pixels
        )

        intensity_variation = np.std(
            positive_pixels
        )

    # ---------------------------------------------------------
    # STAR FORMATION CLASSIFICATION
    # ---------------------------------------------------------

    if (
        uv_intensity >= 450
        and
        num_regions >= 800
    ):

        category = (
            "Active Star Formation Region"
        )

    elif (
        uv_intensity >= 180
        and
        num_regions >= 500
    ):

        category = (
            "Moderate Star Formation Region"
        )

    else:

        category = (
            "Low Star Formation Region"
        )

    # =========================================================
    # SCIENTIFIC INTERPRETATION
    # =========================================================
    #
    # This layer interprets the existing measurements.
    # It does not modify the scientific calculations above.
    # =========================================================

    interpretation = build_scientific_interpretation(

        category=category,

        num_regions=num_regions,

        uv_intensity=uv_intensity,

        intensity_variation=intensity_variation,

        bright_pixel_count=bright_pixel_count,

        bright_pixel_fraction=bright_pixel_fraction,

        largest_region_size=largest_region_size,

        average_region_size=average_region_size
    )

    # ---------------------------------------------------------
    # HISTOGRAM
    # ---------------------------------------------------------

    signal_pixels = img_filtered[
        img_filtered > 0
    ]

    plt.figure(
        figsize=(8, 6)
    )

    if signal_pixels.size == 0:

        plt.text(
            0.2,
            0.5,
            "No signal detected"
        )

        plt.axis("off")

    else:

        histogram_values = np.log10(
            signal_pixels + 1e-6
        )

        plt.hist(
            histogram_values,
            bins=80
        )

        plt.xlabel(
            "log10(Pixel Intensity)"
        )

        plt.ylabel(
            "Number of Pixels"
        )

        plt.title(
            "Distribution of UV Signal"
        )

        plt.grid(
            True
        )

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            out_dir,
            "histogram.png"
        ),
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    # =========================================================
    # SAVE TEXT RESULTS
    # =========================================================

    results_path = os.path.join(
        out_dir,
        "results.txt"
    )

    with open(
        results_path,
        "w",
        encoding="utf-8"
    ) as fid:

        # -----------------------------------------------------
        # ANALYSIS PLANE
        # -----------------------------------------------------

        fid.write(
            f"Analysis Plane: {analysis_plane}\n"
        )

        fid.write("\n")

        # -----------------------------------------------------
        # IMAGE STATISTICS
        # -----------------------------------------------------

        fid.write(
            "IMAGE STATISTICS\n"
        )

        fid.write(
            "----------------\n"
        )

        fid.write(
            f"Minimum Intensity: "
            f"{minimum_intensity:.6f}\n"
        )

        fid.write(
            f"Maximum Intensity: "
            f"{maximum_intensity:.6f}\n"
        )

        fid.write(
            f"Mean Intensity: "
            f"{mean_intensity:.6f}\n"
        )

        fid.write(
            f"Median Intensity: "
            f"{median_intensity:.6f}\n"
        )

        fid.write(
            f"Standard Deviation: "
            f"{standard_deviation:.6f}\n"
        )

        fid.write("\n")

        # -----------------------------------------------------
        # BRIGHT REGION STATISTICS
        # -----------------------------------------------------

        fid.write(
            "BRIGHT REGION STATISTICS\n"
        )

        fid.write(
            "------------------------\n"
        )

        fid.write(
            f"Number of Bright Regions: "
            f"{num_regions}\n"
        )

        fid.write(
            f"Bright Pixel Count: "
            f"{bright_pixel_count}\n"
        )

        fid.write(
            f"Bright Pixel Fraction: "
            f"{bright_pixel_fraction:.6f}\n"
        )

        fid.write(
            f"Largest Bright Region: "
            f"{largest_region_size} pixels\n"
        )

        fid.write(
            f"Average Bright Region Size: "
            f"{average_region_size:.2f} pixels\n"
        )

        fid.write("\n")

        # -----------------------------------------------------
        # EXISTING ANALYSIS RESULTS
        # -----------------------------------------------------

        fid.write(
            "UV ANALYSIS\n"
        )

        fid.write(
            "-----------\n"
        )

        fid.write(
            f"Total UV Intensity: "
            f"{uv_intensity:.6f}\n"
        )

        fid.write(
            f"Intensity Variation: "
            f"{intensity_variation:.6f}\n"
        )

        fid.write(
            f"Background Level: "
            f"{background:.6f}\n"
        )

        fid.write(
            f"Detection Threshold: "
            f"{threshold:.6f}\n"
        )

        fid.write(
            f"Category: "
            f"{category}\n"
        )

        # -----------------------------------------------------
        # SCIENTIFIC INTERPRETATION
        # -----------------------------------------------------

        fid.write("\n")

        fid.write(
            "SCIENTIFIC INTERPRETATION\n"
        )

        fid.write(
            "-------------------------\n"
        )

        fid.write(
            f"{interpretation['summary']}\n\n"
        )

        fid.write(
            f"{interpretation['spatial_description']}\n\n"
        )

        fid.write(
            f"{interpretation['classification_explanation']}\n\n"
        )

        fid.write(
            f"{interpretation['scientific_context']}\n\n"
        )

        fid.write(
            f"Limitation: "
            f"{interpretation['limitation']}\n"
        )

    # =========================================================
    # RETURN RESULTS TO FLASK
    # =========================================================

    results = {

        # -----------------------------------------------------
        # EXISTING RESULTS
        # -----------------------------------------------------

        "num_regions": int(
            num_regions
        ),

        "uv_intensity": float(
            uv_intensity
        ),

        "intensity_variation": float(
            intensity_variation
        ),

        "category": category,

        "background": float(
            background
        ),

        "threshold": float(
            threshold
        ),

        # -----------------------------------------------------
        # FITS METADATA
        # -----------------------------------------------------

        "metadata": metadata,

        # -----------------------------------------------------
        # IMAGE STATISTICS
        # -----------------------------------------------------

        "statistics": {

            "minimum_intensity": float(
                minimum_intensity
            ),

            "maximum_intensity": float(
                maximum_intensity
            ),

            "mean_intensity": float(
                mean_intensity
            ),

            "median_intensity": float(
                median_intensity
            ),

            "standard_deviation": float(
                standard_deviation
            ),

            "bright_pixel_count": int(
                bright_pixel_count
            ),

            "bright_pixel_fraction": float(
                bright_pixel_fraction
            ),

            "largest_region_size": int(
                largest_region_size
            ),

            "average_region_size": float(
                average_region_size
            )
        },

        # -----------------------------------------------------
        # SCIENTIFIC INTERPRETATION
        # -----------------------------------------------------

        "interpretation": interpretation
    }

    print(
        "Analysis Complete"
    )

    return results