document.getElementById("filter-form").addEventListener("change", function () {
    const downloadBtn = document.getElementById("download-btn");
    const baseUrl = downloadBtn.getAttribute("href").split("?")[0];

    const collectionSelect = this.querySelector("select[name='collection']");
    const productNameSelect = this.querySelector("select[name='product_name']");

    const selectedCollection = collectionSelect ? collectionSelect.value : "";
    const selectedProductName = productNameSelect ? productNameSelect.value : "";

    const params = new URLSearchParams();
    if (selectedCollection) {
        params.append("collection", selectedCollection);
    }
    if (selectedProductName) {
        params.append("product_name", selectedProductName);
    }

    if (params.toString()) {
        downloadBtn.setAttribute("href", `${baseUrl}?${params.toString()}`);
    } else {
        downloadBtn.setAttribute("href", baseUrl);
    }
});