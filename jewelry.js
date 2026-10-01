const fileInput = document.getElementById("outfit_image");
const preview = document.getElementById("preview");

fileInput.addEventListener("change", () => {
  const f = fileInput.files[0];
  if (!f) { preview.hidden = true; return; }
  if (f.size > 5 * 1024 * 1024) {
    PocketSmart.showError("Image is too large (max 5 MB).");
    fileInput.value = ""; preview.hidden = true; return;
  }
  preview.src = URL.createObjectURL(f);
  preview.hidden = false;
});

document.getElementById("jewelry-form").addEventListener("submit", e => {
  e.preventDefault();
  const v = id => document.getElementById(id).value;
  const budget = parseFloat(v("budget"));
  if (!budget || budget <= 0) return PocketSmart.showError("Please enter a valid budget.");
  const fd = new FormData();
  fd.append("budget", budget);
  ["occasion", "style", "metal", "notes"].forEach(k => fd.append(k, v(k)));
  if (fileInput.files[0]) fd.append("outfit_image", fileInput.files[0]);
  PocketSmart.submit("/generate-jewelry", fd);
});
