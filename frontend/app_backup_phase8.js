const messageInput = document.getElementById("message");
const sendButton = document.getElementById("send-button");
const micButton = document.getElementById("mic-button");
const chat = document.getElementById("chat");
const fileInput =
    document.getElementById("file-input");
const attachButton =
    document.getElementById("attach-button");


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
// CAREER RESULT
// ==========================================================

function renderCareerResult(data) {

    const job =
        data.job || {};

    const match =
        data.match || {};

    const skills =
        match.skills || {};

    const experience =
        data.experience || {};

    const tailoring =
        data.tailoring || {};

    const validation =
        data.validation || {};

    const resume =
        data.resume || {};

    const pdf =
        data.pdf || {};


    const required =
        skills.required || {};

    const preferred =
        skills.preferred || {};

    const technologyStack =
        skills.technology_stack || {};


    const matchedSkills = [
        ...(required.matched || []),
        ...(preferred.matched || []),
        ...(technologyStack.matched || [])
    ];


    const missingSkills = [
        ...(required.missing || []),
        ...(preferred.missing || []),
        ...(technologyStack.missing || [])
    ];


    const prioritySkills =
        tailoring.priority_skills || [];


    const priorityProjects =
        tailoring.priority_projects || [];


    const overallScore =
        match.overall_score;


    const recommendation =
        match.recommendation ||
        "Match evaluated";


    const validationPassed =
        validation.valid === true;


    const pdfPath =
        pdf.path || "";


    const sourceUrl =
        data.source_url ||
        job.application_url ||
        "";


    careerResult.innerHTML = `

        <div class="career-card">

            <!-- =========================================
                 HEADER
            ========================================== -->

            <div class="career-card-header">

                <div class="career-title-area">

                    <div class="career-eyebrow">
                        CAREER ANALYSIS
                    </div>

                    <h2>
                        ${escapeCareerHtml(
                            job.position ||
                            "Job Position"
                        )}
                    </h2>

                    <div class="career-company">

                        ${escapeCareerHtml(
                            job.company ||
                            "Company not specified"
                        )}

                    </div>

                </div>


                <div class="career-score">

                    <div class="career-score-number">

                        ${escapeCareerHtml(
                            overallScore ??
                            "—"
                        )}%

                    </div>

                    <div class="career-score-label">

                        ${escapeCareerHtml(
                            recommendation
                        )}

                    </div>

                </div>

            </div>


            <!-- =========================================
                 JOB META
            ========================================== -->

            <div class="career-meta">

                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Location
                    </span>

                    <strong>
                        ${escapeCareerHtml(
                            job.location ||
                            "Not specified"
                        )}
                    </strong>

                </div>


                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Work Mode
                    </span>

                    <strong>
                        ${escapeCareerHtml(
                            job.work_mode ||
                            "Not specified"
                        )}
                    </strong>

                </div>


                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Experience
                    </span>

                    <strong>
                        ${escapeCareerHtml(
                            experience.required_years ??
                            "Not specified"
                        )}
                        ${experience.required_years !== undefined
                            ? "years required"
                            : ""}
                    </strong>

                </div>


                <div class="career-meta-item">

                    <span class="career-meta-label">
                        Salary
                    </span>

                    <strong>
                        ${escapeCareerHtml(
                            job.salary ||
                            "Not specified"
                        )}
                    </strong>

                </div>

            </div>


            <!-- =========================================
                 MATCH OVERVIEW
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Match Overview
                    </h3>

                    <span>
                        How your profile compares
                    </span>

                </div>


                <div class="career-score-grid">

                    <div class="career-score-box">

                        <strong>
                            ${escapeCareerHtml(
                                match.role_score ??
                                "—"
                            )}%
                        </strong>

                        <span>
                            Role
                        </span>

                    </div>


                    <div class="career-score-box">

                        <strong>
                            ${escapeCareerHtml(
                                match.location_score ??
                                "—"
                            )}%
                        </strong>

                        <span>
                            Location
                        </span>

                    </div>


                    <div class="career-score-box">

                        <strong>
                            ${escapeCareerHtml(
                                match.work_mode_score ??
                                "—"
                            )}%
                        </strong>

                        <span>
                            Work Mode
                        </span>

                    </div>


                    <div class="career-score-box">

                        <strong>
                            ${escapeCareerHtml(
                                overallScore ??
                                "—"
                            )}%
                        </strong>

                        <span>
                            Overall
                        </span>

                    </div>

                </div>

            </div>


            <!-- =========================================
                 MATCHED SKILLS
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Skills You Match
                    </h3>

                    <span>
                        Skills already supported by your profile
                    </span>

                </div>

                ${careerChips(
                    matchedSkills,
                    "matched"
                )}

            </div>


            <!-- =========================================
                 SKILL GAPS
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Skill Gaps
                    </h3>

                    <span>
                        Requirements not currently supported
                        by your profile
                    </span>

                </div>

                ${careerChips(
                    missingSkills,
                    "missing"
                )}

            </div>


            <!-- =========================================
                 EXPERIENCE
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Experience Assessment
                    </h3>

                    <span>
                        Based on your actual career profile
                    </span>

                </div>


                <div class="
                    career-experience-box
                    ${
                        experience.status === "met"
                            ? "success"
                            : "warning"
                    }
                ">

                    <div>

                        <strong>

                            ${
                                experience.status === "met"
                                    ? "✓ Experience requirement met"
                                    : "⚠ Experience requirement not met"
                            }

                        </strong>

                    </div>


                    <div class="career-experience-stats">

                        <div>

                            <span>
                                Required
                            </span>

                            <strong>
                                ${escapeCareerHtml(
                                    experience.required_years ??
                                    "—"
                                )} years
                            </strong>

                        </div>


                        <div>

                            <span>
                                Your Experience
                            </span>

                            <strong>
                                ${escapeCareerHtml(
                                    experience.candidate_years ??
                                    "—"
                                )} years
                            </strong>

                        </div>

                    </div>


                    ${
                        experience.message
                            ? `
                                <p>
                                    ${escapeCareerHtml(
                                        experience.message
                                    )}
                                </p>
                            `
                            : ""
                    }

                </div>

            </div>


            <!-- =========================================
                 RESUME STRATEGY
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Resume Strategy
                    </h3>

                    <span>
                        What the system prioritized
                    </span>

                </div>


                <div class="career-strategy-grid">

                    <div class="career-strategy-card">

                        <h4>
                            Priority Skills
                        </h4>

                        ${careerChips(
                            prioritySkills,
                            "priority"
                        )}

                    </div>


                    <div class="career-strategy-card">

                        <h4>
                            Priority Projects
                        </h4>

                        ${careerBullets(
                            priorityProjects
                        )}

                    </div>

                </div>

            </div>


            <!-- =========================================
                 VALIDATION
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Resume Validation
                    </h3>

                </div>


                ${
                    validationPassed
                        ? `
                            <div class="
                                career-validation
                                success
                            ">

                                <div class="
                                    career-validation-icon
                                ">
                                    ✓
                                </div>

                                <div>

                                    <strong>
                                        Resume validated successfully
                                    </strong>

                                    <span>
                                        All generated resume facts
                                        passed grounding validation.
                                    </span>

                                </div>

                            </div>
                        `
                        : `
                            <div class="
                                career-validation
                                error
                            ">

                                <div class="
                                    career-validation-icon
                                ">
                                    !
                                </div>

                                <div>

                                    <strong>
                                        Resume validation failed
                                    </strong>

                                    <span>
                                        ${
                                            escapeCareerHtml(
                                                (
                                                    validation.errors ||
                                                    []
                                                ).join(" ")
                                            )
                                        }
                                    </span>

                                </div>

                            </div>
                        `
                }

            </div>


            <!-- =========================================
                 RESUME FACTS
            ========================================== -->

            <div class="career-section">

                <div class="career-section-title">

                    <h3>
                        Generated Resume
                    </h3>

                    <span>
                        Grounded in your existing career profile
                    </span>

                </div>


                <div class="career-grounding">

                    <div class="career-grounding-icon">
                        ✓
                    </div>

                    <div>

                        <strong>
                            No unsupported achievements or
                            fabricated experience
                        </strong>

                        <span>
                            The job description is used to
                            prioritize your existing skills,
                            projects and experience.
                        </span>

                    </div>

                </div>

            </div>


            <!-- =========================================
                 ACTIONS
            ========================================== -->

            <div class="career-actions">


                ${
                    pdfPath
                        ? `
                            <a
                                class="
                                    career-action
                                    primary
                                "
                                href="/career/resume?path=${encodeURIComponent(
                                    pdfPath
                                )}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                📄 Open Tailored Resume
                            </a>
                        `
                        : ""
                }


                ${
                    sourceUrl
                        ? `
                            <a
                                class="
                                    career-action
                                    secondary
                                "
                                href="${escapeCareerHtml(
                                    sourceUrl
                                )}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                ↗ View Job Posting
                            </a>
                        `
                        : ""
                }

            </div>

        </div>
    `;
}


// ==========================================================
// CAREER ANALYSIS
// ==========================================================

async function analyzeCareer() {

    const jobUrl =
        jobUrlInput.value.trim();


    if (!jobUrl) {

        careerStatus.textContent =
            "Please paste a job URL first.";

        jobUrlInput.focus();

        return;
    }


    careerButton.disabled = true;

    careerButton.textContent =
        "Analyzing...";


    careerStatus.textContent =
        "Fetching job description...";


    careerResult.innerHTML = `
        <div class="career-loading">

            <div class="career-loading-spinner"></div>

            <strong>
                Analyzing this job
            </strong>

            <span>
                Matching your profile and preparing
                a grounded resume...
            </span>

        </div>
    `;


    try {

        careerStatus.textContent =
            "Analyzing job requirements...";


        const response =
            await fetch(
                "/career/analyze",
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
                "Career analysis failed."
            );
        }


        careerStatus.textContent =
            "✓ Career analysis completed.";


        renderCareerResult(
            data
        );

    }

    catch (error) {

        console.error(
            "Career analysis error:",
            error
        );


        careerStatus.textContent =
            "Career analysis failed.";


        careerResult.innerHTML = `

            <div class="career-error">

                <strong>
                    Unable to analyze this job
                </strong>

                <span>
                    ${escapeCareerHtml(
                        error.message
                    )}
                </span>

            </div>

        `;

    }

    finally {

        careerButton.disabled =
            false;

        careerButton.textContent =
            "Analyze & Tailor Resume";

    }
}


// ==========================================================
// CAREER EVENTS
// ==========================================================

if (careerButton) {

    careerButton.addEventListener(
        "click",
        analyzeCareer
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

                analyzeCareer();

            }

        }
    );

}
// ==========================================================
// DOCUMENT ATTACHMENT
// ==========================================================

if (attachButton && fileInput) {

    attachButton.addEventListener(
        "click",
        () => {
            fileInput.click();
        }
    );


    fileInput.addEventListener(
        "change",
        async () => {

            const file =
                fileInput.files[0];

            if (!file) {
                return;
            }


            const fileName =
                file.name.toLowerCase();


            const allowedExtensions = [
                ".txt",
                ".pdf",
                ".docx"
            ];


            const valid =
                allowedExtensions.some(
                    extension =>
                        fileName.endsWith(extension)
                );


            if (!valid) {

                addMessage(
                    "My Agent",
                    "Please select a TXT, PDF, or DOCX file.",
                    "ai-message"
                );

                fileInput.value = "";

                return;
            }


            attachButton.disabled = true;

            attachButton.textContent = "⏳";


            const uploadMessage =
                addMessage(
                    "My Agent",
                    `Uploading ${file.name}...`,
                    "ai-message"
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
                        "/rag/upload",
                        {
                            method: "POST",
                            body: formData
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
                        data.error ||
                        "Document upload failed."
                    );
                }


                uploadMessage.remove();


                addMessage(
                    "My Agent",
                    `✓ ${file.name} was added to my knowledge base. I can now answer questions about this document.`,
                    "ai-message"
                );


            } catch (error) {

                console.error(
                    "Document upload error:",
                    error
                );


                uploadMessage.remove();


                addMessage(
                    "My Agent",
                    `I couldn't process ${file.name}: ${error.message}`,
                    "ai-message"
                );


            } finally {

                attachButton.disabled = false;

                attachButton.textContent = "📎";

                fileInput.value = "";

                messageInput.focus();
            }
        }
    );
}