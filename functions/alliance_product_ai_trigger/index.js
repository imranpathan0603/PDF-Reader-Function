'use strict';

const catalyst = require('zcatalyst-sdk-node');
const Busboy = require('busboy');
const fs = require('fs');
const path = require('path');

const FILE_STORE_FOLDER_ID = '64647000000032024';
const JOB_POOL_NAME = 'allianceproductaipool';
const WORKER_FUNCTION_NAME = 'alliance_product_ai_worker';


/*
 * ============================================================
 * PARSE MULTIPART REQUEST
 * ============================================================
 */

function parseMultipart(req) {

    return new Promise((resolve, reject) => {

        const contentType = req.headers['content-type'];

        if (!contentType ||
            !contentType.includes('multipart/form-data')) {

            reject(
                new Error(
                    'Request must be multipart/form-data'
                )
            );

            return;
        }

        const busboy = Busboy({
            headers: req.headers
        });

        const fields = {};
        const files = [];

        busboy.on('field', (fieldname, value) => {

            console.log(
                'Field received:',
                fieldname,
                '=',
                value
            );

            fields[fieldname] = value;
        });


        busboy.on(
            'file',
            (fieldname, file, info) => {

                const {
                    filename,
                    encoding,
                    mimeType
                } = info;

                console.log('========================================');
                console.log('FILE RECEIVED');
                console.log('Field Name :', fieldname);
                console.log('File Name  :', filename);
                console.log('MIME Type  :', mimeType);
                console.log('Encoding   :', encoding);
                console.log('========================================');

                const chunks = [];

                file.on('data', (chunk) => {
                    chunks.push(chunk);
                });

                file.on('end', () => {

                    const buffer =
                        Buffer.concat(chunks);

                    console.log(
                        'File size:',
                        buffer.length,
                        'bytes'
                    );

                    files.push({
                        fieldname: fieldname,
                        filename: filename,
                        mimeType: mimeType,
                        buffer: buffer
                    });
                });

                file.on('error', reject);
            }
        );


        busboy.on('finish', () => {

            console.log('========================================');
            console.log('MULTIPART PARSING COMPLETE');
            console.log('========================================');

            console.log(
                'Fields:',
                JSON.stringify(fields)
            );

            console.log(
                'Files:',
                files.length
            );

            resolve({
                fields,
                files
            });
        });


        busboy.on('error', reject);

        req.pipe(busboy);
    });
}


/*
 * ============================================================
 * MAIN
 * ============================================================
 */

/**
 * @param {import("http").IncomingMessage} req
 * @param {import("http").ServerResponse} res
 */
module.exports = async (req, res) => {

    console.log('');
    console.log('========================================');
    console.log('ALLIANCE PRODUCT AI TRIGGER');
    console.log('========================================');

    let tempFilePath = null;

    try {

        /*
         * Initialize Catalyst
         */

        const app = catalyst.initialize(req);

        console.log(
            'Catalyst SDK initialized'
        );


        /*
         * Only POST
         */

        if (req.method !== 'POST') {

            res.writeHead(405, {
                'Content-Type':
                    'application/json'
            });

            res.end(
                JSON.stringify({
                    success: false,
                    error:
                        'Only POST requests are allowed.'
                })
            );

            return;
        }


        /*
         * ----------------------------------------------------
         * STEP 1: Parse multipart
         * ----------------------------------------------------
         */

        console.log(
            'Parsing multipart request...'
        );

        const parsed =
            await parseMultipart(req);

        const fields =
            parsed.fields;

        const files =
            parsed.files;


        /*
         * ----------------------------------------------------
         * STEP 2: Sales Inbox ID
         * ----------------------------------------------------
         */

        const salesInboxId =
            fields.sales_inbox_id;

        console.log(
            'Sales Inbox ID:',
            salesInboxId
        );

        if (!salesInboxId) {

            throw new Error(
                'sales_inbox_id was not provided.'
            );
        }


        /*
         * ----------------------------------------------------
         * STEP 3: PDF
         * ----------------------------------------------------
         */

        const pdfFile =
            files.find(
                file =>
                    file.fieldname === 'file'
            );

        if (!pdfFile) {

            throw new Error(
                'PDF file was not provided in field "file".'
            );
        }

        console.log(
            'PDF File Name:',
            pdfFile.filename
        );

        console.log(
            'PDF Size:',
            pdfFile.buffer.length,
            'bytes'
        );


        /*
         * ----------------------------------------------------
         * STEP 4: Save PDF temporarily
         * ----------------------------------------------------
         *
         * Catalyst File Store expects a ReadStream.
         *
         * Therefore:
         *
         * Buffer
         *    ↓
         * /tmp/file.pdf
         *    ↓
         * fs.createReadStream()
         *
         */

        const safeFileName =
            path.basename(
                pdfFile.filename ||
                'document.pdf'
            );

        tempFilePath =
            path.join(
                '/tmp',
                `${Date.now()}_${safeFileName}`
            );


        fs.writeFileSync(
            tempFilePath,
            pdfFile.buffer
        );


        console.log(
            'Temporary file created:',
            tempFilePath
        );


        /*
         * ----------------------------------------------------
         * STEP 5: Upload to File Store
         * ----------------------------------------------------
         */

        console.log(
            'Uploading PDF to Catalyst File Store...'
        );

        const filestore =
            app.filestore();

        const folder =
            filestore.folder(
                FILE_STORE_FOLDER_ID
            );


        /*
         * IMPORTANT:
         *
         * Catalyst Node SDK expects code to be
         * a ReadStream.
         */

        const uploadConfig = {

            code:
                fs.createReadStream(
                    tempFilePath
                ),

            name:
                safeFileName
        };


        console.log(
            'Upload configuration created'
        );


        const uploadResponse =
            await folder.uploadFile(
                uploadConfig
            );


        console.log('========================================');
        console.log('FILE STORE UPLOAD SUCCESS');
        console.log('========================================');

        console.log(
            JSON.stringify(
                uploadResponse,
                null,
                2
            )
        );


        /*
         * File ID
         */

        const fileId =
            uploadResponse.id;


        if (!fileId) {

            throw new Error(
                'File Store upload succeeded but no File ID was returned.'
            );
        }


        console.log(
            'File ID:',
            fileId
        );


        /*
         * ----------------------------------------------------
         * STEP 6: Submit Job
         * ----------------------------------------------------
         */

        console.log(
            'Submitting worker job...'
        );

		const jobScheduling =
		app.jobScheduling();
	
		const jobName =
		`APAI_${Date.now()}`;
	
	const functionJob =
		await jobScheduling.JOB.submitJob({
	
			job_name:
				jobName,
	
			jobpool_name:
				JOB_POOL_NAME,
	
			target_type:
				'Function',
	
			target_name:
				WORKER_FUNCTION_NAME,
	
			params: {
	
				sales_inbox_id:
					String(salesInboxId),
	
				file_id:
					String(fileId),
	
				file_name:
					String(safeFileName)
			},
	
			job_config: {
	
				number_of_retries:
					2,
	
				retry_interval:
					15 * 60
			}
		});

        console.log('========================================');
        console.log('WORKER JOB SUBMITTED');
        console.log('========================================');

        console.log(
            'Job Name:',
            jobName
        );

        console.log(
            'Job Response:',
            JSON.stringify(
                functionJob,
                null,
                2
            )
        );


        /*
         * ----------------------------------------------------
         * STEP 7: Success response
         * ----------------------------------------------------
         */

        res.writeHead(200, {
            'Content-Type':
                'application/json'
        });


        res.end(
            JSON.stringify({

                success: true,

                status:
                    'accepted',

                message:
                    'Sales Inbox processing job submitted.',

                sales_inbox_id:
                    String(salesInboxId),

                file_id:
                    String(fileId),

                file_name:
                    safeFileName,

                job_name:
                    jobName
            })
        );


    } catch (error) {

        console.error('');
        console.error('========================================');
        console.error('ALLIANCE PRODUCT AI TRIGGER ERROR');
        console.error('========================================');

        console.error(
            error
        );

        console.error(
            error.stack
        );


        res.writeHead(500, {
            'Content-Type':
                'application/json'
        });


        res.end(
            JSON.stringify({

                success: false,

                error:
                    'Alliance Product AI trigger failed.',

                details:
                    error.message ||
                    String(error)
            })
        );


    } finally {

        /*
         * Remove temporary PDF
         */

        if (
            tempFilePath &&
            fs.existsSync(tempFilePath)
        ) {

            try {

                fs.unlinkSync(
                    tempFilePath
                );

                console.log(
                    'Temporary file deleted:',
                    tempFilePath
                );

            } catch (cleanupError) {

                console.error(
                    'Temporary file cleanup failed:',
                    cleanupError
                );
            }
        }
    }
};