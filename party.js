document.getElementById("party-form").addEventListener("submit", e => {
  e.preventDefault();
  const v = id => document.getElementById(id).value;
  const budget = parseFloat(v("budget"));
  const guests = parseInt(v("guests"), 10);
  if (!budget || budget <= 0) return PocketSmart.showError("Please enter a valid budget.");
  if (!guests || guests < 1) return PocketSmart.showError("Please enter the number of guests.");
  PocketSmart.submit("/generate-party", {
    budget, guests,
    event_type: v("event_type"), venue: v("venue"), city: v("city"), notes: v("notes"),
  });
});
