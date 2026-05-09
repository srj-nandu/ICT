const searchInput = document.getElementById("recordSearch");
const cards = Array.from(document.querySelectorAll(".record-card"));
const recordCheckboxes = Array.from(
    document.querySelectorAll('.record-card input[type="checkbox"][name="record_ids"]')
);
const selectedCount = document.getElementById("selectedCount");
const bulkDeleteButton = document.getElementById("bulkDeleteButton");
const selectVisibleButton = document.getElementById("selectVisible");
const clearSelectionButton = document.getElementById("clearSelection");

function isCardVisible(card) {
    return card.style.display !== "none";
}

function updateSelectionState() {
    const selected = recordCheckboxes.filter((checkbox) => checkbox.checked);

    recordCheckboxes.forEach((checkbox) => {
        checkbox.closest(".record-card")?.classList.toggle("is-selected", checkbox.checked);
    });

    if (selectedCount) {
        selectedCount.textContent = String(selected.length);
    }

    if (bulkDeleteButton) {
        bulkDeleteButton.disabled = selected.length === 0;
    }
}

if (searchInput) {
    searchInput.addEventListener("input", (event) => {
        const query = event.target.value.trim().toLowerCase();
        cards.forEach((card) => {
            const haystack = card.dataset.search || "";
            card.style.display = !query || haystack.includes(query) ? "" : "none";
        });
        updateSelectionState();
    });
}

recordCheckboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateSelectionState);
});

if (selectVisibleButton) {
    selectVisibleButton.addEventListener("click", () => {
        recordCheckboxes.forEach((checkbox) => {
            const card = checkbox.closest(".record-card");
            checkbox.checked = card ? isCardVisible(card) : false;
        });
        updateSelectionState();
    });
}

if (clearSelectionButton) {
    clearSelectionButton.addEventListener("click", () => {
        recordCheckboxes.forEach((checkbox) => {
            checkbox.checked = false;
        });
        updateSelectionState();
    });
}

updateSelectionState();
