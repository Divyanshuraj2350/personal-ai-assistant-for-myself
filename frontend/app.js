const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send-button");
const micButton = document.getElementById("mic-button");
const chat = document.getElementById("chat");
const attachButton =
    document.getElementById("attach-button");

const attachmentMenu =
    document.getElementById("attachment-menu");

const attachmentOptions =
    document.querySelectorAll(".attachment-option");

const attachmentInputs = {
    "document-input":
        document.getElementById("document-input"),

    "image-input":
        document.getElementById("image-input"),

    "audio-input":
        document.getElementById("audio-input"),

    "video-input":
        document.getElementById("video-input"),
};

let fileUploadInProgress = false;


// ==========================================================
// ATTACHMENT MENU
// ==========================================================

function closeAttachmentMenu() {

    attachmentMenu.hidden = true;

    attachButton.setAttribute(
        "aria-expanded",
        "false"
    );
}


function toggleAttachmentMenu() {

    if (fileUploadInProgress) {
        return;
    }

    const isOpen =
        !attachmentMenu.hidden;

    attachmentMenu.hidden =
        isOpen;

    attachButton.setAttribute(
        "aria-expanded",
        String(!isOpen)
    );
}


attachButton.addEventListener(
    "click",
    (event) => {

        event.stopPropagation();

        toggleAttachmentMenu();
    }
);


attachmentOptions.forEach(option => {

    option.addEventListener(
        "click",
        (event) => {

            event.stopPropagation();

            const inputId =
                option.dataset.input;

            const input =
                attachmentInputs[inputId];

            if (!input) {
                return;
            }

            closeAttachmentMenu();

            input.value = "";

            input.click();
        }
    );
});


document.addEventListener(
    "click",
    (event) => {

        if (
            !event.target.closest(
                ".attachment-wrapper"
            )
        ) {
            closeAttachmentMenu();
        }
    }
);


// ==========================================================
// FILE UPLOAD
// ==========================================================

function addFileStatus(
    fileName,
    status,
    message
) {

    const card =
        document.createElement("div");

    card.className =
        "message ai-message file-message";


    const label =
        document.createElement("div");

    label.className =
        "message-label";

    label.textContent =
        "My Agent";


    const content =
        document.createElement("div");

    content.className =
        "file-status-card";


    const title =
        document.createElement("strong");

    title.textContent =
        fileName;


    const state =
        document.createElement("div");

    state.className =
        `file-status ${status}`;

    state.textContent =
        message;


    content.appendChild(title);

    content.appendChild(state);

    card.appendChild(label);

    card.appendChild(content);

    chat.appendChild(card);

    chat.scrollTop =
        chat.scrollHeight;


    return {
        card,
        state,
    };
}


async function uploadFile(file) {

    if (
        !file ||
        fileUploadInProgress
    ) {
        return;
    }

    fileUploadInProgress = true;

    attachButton.disabled = true;

    const statusCard =
        addFileStatus(
            file.name,
            "processing",
            "Uploading and processing..."
        );

    try {

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        const response =
            await fetch(
                "/files/upload",
                {
                    method: "POST",
                    body: formData,
                }
            );


        const data =
            await response.json();


        if (
            !response.ok ||
            data.status !== "success"
        ) {

            throw new Error(
                data.message ||
                "File processing failed."
            );
        }


        statusCard.state.className =
            "file-status success";

        statusCard.state.textContent =
            `✓ Processed successfully — ` +
            `${data.media_type || "file"} ` +
            `with ${data.chunks || 0} chunk(s).`;


        if (data.file_id) {

            const id =
                document.createElement("div");

            id.className =
                "file-id";

            id.textContent =
                `File ID: ${data.file_id}`;

            statusCard.card
                .querySelector(
                    ".file-status-card"
                )
                .appendChild(id);
        }


    } catch (error) {

        console.error(
            "File upload error:",
            error
        );


        statusCard.state.className =
            "file-status error";

        statusCard.state.textContent =
            `✕ ${error.message || "Upload failed."}`;
    }

    finally {

        fileUploadInProgress =
            false;

        attachButton.disabled =
            false;
    }
}


Object.values(
    attachmentInputs
).forEach(input => {

    input.addEventListener(
        "change",
        () => {

            const file =
                input.files[0];

            if (file) {
                uploadFile(file);
            }
        }
    );
});


// ==========================================================
// NORMAL MESSAGE
// ==========================================================

function addMessage(sender, text, type) {

    const message = document.createElement("div");

    message.className = `message ${type}`;


    const label = document.createElement("div");

    label.className = "message-label";

    label.textContent = sender;


    const content = document.createElement("div");

    content.className = "message-content";

    content.textContent = text;


    message.appendChild(label);

    message.appendChild(content);

    chat.appendChild(message);


    chat.scrollTop = chat.scrollHeight;


    return message;
}


// ==========================================================
// MARKDOWN
// ==========================================================

function renderMarkdown(content, markdownText) {

    if (typeof marked === "undefined") {

        content.textContent = markdownText;

        return;
    }


    content.innerHTML = marked.parse(
        markdownText
    );
}


// ==========================================================
// JOB ANALYSIS CARD
// ==========================================================

function addJobAnalysisCard(data) {

    const job = data.job;


    const card = document.createElement("div");

    card.className = "message ai-message";


    const label = document.createElement("div");

    label.className = "message-label";

    label.textContent = "My Agent";


    const analysis = document.createElement("div");

    analysis.className = "job-analysis-card";


    // ------------------------------------------------------
    // Job title
    // ------------------------------------------------------

    const title = document.createElement("h2");

    title.textContent =
        job.position || "Job Analysis";


    // ------------------------------------------------------
    // Company
    // ------------------------------------------------------

    const company = document.createElement("div");

    company.className = "job-company";

    company.textContent =
        job.company || "Company not specified";


    analysis.appendChild(title);

    analysis.appendChild(company);


    // ------------------------------------------------------
    // Basic information
    // ------------------------------------------------------

    const info = document.createElement("div");

    info.className = "job-info";


    addJobInfo(
        info,
        "Location",
        job.location
    );


    addJobInfo(
        info,
        "Work Mode",
        job.work_mode
    );


    addJobInfo(
        info,
        "Experience",
        formatArray(job.experience)
    );


    addJobInfo(
        info,
        "Salary",
        job.salary
    );


    addJobInfo(
        info,
        "Visa Sponsorship",
        job.visa_sponsorship
    );


    analysis.appendChild(info);


    // ------------------------------------------------------
    // Skills
    // ------------------------------------------------------

    addJobSection(
        analysis,
        "Required Skills",
        job.required_skills
    );


    addJobSection(
        analysis,
        "Preferred Skills",
        job.preferred_skills
    );


    addJobSection(
        analysis,
        "Technology Stack",
        job.tech_stack
    );


    // ------------------------------------------------------
    // Responsibilities
    // ------------------------------------------------------

    addJobSection(
        analysis,
        "Responsibilities",
        job.responsibilities
    );


    // ------------------------------------------------------
    // Application URL
    // ------------------------------------------------------

    if (data.source_url) {

        const source = document.createElement("a");

        source.href = data.source_url;

        source.target = "_blank";

        source.rel = "noopener noreferrer";

        source.className = "job-source";

        source.textContent =
            "Open Job Posting ↗";


        analysis.appendChild(source);
    }


    // ------------------------------------------------------
    // Build card
    // ------------------------------------------------------

    card.appendChild(label);

    card.appendChild(analysis);

    chat.appendChild(card);


    chat.scrollTop =
        chat.scrollHeight;
}


// ==========================================================
// JOB INFO
// ==========================================================

function addJobInfo(
    container,
    label,
    value
) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return;
    }


    const item = document.createElement("div");

    item.className =
        "job-info-item";


    const title = document.createElement("span");

    title.className =
        "job-info-label";

    title.textContent =
        label;


    const content = document.createElement("span");

    content.className =
        "job-info-value";

    content.textContent =
        value;


    item.appendChild(title);

    item.appendChild(content);

    container.appendChild(item);
}


// ==========================================================
// JOB SECTION
// ==========================================================

function addJobSection(
    container,
    title,
    items
) {

    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {
        return;
    }


    const section = document.createElement("div");

    section.className =
        "job-section";


    const heading = document.createElement("h3");

    heading.textContent =
        title;


    section.appendChild(heading);


    const list = document.createElement("ul");


    items.forEach(item => {

        const li =
            document.createElement("li");

        li.textContent =
            item;

        list.appendChild(li);
    });


    section.appendChild(list);

    container.appendChild(section);
}


// ==========================================================
// FORMAT ARRAY
// ==========================================================

function formatArray(items) {

    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {
        return null;
    }


    return items.join(" ");
}


// ==========================================================
// APPROVAL CARD
// ==========================================================

function addApprovalCard(data) {

    const card = document.createElement("div");

    card.className =
        "message ai-message";


    const label = document.createElement("div");

    label.className =
        "message-label";

    label.textContent =
        "My Agent";


    const approval = document.createElement("div");

    approval.className =
        "approval-card";


    const title = document.createElement("h3");

    title.textContent =
        "Email Approval";


    const recipient =
        document.createElement("p");

    recipient.innerHTML =
        `<strong>To:</strong> ${escapeHtml(data.recipient)}`;


    const subject =
        document.createElement("p");

    subject.innerHTML =
        `<strong>Subject:</strong> ${escapeHtml(data.subject)}`;


    const bodyLabel =
        document.createElement("p");

    bodyLabel.innerHTML =
        "<strong>Message:</strong>";


    const body =
        document.createElement("div");

    body.className =
        "approval-body";

    body.textContent =
        data.body;


    const buttons =
        document.createElement("div");

    buttons.className =
        "approval-buttons";


    const approveButton =
        document.createElement("button");

    approveButton.textContent =
        "Approve";

    approveButton.className =
        "approve-button";


    const rejectButton =
        document.createElement("button");

    rejectButton.textContent =
        "Reject";

    rejectButton.className =
        "reject-button";


    approveButton.addEventListener(
        "click",
        () => approveEmail(
            data.approval_id,
            approval,
            buttons
        )
    );


    rejectButton.addEventListener(
        "click",
        () => rejectEmail(
            data.approval_id,
            approval,
            buttons
        )
    );


    buttons.appendChild(
        approveButton
    );

    buttons.appendChild(
        rejectButton
    );


    approval.appendChild(title);

    approval.appendChild(recipient);

    approval.appendChild(subject);

    approval.appendChild(bodyLabel);

    approval.appendChild(body);

    approval.appendChild(buttons);


    card.appendChild(label);

    card.appendChild(approval);


    chat.appendChild(card);

    chat.scrollTop =
        chat.scrollHeight;
}


// ==========================================================
// HTML ESCAPING
// ==========================================================

function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent =
        text;

    return div.innerHTML;
}


// ==========================================================
// APPROVE EMAIL
// ==========================================================

async function approveEmail(
    approvalId,
    approvalCard,
    buttons
) {

    buttons
        .querySelectorAll("button")
        .forEach(button => {

            button.disabled = true;
        });


    try {

        const response =
            await fetch(
                `/approval/${approvalId}/approve`,
                {
                    method: "POST"
                }
            );


        const data =
            await response.json();


        if (
            !response.ok ||
            data.status === "error"
        ) {

            throw new Error(
                data.error ||
                data.message ||
                "Email sending failed."
            );
        }


        approvalCard.innerHTML = "";


        const title =
            document.createElement("h3");

        title.textContent =
            "Email Sent ✓";


        const message =
            document.createElement("p");

        message.textContent =
            `Email successfully sent to ${data.recipient}.`;


        approvalCard.appendChild(title);

        approvalCard.appendChild(message);


        chat.scrollTop =
            chat.scrollHeight;


    } catch (error) {

        console.error(
            "Email sending error:",
            error
        );


        buttons
            .querySelectorAll("button")
            .forEach(button => {

                button.disabled = false;
            });


        alert(
            error.message ||
            "Could not send the email."
        );
    }
}


// ==========================================================
// REJECT EMAIL
// ==========================================================

async function rejectEmail(
    approvalId,
    approvalCard,
    buttons
) {

    buttons
        .querySelectorAll("button")
        .forEach(button => {

            button.disabled = true;
        });


    try {

        const response =
            await fetch(
                `/approval/${approvalId}/reject`,
                {
                    method: "POST"
                }
            );


        const data =
            await response.json();


        if (
            !response.ok ||
            data.status === "error"
        ) {

            throw new Error(
                data.message ||
                "Rejection failed."
            );
        }


        approvalCard.innerHTML = "";


        const title =
            document.createElement("h3");

        title.textContent =
            "Email Rejected";


        const message =
            document.createElement("p");

        message.textContent =
            "The email draft was rejected and will not be sent.";


        approvalCard.appendChild(title);

        approvalCard.appendChild(message);


        chat.scrollTop =
            chat.scrollHeight;


    } catch (error) {

        console.error(
            "Rejection error:",
            error
        );


        buttons
            .querySelectorAll("button")
            .forEach(button => {

                button.disabled = false;
            });


        alert(
            error.message ||
            "Could not reject the email."
        );
    }
}


// ==========================================================
// SEND MESSAGE
// ==========================================================

async function sendMessage() {

    const message =
        messageInput.value.trim();


    if (
        !message ||
        sendButton.disabled
    ) {
        return;
    }


    addMessage(
        "You",
        message,
        "user-message"
    );


    messageInput.value = "";

    sendButton.disabled = true;


    const agentMessage =
        addMessage(
            "My Agent",
            "",
            "ai-message"
        );


    const content =
        agentMessage.querySelector(
            ".message-content"
        );


    content.textContent =
        "Thinking...";


    try {

        const response =
            await fetch(
                "/chat",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        message: message
                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                `Server returned ${response.status}`
            );
        }


        const reader =
            response.body.getReader();


        const decoder =
            new TextDecoder();


        let buffer = "";

        let rawResponse = "";


        while (true) {

            const {
                value,
                done
            } = await reader.read();


            if (done) {
                break;
            }


            buffer +=
                decoder.decode(
                    value,
                    {
                        stream: true
                    }
                );


            const events =
                buffer.split("\n\n");


            buffer =
                events.pop();


            for (
                const event of events
            ) {

                if (
                    !event.startsWith(
                        "data: "
                    )
                ) {
                    continue;
                }


                const data =
                    JSON.parse(
                        event.slice(6)
                    );


                // ------------------------------------------
                // JOB ANALYSIS
                // ------------------------------------------

                if (
                    data.type ===
                    "job_analysis"
                ) {

                    agentMessage.remove();

                    addJobAnalysisCard(
                        data
                    );

                    continue;
                }

                // ------------------------------------------
                // JOB ANALYSIS SUMMARY
                // ------------------------------------------

                if (
                    data.type === "job_analysis_summary"
                ) {
                    agentMessage.remove();

                    addMessage(
                        "My Agent",
                        data.content,
                        "ai-message"
                    );

                    continue;
                }



                // ------------------------------------------
                // EMAIL APPROVAL
                // ------------------------------------------

                if (
                    data.type ===
                    "approval"
                ) {

                    agentMessage.remove();

                    addApprovalCard(
                        data
                    );

                    continue;
                }


                // ------------------------------------------
                // NORMAL AI TOKEN
                // ------------------------------------------

                if (
                    data.type ===
                    "token"
                ) {

                    rawResponse +=
                        data.content;


                    renderMarkdown(
                        content,
                        rawResponse
                    );


                    chat.scrollTop =
                        chat.scrollHeight;
                }


                // ------------------------------------------
                // DONE
                // ------------------------------------------

                if (
                    data.type ===
                    "done"
                ) {

                    if (rawResponse) {

                        renderMarkdown(
                            content,
                            rawResponse
                        );
                    }


                    chat.scrollTop =
                        chat.scrollHeight;
                }
            }
        }


    } catch (error) {

        console.error(
            "Chat error:",
            error
        );


        content.textContent =
            "I couldn't connect to the AI server.";

    } finally {

        sendButton.disabled = false;

        messageInput.focus();
    }
}


// ==========================================================
// SEND BUTTON
// ==========================================================

sendButton.addEventListener(
    "click",
    sendMessage
);


// ==========================================================
// ENTER TO SEND
// ==========================================================

messageInput.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            sendMessage();
        }
    }
);


// ==========================================================
// VOICE INPUT
// ==========================================================

micButton.addEventListener(
    "click",
    () => {

        console.log(
            "Voice input will be added later."
        );
    }
);
// ==========================================================
// CAREER ASSISTANT
// ==========================================================

const careerButton =
    document.getElementById("career-button");

const jobUrlInput =
    document.getElementById("job-url");

const careerStatus =
    document.getElementById("career-status");

const careerResult =
    document.getElementById("career-result");


// ==========================================================
// CAREER STATE
// ==========================================================

let careerState = {
    jobUrl: "",
    applicationUrl: "",
    applicationResult: null,
    resumeFile: null,
    resumeUploaded: false,
};


// ==========================================================
// HTML SAFETY
// ==========================================================

function escapeCareerHtml(value) {

    if (
        value === null ||
        value === undefined
    ) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


// ==========================================================
// ARRAY HELPERS
// ==========================================================

function cleanCareerArray(values) {

    if (!Array.isArray(values)) {
        return [];
    }

    return values.filter(
        value =>
            value !== null &&
            value !== undefined &&
            String(value).trim() !== ""
    );
}


function careerChips(
    values,
    type = ""
) {

    const items =
        cleanCareerArray(values);

    if (items.length === 0) {

        return `
            <span class="career-empty">
                None identified
            </span>
        `;
    }

    return `
        <div class="career-chips">

            ${items.map(
                value => `
                    <span
                        class="career-chip ${type}"
                    >
                        ${escapeCareerHtml(value)}
                    </span>
                `
            ).join("")}

        </div>
    `;
}


function careerBullets(values) {

    const items =
        cleanCareerArray(values);

    if (items.length === 0) {

        return `
            <div class="career-empty">
                None identified
            </div>
        `;
    }

    return `
        <ul class="career-bullets">

            ${items.map(
                value => `
                    <li>
                        ${escapeCareerHtml(value)}
                    </li>
                `
            ).join("")}

        </ul>
    `;
}


// ==========================================================
// CAREER STATUS
// ==========================================================

function setCareerStatus(
    message,
    type = ""
) {

    if (!careerStatus) {
        return;
    }

    careerStatus.className =
        `career-status ${type}`;

    careerStatus.textContent =
        message;
}


// ==========================================================
// CAREER LOADING
// ==========================================================

function renderCareerLoading(
    title,
    message
) {

    careerResult.innerHTML = `

        <div class="career-loading">

            <div class="career-loading-spinner"></div>

            <strong>
                ${escapeCareerHtml(title)}
            </strong>

            <span>
                ${escapeCareerHtml(message)}
            </span>

        </div>
    `;
}


// ==========================================================
// CAREER ERROR
// ==========================================================

function renderCareerError(
    title,
    message
) {

    careerResult.innerHTML = `

        <div class="career-error">

            <strong>
                ${escapeCareerHtml(title)}
            </strong>

            <span>
                ${escapeCareerHtml(message)}
            </span>

        </div>
    `;
}


// ==========================================================
// APPLICATION FORM RESULT
// ==========================================================

function renderApplicationFormResult(
    data
) {

    const result =
        data.application_result ||
        data.form ||
        data;

    const applicationUrl =
        result.application_url ||
        result.final_url ||
        result.url ||
        careerState.jobUrl;

    careerState.applicationResult =
        result;

    careerState.applicationUrl =
        applicationUrl || "";

    const formDetected =
        result.is_application_form === true;

    const fieldCount =
        result.candidate_field_count ??
        result.field_count ??
        0;

    const submitCount =
        result.submit_control_count ??
        0;

    const title =
        result.title ||
        "Application Form";

    const finalUrl =
        result.final_url ||
        result.page_url ||
        applicationUrl ||
        "";

    if (!formDetected) {

        careerResult.innerHTML = `

            <div class="career-card">

                <div class="career-card-header">

                    <div class="career-title-area">

                        <div class="career-eyebrow">
                            APPLICATION CHECK
                        </div>

                        <h2>
                            Application form not detected
                        </h2>

                        <div class="career-company">
                            The supplied URL was inspected,
                            but it does not appear to contain
                            a usable application form.
                        </div>

                    </div>

                </div>

                <div class="career-section">

                    <div class="career-section-title">

                        <h3>
                            What was checked
                        </h3>

                    </div>

                    <div class="career-grounding">

                        <div class="career-grounding-icon">
                            !
                        </div>

                        <div>

                            <strong>
                                No application form detected
                            </strong>

                            <span>
                                Please provide the actual
                                employer application URL,
                                such as the Apply page or ATS
                                application page.
                            </span>

                        </div>

                    </div>

                </div>

            </div>
        `;

        setCareerStatus(
            "Application form was not detected.",
            "error"
        );

        return;
    }


    careerResult.innerHTML = `

        <div class="career-card">

            <div class="career-card-header">

                <div class="career-title-area">

                    <div class="career-eyebrow">
                        APPLICATION FORM
                    </div>

                    <h2>
                        Application form detected
                    </h2>

                    <div class="career-company">
                        ${escapeCareerHtml(title)}
                    </div>

                </div>

                <div class="career-score">

                    <div class="career-score-number">
                        ✓
                    </div>

                    <div class="career-score-label">
                        Form detected
                    </div>

                </div>

            </div>


            <div class="career-meta">

                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Candidate Fields
                    </span>

                    <strong>
                        ${escapeCareerHtml(fieldCount)}
                    </strong>

                </div>


                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Submit Controls
                    </span>

                    <strong>
                        ${escapeCareerHtml(submitCount)}
                    </strong>

                </div>

            </div>


            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Application URL
                    </h3>

                    <span>
                        The page that will be used later
                        for form filling
                    </span>

                </div>

                <div class="career-url-box">

                    <span>
                        ${escapeCareerHtml(
                            finalUrl
                        )}
                    </span>

                </div>

            </div>


            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Resume
                    </h3>

                    <span>
                        Upload the resume you want to use
                        for this application
                    </span>

                </div>


                <div class="career-resume-intake">

                    <input
                        id="career-resume-input"
                        type="file"
                        accept=".pdf,application/pdf"
                        hidden
                    >

                    <button
                        id="career-resume-button"
                        type="button"
                        class="career-action primary"
                    >
                        📄 Choose Resume PDF
                    </button>


                    <div
                        id="career-resume-status"
                        class="career-resume-status"
                    >
                        No resume selected.
                    </div>

                </div>

            </div>


            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Current Workflow
                    </h3>

                    <span>
                        Career Assistant progress
                    </span>

                </div>


                <div class="career-workflow">

                    <div class="career-step completed">

                        <span class="career-step-number">
                            ✓
                        </span>

                        <div>

                            <strong>
                                Job URL provided
                            </strong>

                            <span>
                                CA-1
                            </span>

                        </div>

                    </div>


                    <div class="career-step completed">

                        <span class="career-step-number">
                            ✓
                        </span>

                        <div>

                            <strong>
                                Application form detected
                            </strong>

                            <span>
                                CA-2
                            </span>

                        </div>

                    </div>


                    <div
                        id="career-step-resume"
                        class="career-step"
                    >

                        <span
                            id="career-step-resume-number"
                            class="career-step-number"
                        >
                            3
                        </span>

                        <div>

                            <strong>
                                Upload resume
                            </strong>

                            <span>
                                CA-3
                            </span>

                        </div>

                    </div>


                    <div class="career-step">

                        <span class="career-step-number">
                            4
                        </span>

                        <div>

                            <strong>
                                Extract resume
                            </strong>

                            <span>
                                CA-4
                            </span>

                        </div>

                    </div>


                    <div class="career-step">

                        <span class="career-step-number">
                            5
                        </span>

                        <div>

                            <strong>
                                Build structured application data
                            </strong>

                            <span>
                                CA-5
                            </span>

                        </div>

                    </div>

                </div>

            </div>


            <div class="career-section">

                <div class="career-grounding">

                    <div class="career-grounding-icon">
                        🔒
                    </div>

                    <div>

                        <strong>
                            Application submission is disabled
                        </strong>

                        <span>
                            Career Assistant will never submit
                            an application automatically.
                            Human/legal questions will require
                            your explicit answers.
                        </span>

                    </div>

                </div>

            </div>


            <div class="career-actions">

                ${
                    finalUrl
                        ? `
                            <a
                                class="
                                    career-action
                                    secondary
                                "
                                href="${escapeCareerHtml(
                                    finalUrl
                                )}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                ↗ Open Application
                            </a>
                        `
                        : ""
                }

            </div>

        </div>
    `;


    setupCareerResumeUpload();


    setCareerStatus(
        "✓ Application form detected. Upload your resume to continue.",
        "success"
    );
}


// ==========================================================
// CAREER RESUME UPLOAD
// ==========================================================

function setupCareerResumeUpload() {

    const resumeInput =
        document.getElementById(
            "career-resume-input"
        );

    const resumeButton =
        document.getElementById(
            "career-resume-button"
        );

    const resumeStatus =
        document.getElementById(
            "career-resume-status"
        );

    if (
        !resumeInput ||
        !resumeButton ||
        !resumeStatus
    ) {
        return;
    }


    resumeButton.addEventListener(
        "click",
        () => {

            resumeInput.click();

        }
    );


    resumeInput.addEventListener(
        "change",
        async () => {

            const file =
                resumeInput.files[0];

            if (!file) {
                return;
            }


            const fileName =
                file.name.toLowerCase();


            if (
                !fileName.endsWith(".pdf")
            ) {

                resumeStatus.className =
                    "career-resume-status error";

                resumeStatus.textContent =
                    "Please select a PDF resume.";

                resumeInput.value = "";

                return;
            }


            await uploadCareerResume(
                file,
                resumeStatus,
                resumeButton
            );
        }
    );
}


// ==========================================================
// UPLOAD CAREER RESUME
// ==========================================================

async function uploadCareerResume(
    file,
    statusElement,
    buttonElement
) {

    buttonElement.disabled = true;

    buttonElement.textContent =
        "Uploading...";

    statusElement.className =
        "career-resume-status processing";

    statusElement.textContent =
        "Uploading and processing your resume...";


    try {

        const formData =
            new FormData();

        formData.append(
            "file",
            file
        );


        /*
         * IMPORTANT:
         *
         * We reuse the existing /files/upload
         * endpoint so the original uploaded PDF
         * is preserved and receives a file_id.
         *
         * The backend returns:
         *   file_id
         *   file_path
         *   processing status
         *   rag_document_id
         *
         * CA-4 will consume the file_id.
         */

        const response =
            await fetch(
                "/files/upload",
                {
                    method: "POST",
                    body: formData
                }
            );


        let data;

        try {

            data =
                await response.json();

        } catch {

            throw new Error(
                "Server returned an invalid response."
            );

        }


        if (
            !response.ok ||
            data.status !== "success"
        ) {

            throw new Error(
                data.message ||
                data.error ||
                "Resume upload failed."
            );

        }


        careerState.resumeFile = {
            file_id:
                data.file_id || "",

            file_name:
                data.file_name ||
                file.name,

            file_path:
                data.file_path || "",

            rag_document_id:
                data.rag_document_id || "",

            processing_status:
                data.processing_status || "",

            processing_method:
                data.processing_method || ""
        };


        careerState.resumeUploaded =
            true;


        statusElement.className =
            "career-resume-status success";

        statusElement.innerHTML = `
            ✓ Resume uploaded:
            <strong>
                ${escapeCareerHtml(
                    data.file_name || file.name
                )}
            </strong>
        `;


        buttonElement.textContent =
            "✓ Resume Uploaded";


        const resumeStep =
            document.getElementById(
                "career-step-resume"
            );

        const resumeStepNumber =
            document.getElementById(
                "career-step-resume-number"
            );


        if (resumeStep) {

            resumeStep.classList.add(
                "completed"
            );

        }


        if (resumeStepNumber) {

            resumeStepNumber.textContent =
                "✓";

        }


        setCareerStatus(
            "✓ Resume uploaded successfully. It is ready for CA-4 extraction.",
            "success"
        );


        /*
         * We intentionally STOP here.
         *
         * CA-4 Resume Extraction is the next
         * backend step and will use the returned
         * file_id.
         *
         * We do NOT:
         * - modify the original PDF
         * - generate a new resume
         * - fill the employer form
         * - submit anything
         */

        addCareerResumeReadyPanel();

    }
    catch (error) {

        console.error(
            "Career resume upload error:",
            error
        );


        careerState.resumeUploaded =
            false;


        statusElement.className =
            "career-resume-status error";

        statusElement.textContent =
            `✕ ${
                error.message ||
                "Resume upload failed."
            }`;


        buttonElement.textContent =
            "📄 Choose Resume PDF";

    }
    finally {

        buttonElement.disabled =
            false;

    }
}


// ==========================================================
// RESUME READY PANEL
// ==========================================================

function addCareerResumeReadyPanel() {

    const existing =
        document.getElementById(
            "career-resume-ready"
        );

    if (existing) {
        existing.remove();
    }


    const section =
        document.createElement("div");

    section.id =
        "career-resume-ready";

    section.className =
        "career-section";


    section.innerHTML = `

        <div class="career-section-title">

            <h3>
                Resume Ready
            </h3>

            <span>
                CA-3 completed
            </span>

        </div>


        <div class="career-grounding">

            <div class="career-grounding-icon">
                ✓
            </div>

            <div>

                <strong>
                    Original resume preserved
                </strong>

                <span>
                    The uploaded PDF is stored as the
                    source document for the application.
                    The next step is structured resume
                    extraction.
                </span>

            </div>

        </div>

    `;


    careerResult
        .querySelector(".career-card")
        ?.appendChild(section);


    careerResult.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
    });
}


// ==========================================================
// CAREER APPLICATION FORM DETECTION
// ==========================================================

async function detectCareerApplicationForm() {

    const jobUrl =
        jobUrlInput.value.trim();


    if (!jobUrl) {

        setCareerStatus(
            "Please paste a job URL first.",
            "error"
        );

        jobUrlInput.focus();

        return;

    }


    careerState.jobUrl =
        jobUrl;


    careerButton.disabled =
        true;

    careerButton.textContent =
        "Inspecting...";


    setCareerStatus(
        "Checking the supplied URL for an application form...",
        "processing"
    );


    renderCareerLoading(
        "Inspecting application page",
        "Checking whether this URL contains a real employer application form..."
    );


    try {

        /*
         * CA-2 endpoint.
         *
         * The backend should expose the existing
         * application-form inspection logic through
         * /career/application-form.
         */

        const response =
            await fetch(
                "/career/application-form",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        job_url: jobUrl
                    })
                }
            );


        let data;

        try {

            data =
                await response.json();

        } catch {

            throw new Error(
                "Server returned an invalid response."
            );

        }


        if (
            !response.ok ||
            data.status !== "success"
        ) {

            throw new Error(
                data.message ||
                data.error ||
                "Application form detection failed."
            );

        }


        renderApplicationFormResult(
            data
        );

    }
    catch (error) {

        console.error(
            "Application form detection error:",
            error
        );


        setCareerStatus(
            "Application form detection failed.",
            "error"
        );


        renderCareerError(
            "Unable to inspect application page",
            error.message ||
            "Unknown application inspection error."
        );

    }
    finally {

        careerButton.disabled =
            false;

        careerButton.textContent =
            "Detect Application Form";

    }
}


// ==========================================================
// CAREER EVENTS
// ==========================================================

if (careerButton) {

    careerButton.addEventListener(
        "click",
        detectCareerApplicationForm
    );

}


if (jobUrlInput) {

    jobUrlInput.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                detectCareerApplicationForm();

            }

        }
    );

}