const examples = [
    "A LinkedIn post about the future of remote work, professional tone",
    "A short social media caption about AI in education",
    "A blog intro about sustainable business trends",
    "A friendly announcement for a new product launch",
    "A concise summary for a newsletter section"
  ];
  
  const el = document.getElementById("animatedPlaceholder");
  
  let exampleIndex = 0;
  let charIndex = 0;
  let isDeleting = false;
  let isPaused = false;  // <-- NEW
  
  const cursor = "▋"; 
  
  function type() {
    if (!isPaused) {                         // <-- stop animation when paused
      const full = examples[exampleIndex];

      if (!isDeleting) {
        charIndex++;
      } else {
        charIndex--;
      }

      const text = full.substring(0, charIndex);

      el.placeholder = text + " " + cursor;

      let speed = isDeleting ? 45 : 70;

      if (!isDeleting && charIndex === full.length) {
        speed = 1300;
        isDeleting = true;
      }

      if (isDeleting && charIndex === 0) {
        isDeleting = false;
        exampleIndex = (exampleIndex + 1) % examples.length;
        speed = 350;
      }

      setTimeout(type, speed);
      return;
    }

    // If paused, check again soon
    setTimeout(type, 150);
  }

  // ---- EVENT HANDLERS ----
  el.addEventListener("focus", () => {
    isPaused = true;
    el.placeholder = "";         // optional: clear placeholder on focus
  });

  el.addEventListener("blur", () => {
    isPaused = false;
  });

  type();