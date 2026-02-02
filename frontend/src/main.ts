import './style.css'

const form = document.getElementById('searchForm') as HTMLFormElement;
const submitBtn = document.getElementById('submitBtn') as HTMLButtonElement;
const spinner = document.getElementById('spinner') as HTMLElement;
const btnText = submitBtn.querySelector('span') as HTMLElement;

const mdOutput = document.getElementById('markdownOutput') as HTMLElement;
const jsonOutput = document.getElementById('jsonOutput') as HTMLElement;
const tokenStat = document.getElementById('tokenStat') as HTMLElement;
const statusBadge = document.getElementById('statusBadge') as HTMLElement;
const queryInput = document.getElementById('queryInput') as HTMLInputElement;

// Prevent default form submission and run search
form.addEventListener('submit', async (e: Event) => {
    e.preventDefault();
    performSearch();
});

// Since we removed inline handlers, we should ensure the input also works if someone hits enter (handled by form submit usually, but let's be safe)
// Actually, form submit catches the enter key too.

async function performSearch(): Promise<void> {
    // UI Loading State
    submitBtn.disabled = true;
    spinner.style.display = 'block';
    btnText.textContent = 'Processing...';
    mdOutput.textContent = 'Fetching and parsing data...';
    jsonOutput.textContent = 'Waiting for response...';
    tokenStat.textContent = '0 Tokens';
    statusBadge.textContent = 'Loading...';

    const query = queryInput.value.trim();
    const region = (document.getElementById('region') as HTMLSelectElement).value;
    const language = (document.getElementById('language') as HTMLSelectElement).value;
    const limitInput = document.getElementById('limit') as HTMLInputElement;
    const limit = limitInput ? parseInt(limitInput.value) : 10;
    const outputFormat = (document.getElementById('output_format') as HTMLSelectElement).value;

    if (!query) {
        mdOutput.textContent = "Please enter a query or URL.";
        jsonOutput.textContent = "{}";
        statusBadge.textContent = 'Input Required';
        submitBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Run Extraction';
        return;
    }

    // Auto-detect URL
    // Simple regex: starts with http:// or https://
    const isUrl = /^(http|https):\/\/[^ "]+$/.test(query);
    const mode = isUrl ? 'scrape' : 'search';

    try {
        const response = await fetch('/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                mode: mode,
                region: region,
                language: language,
                limit: limit,
                output_format: outputFormat
            })
        });

        const data = await response.json();

        // Update UI
        mdOutput.textContent = data.formatted_output || "No output generated.";
        jsonOutput.textContent = JSON.stringify(data, null, 2);

        if (data.token_estimate) {
            tokenStat.textContent = `~${data.token_estimate} Tokens Solved`;
        }

        statusBadge.textContent = response.ok ? (data.cached ? 'Cached ⚡' : 'Live 🟢') : 'Error 🔴';

    } catch (err) {
        mdOutput.textContent = "Error connecting to API.";
        jsonOutput.textContent = err?.toString() || 'Unknown Error';
        statusBadge.textContent = 'Connection Fail';
    } finally {
        submitBtn.disabled = false;
        spinner.style.display = 'none';
        btnText.textContent = 'Run Extraction';
    }
}
