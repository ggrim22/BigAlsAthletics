  document.getElementById("filter-form").addEventListener("change", function () {
      const selectedCollection = this.querySelector("select").value;
      const downloadBtn = document.getElementById("download-btn");
      const baseUrl = downloadBtn.getAttribute("href").split("?")[0];

      if (selectedCollection) {
          downloadBtn.setAttribute("href", `${baseUrl}?collection=${selectedCollection}`);
      } else {
          downloadBtn.setAttribute("href", baseUrl);
      }
  });