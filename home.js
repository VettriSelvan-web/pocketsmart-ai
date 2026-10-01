/* Home planner: dynamic rooms + item quantities. */
(function () {
  const ITEMS = ["Lights", "Ceiling fans", "Dining table", "Sofa", "Bed", "Wardrobe",
                 "Curtains", "Rug", "Wall art", "Storage shelves", "Table lamp", "Mirror"];
  const roomsEl = document.getElementById("rooms");
  const tpl = document.getElementById("room-template");

  function addRoom() {
    if (roomsEl.children.length >= 10) return PocketSmart.showError("You can add up to 10 rooms.");
    const node = tpl.content.firstElementChild.cloneNode(true);
    const grid = node.querySelector(".items-grid");
    ITEMS.forEach(name => {
      const label = document.createElement("label");
      label.className = "qty";
      label.innerHTML = '<span></span><input type="number" min="0" max="50" value="0">';
      label.querySelector("span").textContent = name;
      label.querySelector("input").dataset.name = name;
      grid.appendChild(label);
    });
    node.querySelector(".remove-room").addEventListener("click", () => {
      if (roomsEl.children.length > 1) node.remove();
      else PocketSmart.showError("Keep at least one room.");
    });
    roomsEl.appendChild(node);
  }

  document.getElementById("add-room").addEventListener("click", addRoom);
  addRoom();

  document.getElementById("home-form").addEventListener("submit", e => {
    e.preventDefault();
    const budget = parseFloat(document.getElementById("budget").value);
    if (!budget || budget <= 0) return PocketSmart.showError("Please enter a valid budget.");

    const rooms = [];
    roomsEl.querySelectorAll(".room").forEach(room => {
      const items = [];
      room.querySelectorAll("input[data-name]").forEach(inp => {
        const qty = parseInt(inp.value, 10);
        if (qty > 0) items.push({ name: inp.dataset.name, quantity: Math.min(qty, 50) });
      });
      if (items.length) rooms.push({ room_type: room.querySelector(".room-type").value, items });
    });
    if (!rooms.length) return PocketSmart.showError("Enter a quantity for at least one item in a room.");

    PocketSmart.submit("/generate-home", {
      budget,
      style: document.getElementById("style").value,
      notes: document.getElementById("notes").value,
      rooms,
    });
  });
})();
