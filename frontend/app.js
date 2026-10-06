const API_BASE_URL =
    "https://astro-laboratory.onrender.com";


const fileInput =
    document.getElementById("fitsfile");

const fileName =
    document.getElementById("file-name");

const uploadForm =
    document.getElementById("upload-form");

const analyzeButton =
    document.getElementById("analyze-button");

const uploadStatus =
    document.getElementById("upload-status");

const uploadProgress =
    document.getElementById("upload-progress");

const uploadProgressBar =
    document.getElementById("upload-progress-bar");


fileInput.addEventListener(
    "change",
    function () {

        if (this.files.length > 0) {

            fileName.textContent =
                this.files[0].name;

            fileName.classList.add(
                "file-selected"
            );

        } else {

            fileName.textContent =
                "No file selected";

            fileName.classList.remove(
                "file-selected"
            );
        }

    }
);


uploadForm.addEventListener(
    "submit",
    async function (event) {

        event.preventDefault();

        const file =
            fileInput.files[0];

        if (!file) {

            uploadStatus.textContent =
                "Please select a FITS file.";

            return;
        }

        if (
            !file.name
                .toLowerCase()
                .endsWith(".fits")
        ) {

            uploadStatus.textContent =
                "Please select a .fits file.";

            return;
        }


        const CHUNK_SIZE =
            4 * 1024 * 1024;

        const totalChunks =
            Math.ceil(
                file.size / CHUNK_SIZE
            );

        const uploadId =
            crypto.randomUUID()
                .replace(/-/g, "");

        analyzeButton.disabled = true;

        analyzeButton.innerHTML =
            'Uploading… <span>↑</span>';

        uploadProgress.classList.add(
            "active"
        );

        uploadProgressBar.style.width =
            "0%";

        uploadStatus.textContent =
            `Preparing upload of ${totalChunks} chunks…`;


        try {

            /*
             * Upload the FITS file in chunks
             * directly to the Render backend.
             */

            for (
                let chunkIndex = 0;
                chunkIndex < totalChunks;
                chunkIndex++
            ) {

                const start =
                    chunkIndex * CHUNK_SIZE;

                const end =
                    Math.min(
                        start + CHUNK_SIZE,
                        file.size
                    );

                const chunk =
                    file.slice(
                        start,
                        end
                    );


                uploadStatus.textContent =
                    `Uploading chunk ${chunkIndex + 1} of ${totalChunks}…`;


                const response =
                    await fetch(
                        `${API_BASE_URL}/upload-chunk`,
                        {
                            method: "POST",

                            headers: {
                                "X-Upload-ID":
                                    uploadId,

                                "X-Filename":
                                    file.name,

                                "X-Chunk-Index":
                                    String(chunkIndex),

                                "X-Total-Chunks":
                                    String(totalChunks),

                                "X-File-Size":
                                    String(file.size)
                            },

                            body: chunk
                        }
                    );


                let data = null;

                try {

                    data =
                        await response.json();

                } catch (jsonError) {

                    data = null;

                }


                if (!response.ok) {

                    throw new Error(
                        data && data.error
                            ? data.error
                            : "Upload failed."
                    );

                }


                const uploadedChunks =
                    chunkIndex + 1;

                const progress =
                    (
                        uploadedChunks /
                        totalChunks
                    ) * 100;

                uploadProgressBar.style.width =
                    `${progress}%`;

            }


            /*
             * All chunks have now been uploaded.
             *
             * Request FITS analysis from Render.
             */

            uploadStatus.textContent =
                "Upload complete. Starting FITS analysis…";

            analyzeButton.innerHTML =
                'Analyzing… <span>⟳</span>';


            const response =
                await fetch(
                    `${API_BASE_URL}/api/analyze-upload?upload_id=${encodeURIComponent(uploadId)}&filename=${encodeURIComponent(file.name)}`,
                    {
                        method: "GET"
                    }
                );


            const data =
                await response.json();


            if (!response.ok || !data.success) {

                throw new Error(
                    data.error ||
                    "FITS analysis failed."
                );

            }


            console.log(
                "Astro Laboratory API analysis result:",
                data
            );


            /*
             * Store the complete API response temporarily
             * so results.html can render it.
             */

            sessionStorage.setItem(
                "astroBrowserAnalysis",
                JSON.stringify(data)
            );


            uploadStatus.textContent =
                "FITS analysis completed successfully.";

            analyzeButton.innerHTML =
                'Analysis Complete <span>✓</span>';


            /*
             * Open the Vercel frontend results page.
             */

            window.location.href =
                "/results.html";


        } catch (error) {

            console.error(error);

            uploadStatus.textContent =
                error.message ||
                "Upload or analysis failed.";

            analyzeButton.disabled =
                false;

            analyzeButton.innerHTML =
                'Analyze FITS File <span>→</span>';

            uploadProgress.classList.remove(
                "active"
            );

        }

    }
);