const catalyst = require("zcatalyst-sdk-node");

const PROCESSOR_FUNCTION_NAME = "alliance_product_ai_processor";
const JOB_POOL_NAME = "allianceproductaipool";

module.exports = async (jobRequest, context) => {

    console.log("========================================");
    console.log("ALLIANCE PRODUCT AI WORKER");
    console.log("========================================");

    try {

        // ============================================================
        // GET JOB PARAMETERS
        // ============================================================

        const salesInboxId = jobRequest.getJobParam("sales_inbox_id");
        const fileId = jobRequest.getJobParam("file_id");
        // const fileName = jobRequest.getJobParam("file_name") || "";

        console.log("Sales Inbox ID :", salesInboxId);
        console.log("File ID        :", fileId);
        // console.log("File Name      :", fileName);

        // ============================================================
        // VALIDATE PARAMETERS
        // ============================================================

        if (!salesInboxId) {
            throw new Error("Missing job parameter: sales_inbox_id");
        }

        if (!fileId) {
            throw new Error("Missing job parameter: file_id");
        }

        // ============================================================
        // INITIALIZE CATALYST
        // ============================================================

        const app = catalyst.initialize(context);

        // ============================================================
        // VERIFY FILE EXISTS IN FILE STORE
        // ============================================================

        const FILE_STORE_FOLDER_ID = "64647000000032024";

        console.log("----------------------------------------");
        console.log("Checking PDF in Catalyst File Store...");
        console.log("Folder ID:", FILE_STORE_FOLDER_ID);
        console.log("File ID:", fileId);

        const filestore = app.filestore();
        const folder = filestore.folder(FILE_STORE_FOLDER_ID);

        const pdfBuffer = await folder.downloadFile(fileId);

        if (!pdfBuffer || pdfBuffer.length === 0) {
            throw new Error(
                `File Store returned empty file for file_id=${fileId}`
            );
        }

        console.log(
            "PDF downloaded successfully. Size:",
            pdfBuffer.length,
            "bytes"
        );

        // ============================================================
        // SUBMIT PYTHON PROCESSOR JOB
        // ============================================================

        console.log("----------------------------------------");
        console.log("Submitting Python processor job...");
        console.log("Processor:", PROCESSOR_FUNCTION_NAME);
        console.log("Job Pool :", JOB_POOL_NAME);

        const jobScheduling = app.jobScheduling();

        const jobName = `AP_${Date.now()}`.slice(-20);

        const processorJob = await jobScheduling.JOB.submitJob({

            job_name: jobName,

            jobpool_name: JOB_POOL_NAME,

            target_type: "Function",

            target_name: PROCESSOR_FUNCTION_NAME,

            params: {
                sales_inbox_id: String(salesInboxId),
                file_id: String(fileId),
            },

            job_config: {
                number_of_retries: 2,
                retry_interval: 15 * 60
            }
        });

        console.log("----------------------------------------");
        console.log("PYTHON PROCESSOR JOB SUBMITTED");
        console.log("----------------------------------------");

        console.log(
            "Processor Job:",
            JSON.stringify(processorJob, null, 2)
        );

        console.log("Job Name:", jobName);
        console.log("Sales Inbox ID:", salesInboxId);
        console.log("File ID:", fileId);

        // ============================================================
        // WORKER SUCCESS
        // ============================================================

        console.log("========================================");
        console.log("ALLIANCE PRODUCT AI WORKER SUCCESS");
        console.log("========================================");

        context.closeWithSuccess();

    } catch (error) {

        console.error("========================================");
        console.error("ALLIANCE PRODUCT AI WORKER FAILED");
        console.error("========================================");

        console.error(error);

        context.closeWithFailure();
    }
};