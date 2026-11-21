const API_BASE = "http://127.0.0.1:8010";

let assets = [];
let complaints = [];
let staffMembers = [];
let currentUser = null;
let accessToken = null;
let activeSection = "dashboard";
let loginInProgress = false;

// ---------- SAFE HELPERS ----------

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getRole() {
    return String(currentUser?.role || currentUser?.Role || "")
        .trim()
        .toLowerCase();
}

function isAdmin() {
    return getRole() === "admin";
}

function isStaff() {
    return getRole() === "staff";
}

function isCitizen() {
    return getRole() === "citizen";
}

function displayName() {
    return currentUser?.name
        || currentUser?.full_name
        || currentUser?.FullName
        || currentUser?.StaffName
        || currentUser?.CitizenName
        || currentUser?.email
        || currentUser?.Email
        || "User";
}

function showMessage(elementId, message, type = "") {
    const element = document.getElementById(elementId);

    if (!element) return;

    element.textContent = message;
    element.className = type;
}

function showConnectionError(message) {
    document.getElementById("connection-status").textContent = message;
    document.querySelector(".status-dot").style.background = "#dc4848";
}

function resetComplaintTables(message = "Please log in to view complaints.") {
    document.getElementById("recent-complaints").innerHTML =
        `<tr><td colspan="5">${escapeHTML(message)}</td></tr>`;

    document.getElementById("all-complaints").innerHTML =
        `<tr><td colspan="6">${escapeHTML(message)}</td></tr>`;

    document.getElementById("total-complaints").textContent = "—";
    document.getElementById("pending-complaints").textContent = "—";
    document.getElementById("resolved-complaints").textContent = "—";
}

// ---------- AUTHENTICATED API REQUESTS ----------

async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});

    if (accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }

    // Do not set JSON Content-Type for FormData.
    // The browser must set the multipart boundary automatically.
    if (
        options.body !== undefined &&
        options.body !== null &&
        !(options.body instanceof FormData)
    ) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401 && accessToken) {
        logout("Your session has expired. Please log in again.");
        throw new Error("Your session has expired. Please log in again.");
    }

    return response;
}

async function readResponse(response) {
    const text = await response.text();

    if (!text) return {};

    try {
        return JSON.parse(text);
    } catch {
        return { detail: text };
    }
}

function getErrorMessage(result, fallback = "Request failed.") {
    if (typeof result?.detail === "string") {
        return result.detail;
    }

    if (Array.isArray(result?.detail)) {
        return result.detail.map(item => item.msg || JSON.stringify(item))
            .join("; ");
    }

    return fallback;
}




async function checkSimilarComplaints(description, category) {
    const response = await apiFetch("/complaints/check-similar", {
        method: "POST",
        body: JSON.stringify({
            RawDescription: description,
            Category: category
        })
    });

    const result = await readResponse(response);

    if (!response.ok) {
        throw new Error(
            getErrorMessage(result, "Unable to check similar complaints.")
        );
    }

    return result.results || [];
}


function displaySimilarComplaints(results) {
    const section = document.getElementById("similar-complaints-section");
    const container = document.getElementById("similar-complaints-results");

    container.replaceChildren();

    if (!results.length) {
        section.hidden = true;
        return;
    }

    results.forEach(item => {
        const card = document.createElement("div");

        const title = document.createElement("strong");
        title.textContent = `Complaint #${item.complaint_id}`;

        const description = document.createElement("p");
        description.textContent = item.description;

        const category = document.createElement("p");
        category.textContent = `Category: ${item.category}`;

        card.append(title, description, category);
        card.style.border = "1px solid #ccc";
        card.style.padding = "10px";
        card.style.marginBottom = "8px";
        card.style.borderRadius = "8px";

        container.appendChild(card);
    });

    section.hidden = false;
}


// ---------- NAVIGATION AND ROLE PERMISSIONS ----------

function showSection(sectionId) {
    const allowedSections = [
        "dashboard",
        "assets",
        "submit",
        "complaints"
    ];

    if (!allowedSections.includes(sectionId)) {
        sectionId = "dashboard";
    }

    if (!currentUser && sectionId !== "dashboard") {
        sectionId = "dashboard";
    }

    if ((isAdmin() || isStaff()) && sectionId === "submit") {
        sectionId = "complaints";
    }

    if (isCitizen() && sectionId === "complaints") {
        sectionId = "dashboard";
    }

    activeSection = sectionId;

    document.querySelectorAll(".page-section").forEach(section => {
        section.style.display =
            section.id === "login-section"
                ? (!currentUser ? "block" : "none")
                : (currentUser && section.id === sectionId ? "block" : "none");
    });

    document.querySelectorAll(".nav-link").forEach(link => {
        const selected = link.getAttribute("href") === `#${sectionId}`;
        link.classList.toggle("active", selected);
    });

    const titles = {
        dashboard: "Dashboard Overview",
        assets: "Urban Assets",
        submit: "Submit Complaint",
        complaints: "Complaint Management"
    };

    document.getElementById("page-title").textContent =
        currentUser ? titles[sectionId] : "Sign in to UrbanCare";
}

function configureRoleView() {
    const navLinks = document.querySelectorAll(".nav-link");

    navLinks.forEach(link => {
        const section = link.getAttribute("href")?.slice(1);

        let visible = true;

        if (!currentUser) {
            visible = false;
        } else if (section === "submit") {
            visible = isCitizen();
        } else if (section === "complaints") {
            visible = isAdmin() || isStaff();
        }

        link.style.display = visible ? "" : "none";
    });

    const submitSection = document.getElementById("submit");
    const complaintSection = document.getElementById("complaints");

    submitSection.style.display = "none";
    complaintSection.style.display = "none";

    const complaintForm = document.getElementById("complaint-form");
    complaintForm.style.display = isCitizen() ? "" : "none";

    const welcomeHeading = document.querySelector(".welcome h2");
    const welcomeDescription = document.querySelector(".welcome p:last-child");

    if (welcomeHeading) {
        welcomeHeading.textContent = `Welcome to UrbanCare, ${displayName()}`;
    }

    if (welcomeDescription) {
        if (isAdmin()) {
            welcomeDescription.textContent =
                "Manage city assets, review complaints, and assign staff.";
        } else if (isStaff()) {
            welcomeDescription.textContent =
                "Review complaints assigned to you.";
        } else {
            welcomeDescription.textContent =
                "Report infrastructure issues and track your complaints.";
        }
    }

    document.querySelectorAll(".admin-controls").forEach(control => {
        control.style.display = isAdmin() ? "" : "none";
    });

    showSection(activeSection);
}

function updateProfile() {
    document.getElementById("profile-name").textContent =
        currentUser ? displayName() : "Not logged in";

    document.getElementById("profile-role").textContent =
        currentUser
            ? `Role: ${currentUser.role || currentUser.Role || "User"}`
            : "Please sign in";

    document.getElementById("profile-avatar").textContent =
        currentUser ? displayName().charAt(0).toUpperCase() : "U";

    document.getElementById("logout-button").style.display =
        currentUser ? "" : "none";
}

// ---------- LOGIN ----------

document.getElementById("login-form").addEventListener("submit", async event => {
    event.preventDefault();

    if (loginInProgress) return;

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const button = event.currentTarget.querySelector('button[type="submit"]');

    loginInProgress = true;
    button.disabled = true;
    button.textContent = "Signing in...";
    showMessage("login-message", "");

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                Email: email,
                Password: password
            })
        });

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Login failed."));
        }

        if (!result.access_token) {
            throw new Error("The server did not return an access token.");
        }

        accessToken = result.access_token;

        const meResponse = await apiFetch("/auth/me");
        const me = await readResponse(meResponse);

        if (!meResponse.ok) {
            accessToken = null;
            throw new Error(getErrorMessage(me, "Unable to verify your account."));
        }

        currentUser = me;

        const role = getRole();

        if (!["admin", "staff", "citizen"].includes(role)) {
            logout("Your account has an unsupported role.");
            throw new Error("Your account role is not supported.");
        }

        document.getElementById("login-password").value = "";
        updateProfile();
        configureRoleView();

        showMessage("login-message", "Login successful.", "success");

        await loadAssets();

        if (isAdmin()) {
        await loadStaff();
        } else {
    staffMembers = [];
    }

await loadComplaints();

        showSection("dashboard");

    } catch (error) {
        accessToken = null;
        currentUser = null;

        updateProfile();
        configureRoleView();

        showMessage(
            "login-message",
            error.message || "Unable to log in. Check the backend connection.",
            "error"
        );

        console.error("Login error:", error);
    } finally {
        loginInProgress = false;
        button.disabled = false;
        button.textContent = "Login";
    }
});

// ---------- LOGOUT ----------

function logout(message = "") {
    accessToken = null;
    currentUser = null;

    assets = [];
    complaints = [];
    staffMembers = [];

    document.getElementById("total-assets").textContent = "—";
    document.getElementById("assets-list").innerHTML =
        "<p>Please log in to view assets.</p>";

    document.getElementById("asset-id").innerHTML =
        '<option value="">Log in to select an asset</option>';

    resetComplaintTables();

    document.getElementById("complaint-form").reset();
    document.getElementById("urgency").value = 5;

    updateProfile();
    configureRoleView();
    showSection("dashboard");

    if (message) {
        showMessage("login-message", message, "error");
    } else {
        showMessage("login-message", "You have logged out.");
    }
}

// ---------- BACKEND CONNECTION ----------

async function checkBackend() {
    try {
        const response = await fetch(`${API_BASE}/`);

        if (!response.ok) {
            throw new Error("Backend unavailable");
        }

        document.getElementById("connection-status").textContent = "Connected";
        document.querySelector(".status-dot").style.background = "#16a36a";
    } catch (error) {
        showConnectionError("Not connected");
        console.error("Backend connection error:", error);
    }
}

// ---------- URBAN ASSETS ----------

async function loadAssets() {
    const container = document.getElementById("assets-list");

    try {
        const response = await fetch(`${API_BASE}/assets`);
        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Unable to load assets."));
        }

        assets = Array.isArray(result) ? result : [];

        document.getElementById("total-assets").textContent = assets.length;

        if (assets.length === 0) {
            container.innerHTML = "<p>No assets found.</p>";
        } else {
            container.innerHTML = assets.map(asset => {
                const statusClass = String(asset.OperationalStatus || "")
                    .toLowerCase()
                    .replaceAll(" ", "-");

                
return `
    <article class="asset-card">
        <span class="asset-type">${escapeHTML(asset.AssetType)}</span>
        <h3>${escapeHTML(asset.AssetName)}</h3>
        <p>Asset ID: ${escapeHTML(asset.asset_id)}</p>
        <p>Location: ${escapeHTML(asset.Lat)}, ${escapeHTML(asset.Long)}</p>
        <p class="asset-status ${escapeHTML(statusClass)}">
            ${escapeHTML(asset.OperationalStatus)}
        </p>

        ${isAdmin() ? `
            <div class="asset-actions">
                <button
                    class="secondary-button"
                    type="button"
                    onclick="editAsset(${Number(asset.asset_id)})">
                    Edit
                </button>

                <button
                    class="secondary-button"
                    type="button"
                    onclick="deleteAsset(${Number(asset.asset_id)})">
                    Delete
                </button>
            </div>
        ` : ""}
    </article>
`;

            }).join("");
        }

        const assetSelect = document.getElementById("asset-id");

        assetSelect.innerHTML =
            '<option value="">Select an asset</option>' +
            assets.map(asset => `
                <option value="${escapeHTML(asset.asset_id)}">
                    ${escapeHTML(asset.AssetName)} (ID: ${escapeHTML(asset.asset_id)})
                </option>
            `).join("");

    } catch (error) {
        container.innerHTML = "<p>Unable to load assets.</p>";
        console.error("Asset loading error:", error);
    }
}

// ---------- STAFF ----------

async function loadStaff() {
    if (!isAdmin()) {
        staffMembers = [];
        return;
    }

    try {
        const response = await apiFetch("/staff");
        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Unable to load staff."));
        }

        staffMembers = Array.isArray(result) ? result : [];
    } catch (error) {
        staffMembers = [];
        console.error("Staff loading error:", error);
    }
}

// ---------- COMPLAINTS ----------

async function loadComplaints() {
    if (!currentUser || !accessToken) {
        resetComplaintTables();
        return;
    }

    try {
        const response = await apiFetch("/complaints");
        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Unable to load complaints."));
        }

        complaints = Array.isArray(result) ? result : [];

        document.getElementById("total-complaints").textContent =
            complaints.length;

        const resolvedCount = complaints.filter(complaint =>
            ["Resolved", "Closed"].includes(complaint.Status)
        ).length;

        document.getElementById("resolved-complaints").textContent =
            resolvedCount;

        document.getElementById("pending-complaints").textContent =
            complaints.length - resolvedCount;

        renderComplaints();

    } catch (error) {
        resetComplaintTables(error.message || "Unable to load complaints.");
        console.error("Complaint loading error:", error);
    }
}

function statusClass(status) {
    return String(status || "unknown")
        .toLowerCase()
        .replaceAll(" ", "-");
}

function renderComplaints() {
    const recentBody = document.getElementById("recent-complaints");
    const allBody = document.getElementById("all-complaints");

    if (complaints.length === 0) {
        recentBody.innerHTML =
            '<tr><td colspan="5">No complaints found.</td></tr>';

        allBody.innerHTML =
            '<tr><td colspan="6">No complaints found.</td></tr>';
        return;
    }

    const sorted = [...complaints].sort((a, b) =>
        Number(b.complaint_id) - Number(a.complaint_id)
    );

    recentBody.innerHTML = sorted.slice(0, 5).map(complaint => `
        <tr>
            <td>#${escapeHTML(complaint.complaint_id)}</td>
            <td>${escapeHTML(complaint.RawDescription)}</td>
            <td>${escapeHTML(complaint.Category)}</td>
            <td>${escapeHTML(complaint.UrgencyScore)}/10</td>
            <td>
                <span class="status-badge ${statusClass(complaint.Status)}">
                    ${escapeHTML(complaint.Status || "Unknown")}
                </span>
            </td>
        </tr>
    `).join("");

    allBody.innerHTML = sorted.map(complaint => {
        const photoHTML = complaint.PhotoURL
    ? `<a href="${escapeHTML(complaint.PhotoURL)}" target="_blank">
           <img src="${escapeHTML(complaint.PhotoURL)}"
                alt="Complaint photo"
                style="width:100px; height:75px; object-fit:cover;
                       border-radius:8px; cursor:pointer;">
       </a>`
    : "No photo";
        const id = Number(complaint.complaint_id);
        const status = complaint.Status || "Submitted";
        const finished = ["Resolved", "Closed"].includes(status);

        const pendingRequest =
            complaint.ResolutionRequestPending === true ||
            Number(complaint.ResolutionRequestPending) === 1;

        const requestNote = String(
            complaint.ResolutionRequestNote || ""
        ).replace(/^RESOLUTION_REQUEST:\s*/, "");

        const staffOptions = staffMembers.map(person => `
            <option value="${escapeHTML(person.staff_id)}">
                ${escapeHTML(person.StaffName)}
            </option>
        `).join("");

        const adminControls = isAdmin() && !finished;

        let actionControls = "";

        if (isAdmin() && pendingRequest) {
            actionControls = `
                <div class="admin-controls">
                    <p><strong>Resolution request pending</strong></p>
                    <p>${escapeHTML(requestNote)}</p>
                    <button class="primary-button"
                        onclick="reviewResolutionRequest(${id}, 'Approved')">
                        Approve
                    </button>
                    <button class="secondary-button"
                        onclick="reviewResolutionRequest(${id}, 'Rejected')">
                        Reject
                    </button>
                </div>
            `;
        } else if (isAdmin() && !finished) {
            actionControls = `
                <div class="admin-controls">
                    <select id="status-${id}">
                        <option value="Assigned">Assigned</option>
                        <option value="In Progress">In Progress</option>
                    </select>
                    <button class="secondary-button"
                        onclick="updateComplaintStatus(${id})">Update</button>
                </div>
            `;
        } else if (isStaff() && !finished) {
            actionControls = `
                <div class="staff-controls">
                    <select id="staff-status-${id}">
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Request Resolution</option>
                    </select>
                    <button class="secondary-button"
                        onclick="updateStaffComplaintStatus(${id})">
                        Submit
                    </button>
                </div>
            `;
        } else {
            actionControls = finished ? "Completed" : "View only";
        }

        return `
            <tr>
                <td>#${escapeHTML(id)}</td>
                <td>${escapeHTML(complaint.RawDescription)}</td>
                <td>${photoHTML}</td>
                <td>${escapeHTML(complaint.Category)}</td>
                <td>
                    <span class="status-badge ${statusClass(status)}">
                        ${escapeHTML(status)}
                    </span>
                    ${isAdmin() && pendingRequest
                        ? '<p><strong>Awaiting approval</strong></p>'
                        : ""}
                </td>
                <td>
                    ${escapeHTML(complaint.StaffName || "Not assigned")}
                    ${adminControls ? `
                        <div class="admin-controls">
                            <select id="staff-${id}">
                                <option value="">Select staff</option>
                                ${staffOptions}
                            </select>
                            <button class="secondary-button"
                                onclick="assignStaff(${id})">Assign</button>
                        </div>
                    ` : ""}
                </td>
                <td>${actionControls}</td>
            </tr>
        `;
    }).join("");
}



async function updateStaffComplaintStatus(complaintId) {
    if (!isStaff()) {
        alert("Only staff can update their assigned complaints.");
        return;
    }

    const select = document.getElementById(`staff-status-${complaintId}`);
    if (!select) return;

    const status = select.value;
    const note = prompt(
        status === "Resolved"
            ? "Describe the completed work for Admin review:"
            : "Enter a progress update (optional):"
    );

    if (note === null) return;

    if (status === "Resolved" && !note.trim()) {
        alert("Please describe the completed work before requesting resolution.");
        return;
    }

    try {
        const response = await apiFetch(
            `/complaints/${complaintId}/staff-status`,
            {
                method: "PUT",
                body: JSON.stringify({
                    Status: status,
                    Note: note.trim()
                })
            }
        );

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(
                getErrorMessage(result, "Unable to update complaint.")
            );
        }

        alert(result.message || "Complaint updated successfully.");
        await loadComplaints();
    } catch (error) {
        alert(`Complaint update failed: ${error.message}`);
    }
}

async function reviewResolutionRequest(complaintId, decision) {
    if (!isAdmin()) {
        alert("Only administrators can review resolution requests.");
        return;
    }

    if (!["Approved", "Rejected"].includes(decision)) {
        alert("Invalid review decision.");
        return;
    }

    const action = decision === "Approved" ? "approve" : "reject";

    if (!confirm(
        `Are you sure you want to ${action} the resolution request for complaint #${complaintId}?`
    )) {
        return;
    }

    const note = prompt(
        decision === "Approved"
            ? "Enter an inspection note (optional):"
            : "Explain why more work is needed:"
    );

    if (note === null) return;

    if (decision === "Rejected" && !note.trim()) {
        alert("Please explain why the resolution request is rejected.");
        return;
    }

    try {
        const response = await apiFetch(
            `/complaints/${complaintId}/resolution-review`,
            {
                method: "PUT",
                body: JSON.stringify({
                    Decision: decision,
                    Note: note.trim()
                })
            }
        );

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(
                getErrorMessage(result, "Unable to review resolution request.")
            );
        }

        alert(result.message || `Resolution request ${action}d.`);
        await loadComplaints();
    } catch (error) {
        alert(`Review failed: ${error.message}`);
    }
}



// ---------- ADMIN ACTIONS ----------

async function assignStaff(complaintId) {
    if (!isAdmin()) {
        alert("Only administrators can assign staff.");
        return;
    }

    const select = document.getElementById(`staff-${complaintId}`);
    const staffId = Number(select?.value);

    if (!staffId) {
        alert("Please select a staff member.");
        return;
    }

    try {
        const response = await apiFetch(
            `/complaints/${complaintId}/assign`,
            {
                method: "POST",
                body: JSON.stringify({ staff_id: staffId })
            }
        );

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Assignment failed."));
        }

        alert("Staff assigned successfully.");
        await loadComplaints();
    } catch (error) {
        alert(`Assignment failed: ${error.message}`);
    }
}

async function updateComplaintStatus(complaintId) {
    if (!isAdmin()) {
        alert("Only administrators can update complaint status.");
        return;
    }

    const select = document.getElementById(`status-${complaintId}`);

    if (!select) return;

    const status = select.value;
    const note = prompt("Enter an update note (optional):") || "";

    try {
        const response = await apiFetch(
            `/complaints/${complaintId}/status`,
            {
                method: "PUT",
                body: JSON.stringify({
                    Status: status,
                    Note: note
                })
            }
        );

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Status update failed."));
        }

        alert("Complaint status updated.");
        await loadComplaints();
    } catch (error) {
        alert(`Status update failed: ${error.message}`);
    }
}



 // ---------- CITIZEN COMPLAINT SUBMISSION ----------


document.getElementById("complaint-form").addEventListener("submit", async function(event) {
    event.preventDefault();

    if (!isCitizen() || !accessToken) {
        showMessage("form-message", "Please log in with a Citizen account.", "error");
        return;
    }

    const submitButton = this.querySelector('button[type="submit"]');
    const photoInput = document.getElementById("photo-url");
    const fileInput = document.getElementById("attachment-file");

    const photoUrl = photoInput ? photoInput.value.trim() : "";
    const selectedFile = fileInput?.files?.[0] || null;

    // Prevent providing both a URL and an uploaded file.
    if (photoUrl && selectedFile) {
        showMessage(
            "form-message",
            "Provide a Photo URL or upload a file, not both.",
            "error"
        );
        return;
    }

    // Validate the optional photo URL.
    if (photoUrl) {
        try {
            const parsedUrl = new URL(photoUrl);

            if (!["http:", "https:"].includes(parsedUrl.protocol)) {
                throw new Error("Invalid URL");
            }
        } catch {
            showMessage(
                "form-message",
                "Enter a valid HTTP or HTTPS photo URL.",
                "error"
            );
            return;
        }
    }

    // Validate an optional attachment.
    const allowedTypes = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf"
    ];

    if (selectedFile && !allowedTypes.includes(selectedFile.type)) {
        showMessage(
            "form-message",
            "Only JPG, PNG, WEBP, GIF and PDF files are allowed.",
            "error"
        );
        return;
    }

    if (selectedFile && selectedFile.size > 5 * 1024 * 1024) {
        showMessage(
            "form-message",
            "The file must be 5 MB or smaller.",
            "error"
        );
        return;
    }

    // Prepare the complaint.
    const complaint = {
        RawDescription: document.getElementById("description").value.trim(),
        Category: document.getElementById("category").value,
        Lat: Number(document.getElementById("latitude").value),
        Long: Number(document.getElementById("longitude").value),
        UrgencyScore: Number(document.getElementById("urgency").value),
        asset_id: Number(document.getElementById("asset-id").value),
        PhotoURL: photoUrl || null
    };

    // Step 1: Check for similar complaints.
    submitButton.disabled = true;
    submitButton.textContent = "Checking for similar complaints...";
    showMessage("form-message", "Checking for similar complaints...");

    try {
        const similarResults = await checkSimilarComplaints(
            complaint.RawDescription,
            complaint.Category
        );

        displaySimilarComplaints(similarResults);

        // Ask before continuing if matches were found.
        if (similarResults.length > 0) {
            const proceed = confirm(
                "Similar complaints already exist.\n\n" +
                "Please review the existing complaints. " +
                "Do you still want to submit a new complaint?"
            );

            if (!proceed) {
                showMessage(
                    "form-message",
                    "Submission cancelled. Review the existing complaints.",
                    "info"
                );
                return;
            }
        }
    } catch (similarityError) {
        console.error("Similarity check failed:", similarityError);

        showMessage(
            "form-message",
            "Could not check similar complaints. Please try again.",
            "error"
        );
        return;
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Submit Complaint";
    }

    // Step 2: Upload the optional attachment and submit.
    submitButton.disabled = true;
    submitButton.textContent = "Submitting...";

    try {
        if (selectedFile) {
            showMessage("form-message", "Uploading attachment...");

            const formData = new FormData();
            formData.append("file", selectedFile);

            const uploadResponse = await apiFetch("/uploads", {
                method: "POST",
                body: formData
            });

            const uploadResult = await readResponse(uploadResponse);

            if (!uploadResponse.ok) {
                throw new Error(
                    getErrorMessage(uploadResult, "Attachment upload failed.")
                );
            }

            if (!uploadResult.url) {
                throw new Error(
                    "The server did not return the uploaded file URL."
                );
            }

            complaint.PhotoURL = new URL(
                uploadResult.url,
                API_BASE
            ).href;
        }

        showMessage("form-message", "Submitting complaint...");

        const response = await apiFetch("/complaints", {
            method: "POST",
            body: JSON.stringify(complaint)
        });

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(
                getErrorMessage(result, "Submission failed.")
            );
        }

        showMessage(
            "form-message",
            `Complaint submitted successfully! ID: ${result.complaint_id}`,
            "success"
        );

        this.reset();
        document.getElementById("urgency").value = 5;

        // Clear the previous similarity results.
        displaySimilarComplaints([]);

        await loadComplaints();

    } catch (error) {
        showMessage(
            "form-message",
            error.message || "Unable to submit complaint.",
            "error"
        );

        console.error("Complaint submission error:", error);

    } finally {
        
        submitButton.textContent = "Submit Complaint";
    }
});

// ---------- NAVIGATION ----------

document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", event => {
        event.preventDefault();

        const sectionId = link.getAttribute("href").slice(1);
        showSection(sectionId);
    });
});

// ---------- INITIALIZATION ----------

async function initializeDashboard() {
    updateProfile();
    configureRoleView();
    showSection("dashboard");

    await checkBackend();
    await loadAssets();
}

initializeDashboard();


// ---------- ADMIN: ADD NEW ASSET ----------

document.getElementById("add-asset-form").addEventListener("submit", async function(event) {
    event.preventDefault();

    if (!isAdmin() || !accessToken) {
        showMessage(
            "asset-form-message",
            "Only administrators can add assets.",
            "error"
        );
        return;
    }

    const submitButton = this.querySelector('button[type="submit"]');

    const assetData = {
        AssetType: document.getElementById("new-asset-type").value.trim(),
        AssetName: document.getElementById("new-asset-name").value.trim(),
        Lat: Number(document.getElementById("new-asset-lat").value),
        Long: Number(document.getElementById("new-asset-long").value),
        InstallationDate: document.getElementById("new-asset-installation").value,
        OperationalStatus: document.getElementById("new-asset-status").value,
        HealthScore: Number(document.getElementById("new-asset-health").value),
        LastMaintenanceDate:
            document.getElementById("new-asset-maintenance").value || null,
        Description: document.getElementById("new-asset-description").value.trim()
    };

    submitButton.disabled = true;
    submitButton.textContent = "Adding Asset...";

    showMessage("asset-form-message", "Registering new asset...");

    try {
        const response = await apiFetch("/assets", {
            method: "POST",
            body: JSON.stringify(assetData)
        });

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(
                getErrorMessage(result, "Unable to add asset.")
            );
        }

        showMessage(
            "asset-form-message",
            result.message || "Asset added successfully!",
            "success"
        );

        this.reset();

        document.getElementById("new-asset-health").value = 100;
        document.getElementById("new-asset-status").value = "Operational";

        // Refresh the asset list and complaint asset dropdown.
        await loadAssets();

        alert("New asset registered successfully!");

    } catch (error) {
        showMessage(
            "asset-form-message",
            error.message || "Unable to add asset.",
            "error"
        );

        console.error("Add asset error:", error);

    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Add Asset";
    }
});



// ---------- EDIT ASSET (ADMIN ONLY) ----------

async function editAsset(assetId) {
    if (!isAdmin()) {
        alert("Only administrators can edit assets.");
        return;
    }

    const asset = assets.find(a => Number(a.asset_id) === Number(assetId));

    if (!asset) {
        alert("Asset not found. Please refresh the assets.");
        return;
    }

    const assetType = prompt("Enter Asset Type:", asset.AssetType);
    if (assetType === null) return;

    const assetName = prompt("Enter Asset Name:", asset.AssetName);
    if (assetName === null) return;

    const lat = prompt("Enter Latitude:", asset.Lat);
    if (lat === null) return;

    const long = prompt("Enter Longitude:", asset.Long);
    if (long === null) return;

    const installationDate = prompt(
        "Enter Installation Date (YYYY-MM-DD):",
        asset.InstallationDate || ""
    );
    if (installationDate === null) return;

    const operationalStatus = prompt(
        "Enter Status (Operational / Under Maintenance / Non-Operational):",
        asset.OperationalStatus
    );
    if (operationalStatus === null) return;

    const healthScore = prompt("Enter Health Score (0-100):", asset.HealthScore ?? 100);
    if (healthScore === null) return;

    const lastMaintenanceDate = prompt(
        "Enter Last Maintenance Date (YYYY-MM-DD), or leave blank:",
        asset.LastMaintenanceDate || ""
    );
    if (lastMaintenanceDate === null) return;

    const description = prompt("Enter Description:", asset.Description || "");
    if (description === null) return;

    const updatedAsset = {
        AssetType: assetType.trim(),
        AssetName: assetName.trim(),
        Lat: Number(lat),
        Long: Number(long),
        InstallationDate: installationDate,
        OperationalStatus: operationalStatus.trim(),
        HealthScore: Number(healthScore),
        LastMaintenanceDate: lastMaintenanceDate || null,
        Description: description.trim() || null
    };

    if (
        !updatedAsset.AssetType ||
        !updatedAsset.AssetName ||
        !updatedAsset.InstallationDate ||
        !Number.isFinite(updatedAsset.Lat) ||
        !Number.isFinite(updatedAsset.Long) ||
        !Number.isFinite(updatedAsset.HealthScore) ||
        updatedAsset.HealthScore < 0 ||
        updatedAsset.HealthScore > 100 ||
        !["Operational", "Under Maintenance", "Non-Operational"]
            .includes(updatedAsset.OperationalStatus)
    ) {
        alert("Please enter valid asset details.");
        return;
    }

    try {
        const response = await apiFetch(`/assets/${assetId}`, {
            method: "PUT",
            body: JSON.stringify(updatedAsset)
        });

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(getErrorMessage(result, "Unable to edit asset."));
        }

        alert("Asset updated successfully!");
        await loadAssets();

    } catch (error) {
        alert("Edit failed: " + error.message);
        console.error("Edit asset error:", error);
    }
}


// ---------- ADMIN: DELETE ASSET ----------

async function deleteAsset(assetId) {
    if (!isAdmin() || !accessToken) {
        alert("Only administrators can delete assets.");
        return;
    }

    const asset = assets.find(
        item => Number(item.asset_id) === Number(assetId)
    );

    if (!asset) {
        alert("Asset not found. Please refresh the asset list.");
        return;
    }

    const confirmed = confirm(
        `Are you sure you want to delete this asset?\n\n` +
        `Asset: ${asset.AssetName}\n` +
        `Asset ID: ${assetId}\n\n` +
        `This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
        const response = await apiFetch(`/assets/${assetId}`, {
            method: "DELETE"
        });

        const result = await readResponse(response);

        if (!response.ok) {
            throw new Error(
                getErrorMessage(result, "Unable to delete asset.")
            );
        }

        alert(result.message || "Asset deleted successfully!");

        await loadAssets();

    } catch (error) {
        alert(`Asset deletion failed: ${error.message}`);
        console.error("Delete asset error:", error);
    }
}
